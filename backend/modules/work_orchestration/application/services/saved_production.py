"""M08 saved candidates. Opening never validates, promotes or restores a session."""
from __future__ import annotations

from datetime import UTC, datetime

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    items,
    object_data,
)
from backend.modules.validation_control.application.commands.validate_assessment import (
    ValidateAssessmentCommand,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from backend.modules.work_orchestration.ports.outbound.saved_production import SavedProductionStore


class SavedProductionService:
    def __init__(self, store: SavedProductionStore) -> None:
        self.store = store

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

    def list_versions(self) -> list[dict[str, object]]:
        return [{"production_ref": r.production_ref, "version_ref": r.version_ref,
                 "record_sha256": r.sha256, "origin": r.data["origin"],
                 "has_bundle": r.bundle is not None} for r in self.store.list_versions()]

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
