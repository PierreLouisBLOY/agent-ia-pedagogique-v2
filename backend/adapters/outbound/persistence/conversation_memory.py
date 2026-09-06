"""Real volatile store: atomic CAS, immutable exact versions, no filesystem."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from threading import RLock

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    as_plain,
    fingerprint,
    object_data,
)
from backend.modules.validation_control.contracts.dto.deterministic_validation import (
    AssessmentValidation,
)
from backend.modules.work_orchestration.contracts.dto.conversation import (
    ConversationRejected,
    ConversationState,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import R3Command, R3Rejected


class ConversationMemoryStore:
    def __init__(self, initial: ConversationState) -> None:
        self._state = initial
        self._versions: dict[tuple[str, str], ProductionReadView] = {}
        self._lock = RLock()
        self._r3_bundles: dict[tuple[str, str], AssessmentBundle] = {}
        self._r3_operations: dict[str, dict[str, object]] = {}
        self._r3_commands: dict[str, tuple[str, str]] = {}
        self._r3_reviews: dict[str, dict[str, object]] = {}
        self._r3_validations: dict[tuple[str, str], tuple[AssessmentValidation, ...]] = {}
        self._r3_lease: tuple[R3Command, str, int] | None = None

    def read(self, conversation_id: str) -> ConversationState | None:
        with self._lock:
            return self._state if self._state.conversation_id == conversation_id else None

    def publish(self, state: ConversationState, *, expected_revision: int,
                production: ProductionReadView | None = None) -> None:
        with self._lock:
            if self._r3_lease is not None:
                raise ConversationRejected("GENERATION_IN_PROGRESS")
            if (state.conversation_id != self._state.conversation_id
                    or self._state.revision != expected_revision
                    or state.revision != expected_revision + 1):
                raise ConversationRejected("REVISION_CONFLICT")
            if production is not None:
                key = (production.production_ref, production.version_ref)
                old = self._versions.get(key)
                if production.conversation_id != state.conversation_id or (
                    old is not None and old != production
                ):
                    raise ConversationRejected("APPLICATION_FAILURE")
                if old is None and len(self._versions) >= 3:
                    raise ConversationRejected("SESSION_CAPACITY_REACHED")
                if state.view["current_candidate"] != {
                    "production_ref": key[0], "version_ref": key[1],
                }:
                    raise ConversationRejected("APPLICATION_FAILURE")
                self._versions[key] = production
            elif state.view["current_candidate"] != self._state.view["current_candidate"]:
                raise ConversationRejected("APPLICATION_FAILURE")
            self._state = state

    def read_version(self, *, conversation_id: str, production_ref: str,
                     version_ref: str) -> ProductionReadView | None:
        with self._lock:
            if conversation_id != self._state.conversation_id:
                return None
            return self._versions.get((production_ref, version_ref))

    def contains_production(self, *, conversation_id: str, production_ref: str) -> bool:
        with self._lock:
            return conversation_id == self._state.conversation_id and any(
                ref == production_ref for ref, _ in self._versions
            )

    def r3_bundle(self, production_ref: str, version_ref: str) -> AssessmentBundle | None:
        with self._lock:
            return self._r3_bundles.get((production_ref, version_ref))

    def r3_receipt(self, command: R3Command) -> dict[str, object] | None:
        with self._lock:
            existing = self._r3_commands.get(command.command_id)
            if existing is None:
                return None
            if existing[0] != command.fingerprint:
                raise R3Rejected("IDEMPOTENCY_CONFLICT")
            return object_data(as_plain(self._r3_operations[existing[1]]))

    def r3_reserve(self, command: R3Command, operation_ref: str) -> dict[str, object]:
        with self._lock:
            replay = self.r3_receipt(command)
            if replay is not None:
                return replay
            if command.body["conversation_id"] != self._state.conversation_id:
                raise R3Rejected("CONVERSATION_NOT_FOUND")
            active = self._state.view.get("active_generation")
            if self._r3_lease is not None or isinstance(active, Mapping) and active.get("state") == "IN_PROGRESS":
                raise R3Rejected("GENERATION_IN_PROGRESS")
            if command.body["expected_revision"] != self._state.revision:
                raise R3Rejected("REVISION_CONFLICT")
            if len(self._r3_commands) >= 64 or operation_ref in self._r3_operations:
                raise R3Rejected("SESSION_CAPACITY_REACHED")
            key = (str(command.body["production_ref"]), command.version_ref)
            if key not in self._versions:
                raise R3Rejected("PRODUCTION_VERSION_NOT_FOUND")
            if command.operation == "modifications" and self._state.view["current_candidate"] != {
                    "production_ref": key[0], "version_ref": key[1]}:
                raise R3Rejected("REVISION_CONFLICT")
            if command.operation == "modifications" and len(self._versions) >= 3:
                raise R3Rejected("SESSION_CAPACITY_REACHED")
            report_count = len(self._r3_validations.get(key, ())) + sum(
                1 for r in self._r3_reviews.values()
                if (r["production_ref"], r["version_ref"]) == key)
            if command.operation != "modifications" and report_count >= 8:
                raise R3Rejected("SESSION_CAPACITY_REACHED")
            revision = self._state.revision + 1
            view = object_data(as_plain(self._state.view))
            view["revision"] = revision
            new_state = replace(self._state, revision=revision, view=view)
            result: dict[str, object] = {"operation_ref": operation_ref, "state": "RUNNING",
                "command_id": command.command_id, "production_ref": key[0], "version_ref": key[1],
                "revision": revision, "review_ref": "review:" + operation_ref.split(":")[1] if command.operation == "reviews" else None}
            self._r3_commands[command.command_id] = (command.fingerprint, operation_ref)
            self._r3_operations[operation_ref] = result
            self._r3_lease = (command, operation_ref, revision)
            self._state = new_state
            return dict(result)

    def r3_complete(self, operation_ref: str, result: Mapping[str, object], *,
                    production: ProductionReadView | None = None,
                    bundle: AssessmentBundle | None = None,
                    validation: AssessmentValidation | None = None,
                    review: Mapping[str, object] | None = None) -> None:
        with self._lock:
            lease = self._r3_lease
            if lease is None or lease[1] != operation_ref or lease[2] != self._state.revision:
                raise R3Rejected("REVISION_CONFLICT")
            command = lease[0]
            old_key = (str(command.body["production_ref"]), command.version_ref)
            key = old_key if production is None else (production.production_ref, production.version_ref)
            if result.get("state") not in {"SUCCEEDED", "FAILED_NO_EFFECT", "FAILED_OUTPUT", "UNKNOWN"}:
                raise R3Rejected("APPLICATION_FAILURE")
            if result["state"] != "SUCCEEDED" and any(v is not None for v in (production, bundle, validation, review)):
                raise R3Rejected("APPLICATION_FAILURE")
            if production is not None and (production.conversation_id != self._state.conversation_id
                    or production.production_ref != old_key[0] or key in self._versions
                    or len(self._versions) >= 3 or command.operation != "modifications"):
                raise R3Rejected("REVISION_CONFLICT")
            if bundle is not None:
                if ((bundle.production_ref, bundle.version_ref) != key or key in self._r3_bundles
                        or validation is None or validation.overall_status == "FAIL"):
                    raise R3Rejected("ASSESSMENT_PUBLICATION_REJECTED")
            if production is not None and bundle is None:
                raise R3Rejected("ASSESSMENT_PUBLICATION_REJECTED")
            selected_bundle = bundle or self._r3_bundles.get(key)
            if validation is not None and ((validation.production_ref, validation.version_ref) != key
                    or validation.bundle_sha256 != (selected_bundle.sha256 if selected_bundle else None)):
                raise R3Rejected("ASSESSMENT_REFERENCE")
            reports = self._r3_validations.get(key, ())
            review_count = sum(1 for r in self._r3_reviews.values() if (r["production_ref"], r["version_ref"]) == key)
            if len(reports) + review_count + int(validation is not None) + int(review is not None) > 8:
                raise R3Rejected("SESSION_CAPACITY_REACHED")
            if review is not None:
                current_bundle = self._r3_bundles.get(key)
                if (current_bundle is None or (review.get("production_ref"), review.get("version_ref")) != key
                        or review.get("bundle_sha256") != current_bundle.sha256):
                    raise R3Rejected("ASSESSMENT_REFERENCE")
            versions = dict(self._versions)
            bundles = dict(self._r3_bundles)
            validations = dict(self._r3_validations)
            reviews = dict(self._r3_reviews)
            if production is not None:
                versions[key] = production
            if bundle is not None:
                bundles[key] = bundle
            if validation is not None:
                validations[key] = (*reports, validation)
            if review is not None:
                reviews[str(review["review_ref"])] = object_data(as_plain(review))
            revision = self._state.revision + 1
            view = object_data(as_plain(self._state.view))
            view["revision"] = revision
            if production is not None:
                view["current_candidate"] = {"production_ref": key[0], "version_ref": key[1]}
            state = replace(self._state, revision=revision, view=view)
            final = {**self._r3_operations[operation_ref], **dict(result), "revision": revision,
                     "production_ref": key[0], "version_ref": key[1]}
            self._versions, self._r3_bundles = versions, bundles
            self._r3_validations, self._r3_reviews = validations, reviews
            self._r3_operations[operation_ref] = final
            self._state, self._r3_lease = state, None

    def r3_report(self, reference: str, *, review: bool = False) -> dict[str, object]:
        with self._lock:
            if review:
                value = self._r3_reviews.get(reference)
                if value is None:
                    value = next((r for r in self._r3_operations.values() if r.get("review_ref") == reference), None)
            else:
                value = self._r3_operations.get(reference)
            if value is None:
                raise R3Rejected("REPORT_NOT_FOUND")
            return object_data(as_plain(value))

    def r3_snapshot(self, production_ref: str, version_ref: str) -> dict[str, object]:
        with self._lock:
            key = (production_ref, version_ref)
            if key not in self._versions:
                raise R3Rejected("PRODUCTION_VERSION_NOT_FOUND")
            bundle = self._r3_bundles.get(key)
            reviews = [r for r in self._r3_reviews.values() if (r["production_ref"], r["version_ref"]) == key]
            validations = [r.as_dict() for r in self._r3_validations.get(key, ())]
            return {"production_ref": production_ref, "version_ref": version_ref,
                "subject_sha256": fingerprint({"content": self._versions[key].data["content"],
                                               "sections": self._versions[key].data["sections"]}),
                "bundle": as_plain(bundle.data) if bundle else None, "bundle_sha256": bundle.sha256 if bundle else None,
                "review_status": "REVIEWED" if any(r["status"] == "completed" for r in reviews) else "REVIEW_NOT_RUN",
                "reviews": as_plain(reviews), "validations": validations, "validation_state": "CANDIDATE",
                "badge": "NON VALIDÉE", "revision": self._state.revision,
                "current_candidate": as_plain(self._state.view["current_candidate"]),
                "versions": [{"production_ref": p, "version_ref": v} for p, v in self._versions if p == production_ref]}

    def r3_clear(self) -> None:
        with self._lock:
            self._r3_lease = None
            self._r3_bundles.clear()
            self._r3_reviews.clear()
            self._r3_validations.clear()
            self._r3_operations.clear()
            self._r3_commands.clear()
            self._versions.clear()
