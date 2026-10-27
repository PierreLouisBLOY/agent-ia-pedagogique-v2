"""Prepare a distinct local candidate. No publication, provider or ledger write."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import cast

from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
)
from backend.modules.pedagogical_design.application.commands.repair_captured_sections import (
    CONTENT_FIELDS,
    RepairCapturedSectionIds,
    SectionIdRepair,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    object_data,
)
from backend.modules.pedagogical_design.ports.captured_content_validation import (
    CapturedContentValidation,
)
from backend.modules.validation_control.application.commands.validate_p0 import ValidateP0Command
from backend.modules.work_orchestration.contracts.dto.p0_production_read_view import (
    P0ProductionReadView,
)
from backend.modules.work_orchestration.contracts.dto.rejected_capture import (
    RejectedCapture,
    RejectedCaptureRequest,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from backend.shared_kernel._safe_data import freeze_safe_mapping


@dataclass(frozen=True, slots=True)
class PreparedRecoveredCapture:
    record: SavedProduction = field(repr=False)
    audit: Mapping[str, object]


class PrepareRecoveredCapture:
    def __init__(self, validator: CapturedContentValidation, *,
                 repair: Callable[[Mapping[str, object]], SectionIdRepair] | None = None,
                 plan_sha256: str | None = None, adoption_sha256: str | None = None,
                 scope: RejectedCaptureRequest | None = None) -> None:
        self.validator = validator
        self.repair = repair or RepairCapturedSectionIds().execute
        self.plan_sha256, self.adoption_sha256 = plan_sha256, adoption_sha256
        self.scope = scope

    def execute(self, capture: RejectedCapture) -> PreparedRecoveredCapture:
        if type(capture) is not RejectedCapture:
            raise ValueError("LOCAL_RECOVERY_CAPTURE_REQUIRED")
        if self.scope is not None and capture.request != self.scope:
            raise ValueError("LOCAL_RECOVERY_CAPTURE_SCOPE_CHANGED")
        content = self.validator.parse(capture.output_text, capture.dispatch)
        repair = self.repair(content)
        if self.plan_sha256 is not None and repair.audit.get("approved_plan_sha256") != self.plan_sha256:
            raise ValueError("LOCAL_RECOVERY_REPAIR_PLAN_CHANGED")
        identity = {"operation": "LOCAL_REJECTED_CAPTURE_DERIVATIVE_1",
            "command": capture.request.command_id, "capture": capture.request.result_sha256,
            "mapping": repair.audit["mapping_sha256"], "repair_operation": repair.audit["operation"],
            "approved_plan_sha256": self.plan_sha256}
        dispatch = object_data(as_plain(capture.dispatch))
        dispatch["production_ref"] = "prod:" + fingerprint({**identity, "identity": "production"})[:32]
        dispatch["version_ref"] = "ver:" + fingerprint({**identity, "identity": "version"})[:32]
        dispatch["lineage"] = {**object_data(dispatch["lineage"]), "parent_version_ref": None}
        bound, guard = self.validator.bind(dispatch, repair.content)
        # Existing binding may add a candidate label. That is not an ID-only repair.
        projected = {key: as_plain(bound.data[key]) for key in CONTENT_FIELDS}
        if projected != as_plain(repair.content):
            raise ValueError("LOCAL_RECOVERY_NON_ID_CHANGE_BY_BINDING")
        evidence = {str(key): str(value) for key, value in object_data(dispatch["evidence"]).items()}
        candidate = CreateP0Candidate().execute(bound.data, evidence=evidence)
        report = ValidateP0Command().execute(candidate)
        if report["status"] != "PASS":
            raise ValueError("LOCAL_RECOVERY_BUSINESS_VALIDATION_FAILED")
        provenance = {"RECOVERED_CAPTURE_SHA256": capture.request.result_sha256,
            "RECOVERED_COMMAND_SHA256": fingerprint(capture.request.command_id),
            "RECOVERED_REQUEST_SHA256": capture.request.request_sha256,
            "RECOVERED_ORIGINAL_DISPATCH_SHA256": fingerprint(capture.dispatch),
            "RECOVERED_SECTION_MAPPING_SHA256": str(repair.audit["mapping_sha256"])}
        if self.plan_sha256 is not None and self.adoption_sha256 is not None:
            provenance.update(RECOVERY_PLAN_SHA256=self.plan_sha256, RECOVERY_ADOPTION_SHA256=self.adoption_sha256)
        record = SavedProduction({"contract_id": "SAVED-PRODUCTION-P0-1.0",
            "bundle": as_plain(candidate.data), "view": as_plain(P0ProductionReadView.from_bundle(candidate).data),
            "reviews": [], "validations": [], "origin": "LOCAL_APPLICATION", "provenance": provenance,
            "reservations": ["RECOVERED_LOCAL_DERIVATIVE_PENDING_REVIEW", "PARSING_REJECTED_ORIGINAL_RETAINED",
                "CAPTURED_SOURCE_EVIDENCE_NOT_REVALIDATED", "PEDAGOGICAL_ACCEPTANCE_NOT_PERFORMED"]})
        audit = {**cast(dict[str, object], as_plain(repair.audit)), "derived_production_ref": record.production_ref,
            "derived_version_ref": record.version_ref, "record_sha256": record.sha256,
            "original_dispatch_sha256": fingerprint(capture.dispatch), "derived_dispatch_sha256": fingerprint(dispatch),
            "normal_guard": as_plain(guard), "business_validation": report,
            "source_evidence": "CAPTURED_CHECKSUMS_ONLY_NOT_FRESH_ADMISSION",
            "state": "RECOVERED_LOCAL_DERIVATIVE_PENDING_REVIEW", "publication": "NOT_PERFORMED"}
        return PreparedRecoveredCapture(record, freeze_safe_mapping(audit))
