"""M08 saved candidates. Opening never validates, promotes or restores a session."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from backend.modules.pedagogical_design.application.commands.revise_local_chapter import (
    ReviseLocalChapter,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    as_plain,
    fingerprint,
    identifier,
    items,
    object_data,
)
from backend.modules.validation_control.application.commands.validate_assessment import (
    ValidateAssessmentCommand,
)
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
from backend.modules.work_orchestration.application.queries.verify_saved_p0_lineage import (
    verify_saved_parent,
)
from backend.modules.work_orchestration.contracts.dto.p0_codesign_trace import (
    SAVED_CODESIGN_CONTRACT,
)
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from backend.modules.work_orchestration.ports.outbound.saved_production import SavedProductionStore


def _compare_content(before: object, after: object, path: tuple[str, ...], changes: list[dict[str, object]]) -> None:
    if before == after:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            _compare_content(before.get(key), after.get(key), (*path, key), changes)
    elif isinstance(before, (tuple, list)) and isinstance(after, (tuple, list)):
        for index in range(max(len(before), len(after))):
            _compare_content(before[index] if index < len(before) else None,
                             after[index] if index < len(after) else None, (*path, str(index)), changes)
    else:
        if len(changes) >= 256:
            raise ValueError("P0_CODESIGN_COMPARISON_BOUND")
        changes.append({"id": ".".join(path), "field": "content", "before": before, "after": after})


class SavedProductionService:
    def __init__(self, store: SavedProductionStore, *,
                 compare_projection: Callable[[SavedProduction, str], Mapping[str, object]] | None = None) -> None:
        self.store = store
        self.compare_projection = compare_projection

    def save(self, record: SavedProduction) -> dict[str, object]:
        created = self.store.save(record)
        return {"saved": True, "created": created, "record_sha256": record.sha256,
                "production_ref": record.production_ref, "version_ref": record.version_ref,
                "status": "CANDIDATE", "retention": "DURABLE_R4"}

    def open(self, production_ref: str, version_ref: str) -> dict[str, object]:
        record = self.store.load(production_ref, version_ref)
        actions = self.store.actions(record)
        return {"record": record.mutable_copy(), "record_sha256": record.sha256,
                "retention": "DURABLE_R4", "active_authority": "NONE_RESTORED",
                "status": "PROMOTED" if any(a.get("kind") == "CAP-A02" for a in actions)
                          else "CANDIDATE", "new_actions": [dict(a) for a in actions]}

    def read_local_p0(self, production_ref: str, version_ref: str) -> SavedProduction:
        """Authenticated immutable record, without restoring session actions or rights."""
        record = self.store.load(production_ref, version_ref)
        if (record.production_ref, record.version_ref) != (production_ref, version_ref):
            raise ValueError("P0_SAVED_VERSION_BINDING")
        if record.data["origin"] != "LOCAL_APPLICATION" or record.p0_bundle is None:
            raise ValueError("P0_SAVED_SOURCE_REJECTED")
        return record

    def edit_local_chapter(self, production_ref: str, version_ref: str, *,
                           action_id: str, expected_sha256: str, question_id: str,
                           prompt: str, expected_answer: str, rationale: str) -> dict[str, object]:
        parent = self.read_local_p0(production_ref, version_ref)
        if parent.sha256 != expected_sha256:
            raise ValueError("R4_IDENTITY_CONFLICT")
        action_id = identifier(action_id, "action")
        version = "ver:" + fingerprint({"operation": "LOCAL_ASSEMBLY_QUESTION_EDIT_V1",
                                        "parent": parent.sha256, "action": action_id})[:32]
        assert parent.p0_bundle is not None
        try:
            child = ReviseLocalChapter().execute(parent.p0_bundle, version_ref=version,
                question_id=question_id, prompt=prompt, expected_answer=expected_answer,
                rationale=rationale)
            data = parent.mutable_copy()
            raw_reservations = data["reservations"]
            if not isinstance(raw_reservations, (list, tuple)):
                raise ValueError("R4_LOCAL_EDIT_REJECTED")
            reservations = list(raw_reservations)
            if "LOCAL_QUESTION_EDIT_UNVALIDATED" not in reservations:
                reservations.append("LOCAL_QUESTION_EDIT_UNVALIDATED")
            data.update(bundle=child.mutable_copy(),
                        view=as_plain(P0ProductionReadView.from_bundle(child).data),
                        reviews=[], validations=[], reservations=reservations,
                        provenance={**object_data(data["provenance"]),
                            "LOCAL_EDIT_PARENT_RECORD_SHA256": parent.sha256,
                            "LOCAL_EDIT_ACTION_SHA256": fingerprint(action_id),
                            "LOCAL_EDIT_OPERATION_SHA256": fingerprint({"question_id": question_id,
                                "prompt": prompt, "expected_answer": expected_answer, "rationale": rationale}),
                            "LOCAL_EDIT_ACTOR_TRACE_SHA256": fingerprint("LOCAL_UI_OPERATOR_UNAUTHENTICATED")})
            record = SavedProduction(data)
            verify_saved_parent(record, parent)
        except ValueError as error:
            if str(error) in {"R4_LOCAL_EDIT_UNAVAILABLE", "R4_LOCAL_EDIT_NO_CHANGE"}:
                raise
            raise ValueError("R4_LOCAL_EDIT_REJECTED") from None
        return {**self.save(record), "parent_version_ref": parent.version_ref,
                "draft_state": "DRAFT", "promotion": "NOT_PERFORMED"}

    def compare_local_chapter(self, production_ref: str, version_ref: str,
                              kind: str) -> dict[str, object]:
        if kind not in {"student", "correction"}:
            raise ValueError("R4_EXPORT_KIND")
        child = self.read_local_p0(production_ref, version_ref)
        assert child.p0_bundle is not None
        parent_ref = object_data(child.p0_bundle.data["lineage"])["parent_version_ref"]
        if not isinstance(parent_ref, str):
            raise ValueError("R4_COMPARISON_UNAVAILABLE")
        parent = self.read_local_p0(production_ref, parent_ref)
        if child.data["contract_id"] == SAVED_CODESIGN_CONTRACT:
            verify_saved_parent(child, parent)
            assert parent.p0_bundle is not None
            if self.compare_projection is None:
                raise ValueError("P0_CODESIGN_COMPARE_PROJECTION_REQUIRED")
            before = self.compare_projection(parent, kind)
            after = self.compare_projection(child, kind)
            changes: list[dict[str, object]] = []
            _compare_content(dict(before), dict(after), (), changes)
            return {"production_ref": production_ref, "version_ref": version_ref,
                "parent_version_ref": parent_ref, "record_sha256": child.sha256,
                "parent_record_sha256": parent.sha256, "kind": kind, "changes": changes, "promotion": "NOT_PERFORMED"}
        if object_data(child.data["provenance"]).get("LOCAL_EDIT_PARENT_RECORD_SHA256") != parent.sha256:
            raise ValueError("R4_COMPARISON_UNAVAILABLE")
        verify_saved_parent(child, parent)
        assert parent.p0_bundle is not None
        before = object_data(parent.p0_bundle.data["course_chapter"])
        after = object_data(child.p0_bundle.data["course_chapter"])
        fields: list[tuple[str, tuple[str, ...]]] = [("questions", ("prompt",))]
        if kind == "correction":
            fields.append(("teacher_answers", ("expected_answer", "rationale", "vigilance", "remediation")))
        changes = []
        for collection, keys in fields:
            originals = {str(row["id"]): row for row in items(before[collection], 60)}
            for row in items(after[collection], 60):
                old = originals[str(row["id"])]
                for key in keys:
                    if row[key] != old[key]:
                        changes.append({"id": row["id"], "field": key,
                                        "before": old[key], "after": row[key]})
        return {"production_ref": production_ref, "version_ref": version_ref,
                "parent_version_ref": parent_ref, "record_sha256": child.sha256,
                "parent_record_sha256": parent.sha256, "kind": kind, "changes": changes,
                "promotion": "NOT_PERFORMED"}

    def list_versions(self) -> list[dict[str, object]]:
        return [{"production_ref": r.production_ref, "version_ref": r.version_ref,
                 "record_sha256": r.sha256, "origin": r.data["origin"],
                 "has_bundle": r.bundle is not None or r.p0_bundle is not None,
                 "contract_id": r.data["contract_id"],
                 "title": object_data(r.data["view"]).get("title", "Production conservée"),
                 "context": as_plain(object_data(r.data["view"]).get("pedagogical_context", {})),
                 "parent_version_ref": object_data(object_data(r.data["view"])["lineage"]).get("parent_version_ref")}
                for r in self.store.list_versions()]

    def validate_p0(self, production_ref: str, version_ref: str, action_id: str,
                    expected_sha256: str) -> dict[str, object]:
        record = self.store.load(production_ref, version_ref)
        if record.sha256 != expected_sha256:
            raise ValueError("R4_IDENTITY_CONFLICT")
        if record.data["origin"] != "LOCAL_APPLICATION":
            raise ValueError("R4_DOCUMENTARY_IMPORT_READ_ONLY")
        for action in self.store.actions(record):
            if action.get("action_id") == action_id:
                if action.get("kind") != "P0-VALIDATION":
                    raise ValueError("R4_IDEMPOTENCY_CONFLICT")
                return dict(action)
        bundle = record.p0_bundle
        if bundle is None:
            raise ValueError("R6_P0_BUNDLE_REQUIRED")
        parent = None
        parent_ref = object_data(bundle.data["lineage"])["parent_version_ref"]
        if isinstance(parent_ref, str):
            parent = self.store.load(production_ref, parent_ref).p0_bundle
            if parent is None:
                raise ValueError("R6_P0_PARENT_REQUIRED")
        report = ValidateP0Command().execute(bundle, parent=parent)
        action = {"action_id": action_id, "kind": "P0-VALIDATION", "report": report}
        return dict(self.store.append_action(record, action_id, action))

    def validate(self, production_ref: str, version_ref: str, action_id: str,
                 expected_sha256: str) -> dict[str, object]:
        record = self.store.load(production_ref, version_ref)
        if record.sha256 != expected_sha256:
            raise ValueError("R4_IDENTITY_CONFLICT")
        if record.data["origin"] != "LOCAL_APPLICATION":
            raise ValueError("R4_DOCUMENTARY_IMPORT_READ_ONLY")
        for action in self.store.actions(record):
            if action.get("action_id") == action_id:
                if action.get("kind") != "CAP-A01":
                    raise ValueError("R4_IDEMPOTENCY_CONFLICT")
                return dict(action)
        bundle = record.bundle
        if bundle is None:
            raise ValueError("R4_BUNDLE_REQUIRED")
        parent: AssessmentBundle | None = None
        parent_ref = object_data(bundle.data["lineage"]).get("parent_version_ref")
        if isinstance(parent_ref, str):
            parent = self.store.load(production_ref, parent_ref).bundle
        report = ValidateAssessmentCommand().execute(bundle, production_ref=production_ref,
            version_ref=version_ref, subject_sha256=str(bundle.data["subject_sha256"]),
            validation_ref="validation:" + action_id.partition(":")[2],
            evaluated_at=datetime.now(UTC).isoformat(),
            references=items(bundle.data["references"]), parent=parent)
        action = {"action_id": action_id, "kind": "CAP-A01", "report": report.as_dict()}
        return dict(self.store.append_action(record, action_id, action))
