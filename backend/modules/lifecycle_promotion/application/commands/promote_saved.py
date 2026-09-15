"""CAP-A02: explicit gate after exact CAP-R02/CAP-A01; no implicit promotion."""
from datetime import datetime

from backend.modules.lifecycle_promotion.contracts.dto.promotion import PromotionGate
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    items,
    object_data,
)
from backend.modules.work_orchestration.ports.outbound.saved_production import SavedProductionStore


class PromoteSavedCommand:
    def __init__(self, store: SavedProductionStore) -> None:
        self.store = store

    def execute(self, *, production_ref: str, version_ref: str, action_id: str,
                expected_sha256: str, gate: PromotionGate | None, now: datetime) -> dict[str, object]:
        record = self.store.load(production_ref, version_ref)
        if record.sha256 != expected_sha256:
            raise ValueError("R4_IDENTITY_CONFLICT")
        if record.data["origin"] != "LOCAL_APPLICATION":
            raise ValueError("R4_DOCUMENTARY_IMPORT_READ_ONLY")
        actions = self.store.actions(record)
        for action in actions:
            if action.get("action_id") == action_id:
                if action.get("kind") != "CAP-A02":
                    raise ValueError("R4_IDEMPOTENCY_CONFLICT")
                return dict(action)  # Receipt read only; never reactivate consumed authority.
        reports = [object_data(a.get("report")) for a in actions if a.get("kind") == "CAP-A01"]
        if not reports or record.bundle is None:
            raise ValueError("R4_VALIDATION_REQUIRED")
        report = reports[-1]
        if (report.get("version_ref") != version_ref
                or report.get("bundle_sha256") != record.bundle.sha256
                or report.get("overall_status") not in {"PASS", "WARNING"}
                or any(c.get("status") == "FAIL" for c in items(report.get("checks")))):
            raise ValueError("R4_VALIDATION_FAILED")
        for review in items(record.data["reviews"]):
            if (review.get("promotion_blocked_by_review") is True
                    or str(review.get("status", "completed")).lower() != "completed"
                    or str(review.get("overall_assessment", "")).lower() in {"unusable", "incomplete"}
                    or any(str(f.get("severity")).lower() == "blocking" for f in items(review.get("findings", [])))):
                raise ValueError("R4_BLOCKING_REVIEW")
        if gate is None or not gate.permits(record_sha256=record.sha256,
                validation_ref=str(report["validation_ref"]), now=now):
            raise ValueError("R4_FRESH_HUMAN_GATE_REQUIRED")
        if any(a.get("kind") == "CAP-A02" for a in actions):
            raise ValueError("R4_ALREADY_PROMOTED")
        action = {"action_id": action_id, "kind": "CAP-A02", "status": "PROMOTED",
                  "version_ref": version_ref, "bundle_sha256": record.bundle.sha256,
                  "validation_ref": report["validation_ref"], "decision_ref": gate.decision_ref,
                  "actor": gate.actor, "decided_at": now.isoformat(),
                  "a16_warning_preserved": True, "authority_status": "CONSUMED"}
        return dict(self.store.append_action(record, action_id, action,
                    expected_actions_sha256=fingerprint(actions)))
