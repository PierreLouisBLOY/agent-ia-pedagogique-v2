"""Conversation owner: admission, idempotence and atomic candidate publication."""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime
from typing import cast

from backend.modules.pedagogical_context.application.services.conversation_context import (
    ConversationContextService,
)
from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    FIELDS,
    ConfirmedConversationContext,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import (
    RETENTION,
    CommandReceipt,
    ConversationCommand,
    ConversationRejected,
    ConversationState,
    identity,
    plain,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.ports.outbound.conversation_store import ConversationStore
from backend.modules.work_orchestration.ports.outbound.generation_job import (
    GenerationJobPort,
    GenerationJobResult,
)


def initial_conversation(conversation_id: str, expires_at: datetime) -> ConversationState:
    identity(conversation_id, "conv")
    return ConversationState(conversation_id, 1, {
        "conversation_id": conversation_id, "revision": 1, "messages": [],
        "current_request_id": None,
        "context": {"status": "EMPTY", "values": {}, "provenance": []},
        "missing_fields": list(FIELDS), "context_revision": 0,
        "confirmed_context_sha256": None, "current_candidate": None,
        "active_generation": None, "retention": RETENTION,
        "expiration": expires_at.isoformat().replace("+00:00", "Z"), "capacity": 3,
    })


class ConversationService:
    def __init__(
        self, *, conversation_id: str, store: ConversationStore, jobs: GenerationJobPort,
        contexts: ConversationContextService, new_id: Callable[[str], str],
        clock: Callable[[], datetime], expires_at: datetime,
        ambiguity_observer: Callable[[], None] | None = None,
    ) -> None:
        self._id = identity(conversation_id, "conv")
        self._store, self._jobs, self._contexts = store, jobs, contexts
        self._new_id, self._clock, self._expires = new_id, clock, expires_at
        self._request: ConversationDraftRequest | None = None
        self._ambiguity_observer = ambiguity_observer

    def _state(self) -> ConversationState:
        state = self._store.read(self._id)
        if state is None:
            raise ConversationRejected("CONVERSATION_NOT_FOUND")
        if self._clock() >= self._expires:
            raise ConversationRejected("CONVERSATION_EXPIRED")
        return state

    def snapshot(self) -> Mapping[str, object]:
        return self._state().view

    def execute(self, command: ConversationCommand) -> Mapping[str, object]:
        if type(command) is not ConversationCommand:
            raise ConversationRejected("VALIDATION_REJECTED")
        if command.body["conversation_id"] != self._id:
            raise ConversationRejected("CONVERSATION_NOT_FOUND")
        state = self._state()
        for receipt in state.receipts:
            if receipt.command_id == command.command_id:
                if receipt.fingerprint != command.fingerprint:
                    raise ConversationRejected("IDEMPOTENCY_CONFLICT")
                return receipt.data
        if command.body["expected_revision"] != state.revision:
            raise ConversationRejected("REVISION_CONFLICT")
        active = state.view["active_generation"]
        if isinstance(active, Mapping):
            if active["state"] == "IN_PROGRESS":
                raise ConversationRejected("GENERATION_IN_PROGRESS")
            if active["state"] == "UNKNOWN":
                raise ConversationRejected("GENERATION_OUTCOME_UNKNOWN")
        if len(state.receipts) >= 64:
            raise ConversationRejected("SESSION_CAPACITY_REACHED")
        if command.operation == "messages":
            return self._message(state, command)
        return self._start(state, command)

    def _message(self, state: ConversationState, command: ConversationCommand) -> Mapping[str, object]:
        view = cast(dict[str, object], plain(state.view))
        messages = cast(list[dict[str, object]], view["messages"])
        if len(messages) >= 40:
            raise ConversationRejected("SESSION_CAPACITY_REACHED")
        body = command.body
        text = str(body["text"])
        message_id = self._new_id("msg")
        context = cast(dict[str, object], view["context"])
        values = cast(Mapping[str, object], context["values"])
        patch = cast(Mapping[str, object], body["context_patch"])
        brief = state.brief
        conflicts = state.conflicts
        outside = re.search(r"\b(modifie|modifier|corrige|corriger|valide|valider|exporte|exporter)\b",
                            text.casefold()) is not None
        if outside:
            response_kind = "OUT_OF_SCOPE"
            response = "Cette opération appartient à une étape ultérieure, hors R2. Aucune action effectuée."
        else:
            update = self._contexts.propose(text=text, current=values, patch=patch,
                                            previous_text=brief)
            conflicts = tuple(sorted((set(conflicts) | set(update.conflicts)) - set(patch)))
            missing = tuple(f for f in FIELDS if f not in update.values or f in conflicts)
            if missing and self._ambiguity_observer is not None:
                self._ambiguity_observer()
            confirmed = None
            if body["confirm_context"]:
                if missing:
                    raise ConversationRejected("CONTEXT_CLARIFICATION_REQUIRED")
                confirmed = ConfirmedConversationContext(update.values)
            provenance = cast(list[dict[str, object]], context["provenance"])
            for field in FIELDS:
                source = ("CONFIRMATION" if confirmed else "EXPLICIT_PATCH" if field in patch
                          else "EXTRACTION" if field in update.extracted_fields else None)
                if source:
                    provenance.append({"field": field, "message_id": message_id,
                                       "source_kind": source})
            if len(provenance) > 40:
                raise ConversationRejected("SESSION_CAPACITY_REACHED")
            context = {"status": "CONFIRMED" if confirmed else "PROPOSED",
                       "values": update.values, "provenance": provenance}
            view["context"] = context
            view["missing_fields"] = missing
            view["confirmed_context_sha256"] = confirmed.sha256 if confirmed else None
            view["context_revision"] = cast(int, view["context_revision"]) + 1
            view["current_request_id"] = self._new_id("req")
            view["active_generation"] = None
            if not brief or state.view["current_candidate"] is not None:
                brief = text
            response_kind = "CONTEXT_SUMMARY" if not missing else "CLARIFICATION"
            response = ("Contexte confirmé. La génération d’une candidate nécessite une autorisation distincte."
                        if confirmed else "Confirmez ou corrigez le récapitulatif pédagogique."
                        if not missing else "Précisez les champs manquants ou contradictoires : "
                        + ", ".join(missing) + ". Pour BTS CG, l’année doit être précisée.")
        timestamp = self._clock().isoformat().replace("+00:00", "Z")
        messages.extend([
            {"message_id": message_id, "role": "USER", "text": text,
             "created_at": timestamp, "based_on_revision": state.revision},
            {"message_id": self._new_id("msg"), "role": "ASSISTANT", "text": response,
             "created_at": timestamp, "based_on_revision": state.revision,
             "response_kind": response_kind},
        ])
        if sum(len(str(m["text"]).encode()) for m in messages) > 64 * 1024:
            raise ConversationRejected("SESSION_CAPACITY_REACHED")
        view["revision"] = state.revision + 1
        receipt = CommandReceipt(command.command_id, command.fingerprint, view)
        updated = replace(state, revision=state.revision + 1, view=view,
                          receipts=(*state.receipts, receipt), conflicts=conflicts, brief=brief)
        self._store.publish(updated, expected_revision=state.revision)
        return receipt.data

    def _start(self, state: ConversationState, command: ConversationCommand) -> Mapping[str, object]:
        context = cast(Mapping[str, object], state.view["context"])
        if (context["status"] != "CONFIRMED" or state.view["missing_fields"]
                or command.body["confirmed_context_sha256"] != state.view["confirmed_context_sha256"]):
            raise ConversationRejected("CONTEXT_NOT_CONFIRMED")
        if state.job_count >= 3:
            raise ConversationRejected("SESSION_CAPACITY_REACHED")
        request = ConversationDraftRequest(
            str(state.view["current_request_id"]), self._id, self._new_id("gen"), state.brief,
            ConfirmedConversationContext(cast(Mapping[str, object], context["values"])),
        )
        self._jobs.authorize(request)
        view = dict(state.view)
        view["revision"] = state.revision + 1
        view["active_generation"] = {"generation_id": request.generation_id,
                                     "state": "IN_PROGRESS", "error_code": None,
                                     "production_ref": None, "version_ref": None}
        response = {"conversation_id": self._id, "revision": state.revision + 1,
                    "generation_id": request.generation_id, "state": "IN_PROGRESS"}
        receipt = CommandReceipt(command.command_id, command.fingerprint, response)
        self._store.publish(replace(state, revision=state.revision + 1, view=view,
                                    job_count=state.job_count + 1,
                                    receipts=(*state.receipts, receipt)),
                            expected_revision=state.revision)
        self._request = request
        try:
            self._jobs.start(request)
        except Exception:
            # A port failure may follow dispatch: never infer absence of effects or retry.
            self._finish(GenerationJobResult(request.generation_id, "UNKNOWN",
                                            error_code="GENERATION_OUTCOME_UNKNOWN"))
        return receipt.data

    def poll(self) -> None:
        """Called independently by the host, never by a read query."""
        if self._request is None:
            return
        try:
            result = self._jobs.poll()
        except Exception:
            result = GenerationJobResult(self._request.generation_id, "UNKNOWN",
                                          error_code="GENERATION_OUTCOME_UNKNOWN")
        if result is not None:
            self._finish(result)

    def _finish(self, result: GenerationJobResult) -> None:
        request = self._request
        state = self._store.read(self._id)
        if request is None or state is None or result.generation_id != request.generation_id:
            raise ConversationRejected("APPLICATION_FAILURE")
        view = dict(state.view)
        production = None
        terminal = result.state
        code = result.error_code
        try:
            if result.draft is not None:
                production = ProductionReadView.from_draft(result.draft, request, self._new_id("ver"))
        except (ValueError, TypeError):
            terminal, code = "FAILED_OUTPUT", "GENERATION_OUTPUT_INVALID"
        active = {"generation_id": request.generation_id, "state": terminal,
                  "error_code": ConversationRejected(code).code if code else None,
                  "production_ref": production.production_ref if production else None,
                  "version_ref": production.version_ref if production else None}
        view["active_generation"] = active
        view["revision"] = state.revision + 1
        if production:
            view["current_candidate"] = {"production_ref": production.production_ref,
                                         "version_ref": production.version_ref}
        try:
            self._store.publish(replace(state, revision=state.revision + 1, view=view),
                                expected_revision=state.revision, production=production)
        except Exception:
            # No candidate pointer may escape a failed atomic publication. Stay fail-closed.
            failed = dict(state.view)
            failed["revision"] = state.revision + 1
            failed["active_generation"] = {"generation_id": request.generation_id, "state": "UNKNOWN",
                "error_code": "GENERATION_OUTCOME_UNKNOWN", "production_ref": None, "version_ref": None}
            self._store.publish(replace(state, revision=state.revision + 1, view=failed),
                                expected_revision=state.revision)
        self._request = None

    def close(self) -> None:
        self._jobs.close()
        self.poll()
