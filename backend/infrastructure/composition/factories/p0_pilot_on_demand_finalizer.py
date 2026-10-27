"""Translate one stable Application confirmation into the existing pilot gate.

No temporal object is made at startup. The ordinary pilot broker retains the
original LOCK, source, inventory, budget, slot, transport, and result paths.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_pilot_effect_broker import (
    P0PilotEffectBroker,
)
from backend.adapters.outbound.generation.openai.p0_pilot_effect_gate import (
    P0PilotEffectGate,
)
from backend.adapters.outbound.persistence.p0_pilot_confirmation import (
    P0PilotConfirmationStore,
    PilotLedger,
)
from backend.adapters.outbound.persistence.p0_pilot_incident import (
    OWNER_SCOPE,
    P0PilotIncidentDisposition,
)
from backend.infrastructure.composition.factories.p0_normal_profile import (
    require_openai_environment_key,
)
from backend.infrastructure.composition.factories.p0_pilot_effect_binding import (
    P0PilotEffectBinding,
)
from backend.infrastructure.composition.factories.p0_pilot_on_demand_contract import (
    DOCUMENTS,
    derive,
)
from backend.infrastructure.filesystem import (
    atomic_publish_fresh,
    capture_secure_path,
    private_temporary_file,
    read_file_nofollow,
)
from backend.modules.work_orchestration.application.services.p0_creation import (
    P0CreationService,
)


class Effect(Protocol):
    generation: P0PilotEffectGate
    binding: P0PilotEffectBinding
    broker: P0PilotEffectBroker
    source_receipts: Callable[[Mapping[str, object]], Sequence[Mapping[str, object]]]
    def prepare_local_credential(self) -> None: ...
    def close(self) -> None: ...


class P0PilotOnDemandFinalizer:
    """Effect adapter called only by the final Application consent command."""

    def __init__(self, *, recipe: Mapping[str, object],
                 templates: Mapping[str, Mapping[str, object]],
                 normal_profile: Mapping[str, object],
                 documents_root: Path, confirmation: P0PilotConfirmationStore,
                 service: P0CreationService,
                 effect_factory: Callable[[Path, str, Callable[[Mapping[str, object]], None]], Effect],
                 incident: P0PilotIncidentDisposition | None = None) -> None:
        self.recipe = dict(recipe)
        self.templates = {key: dict(value) for key, value in templates.items()}
        self.normal_profile = dict(normal_profile)
        self.documents_root = documents_root
        self.confirmation = confirmation
        self.service = service
        self.effect_factory = effect_factory
        self.incident = incident
        self._root_identity = capture_secure_path(documents_root, allowed_root=documents_root)
        if not self._root_identity.is_directory or confirmation.recipe_sha256 != sha(canonical(recipe)):
            raise ValueError("P1_PILOT_ON_DEMAND_ROOT_REQUIRED")
        self._effects: list[Effect] = []

    def _publish(self, path: Path, data: Mapping[str, object]) -> str:
        if not self._root_identity.same_identity(capture_secure_path(
                self.documents_root, allowed_root=self.documents_root)):
            raise ValueError("P1_PILOT_ON_DEMAND_ROOT_CHANGED")
        raw = canonical(data)
        if capture_secure_path(path, allowed_root=self.documents_root).exists:
            raise ValueError("P1_PILOT_ON_DEMAND_DOCUMENT_EXISTS")
        temporary = private_temporary_file(self.documents_root,
            allowed_root=self.documents_root, prefix="p0-derived-", suffix=".pending")
        with temporary.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_publish_fresh(temporary, path, allowed_root=self.documents_root)
        if read_file_nofollow(path, allowed_root=self.documents_root,
                             maximum_bytes=131_072) != raw:
            raise ValueError("P1_PILOT_ON_DEMAND_DOCUMENT_CHANGED")
        return sha(raw)

    def execute(self, request: Mapping[str, object],
                sources: Sequence[Mapping[str, object]],
                stable: Mapping[str, object], consent: Mapping[str, object],
                now: datetime) -> dict[str, object]:
        # This mode never falls back to getpass or stdin. A missing environment
        # key is rejected before temporal records, PENDING, LOCK or reservation.
        if any(consent.get(key) is not True for key in (
                "transfer_accepted", "cost_bound_accepted", "double_execution_cost_risk_accepted")):
            raise ValueError("P1_PILOT_EXACT_CONSENT_REQUIRED")
        require_openai_environment_key()
        command = str(consent["command_id"])
        paths = {key: self.documents_root / f"p0-derived.{command}.{key}.json"
            for key in DOCUMENTS}
        docs = derive(self.recipe, self.templates, self.normal_profile,
            at=now, paths=paths)
        digests = {key: self._publish(paths[key], docs[key]) for key in DOCUMENTS}
        pending_sha: str | None = None

        def pending_check(current: Mapping[str, object]) -> None:
            if pending_sha is None:
                raise ValueError("P1_PILOT_CONFIRMATION_NOT_CURRENT")
            from backend.adapters.outbound.generation.openai.p0_content import (
                build_p0_content_request,
            )
            from backend.adapters.outbound.generation.openai.p0_normal import (
                NormalP0GenerationAdapter,
            )
            if sha(NormalP0GenerationAdapter.body(build_p0_content_request(current))) != stable["request_sha256"]:
                raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
            self.confirmation.require_current(ledger=cast(PilotLedger, effect.broker.ledger),
                command_id=command, pending_sha256=pending_sha, now=effect.broker.clock())

        effect = self.effect_factory(paths["effect"], digests["effect"], pending_check)
        self._effects.append(effect)
        dynamic_sources = effect.source_receipts(request)
        if len(dynamic_sources) != len(sources) or not dynamic_sources:
            raise ValueError("P1_PILOT_ON_DEMAND_SOURCE_CHANGED")
        for before, after in zip(sources, dynamic_sources, strict=True):
            expected_owner = docs["permission"]["owner_decision_sha256"]
            if (before.get("owner_admission_sha256") !=
                    self.templates["permission"]["owner_decision_sha256"]
                or after.get("owner_admission_sha256") != expected_owner
                or canonical({k: v for k, v in before.items()
                    if k != "owner_admission_sha256"}) != canonical({
                    k: v for k, v in after.items()
                    if k != "owner_admission_sha256"})):
                raise ValueError("P1_PILOT_ON_DEMAND_SOURCE_CHANGED")
        if self.incident is not None:
            # The new marker is a separately adopted local disposition. It is
            # published only by this consented Application command, after the
            # environment key has been prepared and before mixed preview.
            effect.prepare_local_credential()
            if effect.broker.clock() >= utc(docs["authority"]["expires_at_utc"]):
                raise ValueError("P1_PILOT_EFFECT_AUTHORITY_REQUIRED")
            with effect.broker.ledger.locked():
                ledger = cast(PilotLedger, effect.broker.ledger)
                self.confirmation.require_not_revoked(ledger=ledger)
                self.incident.assert_reviewed()
                if capture_secure_path(self.incident.path,
                        allowed_root=self.incident.confirmation_root).exists:
                    self.incident.read()
                else:
                    self.incident.publish(ledger=ledger, now=now, operator=OWNER_SCOPE)
        normal = effect.generation.preview(request=request,
            preparation_ref=str(consent["preparation_ref"]),
            preparation_sha256=str(consent["preparation_sha256"]),
            source_receipts=dynamic_sources)
        shown = cast(Mapping[str, object], normal["preview"])
        if (normal.get("state") != "LOCAL_OPERATOR_CONSENT_REQUIRED"
            or normal.get("provider_attempts") != 0
            or any(shown.get(key) != stable.get(key) for key in (
                "request_sha256", "request_bytes", "request_body_utf8",
                "context_sha256", "reference_set_sha256", "cost_bound_usd"))
            or canonical(shown.get("source_receipts")) != canonical(dynamic_sources)
            or shown.get("cost_bound_usd") != "0.1237945"
            or shown.get("permission_sha256") != digests["permission"]
            or not isinstance(shown.get("preflight"), Mapping)
            or cast(Mapping[str, object], shown["preflight"]).get("cost_bound_usd")
                != stable["cost_bound_usd"]):
            raise ValueError("P1_PILOT_ON_DEMAND_PREVIEW_CHANGED")
        import json
        body = json.loads(str(shown["request_body_utf8"]))
        if any(body.get(key) != value for key, value in
               cast(Mapping[str, object], stable["request_parameters"]).items()):
            raise ValueError("P1_PILOT_ON_DEMAND_PARAMETERS_CHANGED")
        if self.incident is None:
            effect.prepare_local_credential()
        record = {"schema": self.confirmation.pending_schema,
            **({"right_id": self.confirmation.right_id} if self.confirmation.right_id is not None else {}),
            "recipe_sha256": sha(canonical(self.recipe)), "command_id": command,
            "stable_preview_sha256": sha(canonical(stable)),
            "normal_preview_sha256": str(normal["preview_sha256"]),
            "issued_at_utc": docs["authority"]["issued_at_utc"],
            "expires_at_utc": docs["authority"]["expires_at_utc"],
            "permission_sha256": digests["permission"],
            "decision_sha256": digests["decision"],
            "envelope_sha256": digests["envelope"],
            "authority_sha256": digests["authority"],
            "effect_sha256": digests["effect"],
            "transfer_accepted": True, "cost_bound_accepted": True,
            "double_execution_cost_risk_accepted": True}
        with effect.broker.ledger.locked():
            pending_sha = self.confirmation.begin(ledger=cast(PilotLedger, effect.broker.ledger),
                record=record, now=now)
        effect.binding.activate(self.service)
        translated = {"command_id": command,
            "preparation_ref": consent["preparation_ref"],
            "preparation_sha256": consent["preparation_sha256"],
            "preview_sha256": normal["preview_sha256"],
            "transfer_accepted": True, "cost_bound_accepted": True,
            "double_execution_cost_risk_accepted": True}
        effect.generation.accept(request=request, consent=translated,
            source_receipts=dynamic_sources)
        result = effect.generation.dispatch(command_id=command,
            run=lambda: self.service.execute("generate", {
                key: translated[key] for key in (
                    "command_id", "preparation_ref", "preparation_sha256")}))
        return {**result, "pilot_confirmation_sha256": pending_sha,
            "pilot_authority_sha256": digests["authority"]}

    def close(self) -> None:
        for effect in self._effects:
            effect.close()
