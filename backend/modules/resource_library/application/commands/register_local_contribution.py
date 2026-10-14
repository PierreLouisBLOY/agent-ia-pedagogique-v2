"""One explicitly admitted local contribution; identifiers are allocated here only."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import uuid4

from backend.core_contracts.outcome import (
    ApplicationFailure,
    ApplicationFailureKind,
    ApplicationOutcome,
    OutcomeStatus,
)
from backend.modules.documents_provenance.contracts.dto.local_contribution_provenance import (
    LocalContributionProvenance,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.resource_library.contracts.dto.local_contribution import (
    LocalContributionAuthority,
    LocalContributionRecord,
    LocalContributionRequest,
    reference_snapshot,
)
from backend.modules.resource_library.ports.outbound.local_contribution_store import (
    LocalContributionPersistenceError,
    LocalContributionStorePort,
)
from backend.shared_kernel.correlation import CorrelationId


class RegisterLocalContribution:
    def __init__(self, store: LocalContributionStorePort, *, authority: LocalContributionAuthority,
                 provenance: LocalContributionProvenance, reference_reader: Callable[[str], Mapping[str, object]],
                 enabled: bool = False) -> None:
        if type(enabled) is not bool:
            raise ValueError("LOCAL_CONTRIBUTION_ENABLED_BOOL")
        self.store, self.authority, self.provenance = store, authority, provenance
        self.reference_reader, self.enabled = reference_reader, enabled
        for key in ("draft_origin_sha256", "local_admission_decision_sha256", "operation_authorization_sha256", "local_context_sha256"):
            if authority.data[key] != provenance.data[key]:
                raise ValueError("LOCAL_CONTRIBUTION_PROVENANCE_BINDING")

    def execute(self, request: LocalContributionRequest, *, correlation: CorrelationId) -> ApplicationOutcome[object, object]:
        if not self.enabled:
            raise ValueError("LOCAL_CONTRIBUTION_DISABLED")
        if type(request) is not LocalContributionRequest:
            raise ValueError("LOCAL_CONTRIBUTION_TYPED_REQUEST")
        for key in ("text_sha256", "utf8_bytes", "local_context_sha256"):
            if request.data[key] != self.authority.data[key]:
                raise ValueError("LOCAL_CONTRIBUTION_OUTSIDE_ADMISSION")
        expected = {key: self.authority.data[key] for key in ("target_ref", "target_binding_sha256", "operator_profile_sha256")}
        expected["binding_sha256"] = self.authority.sha256
        if dict(self.store.attest()) != expected:
            raise ValueError("LOCAL_CONTRIBUTION_TARGET_CHANGED")
        ref = reference_snapshot(self.reference_reader(str(request.data["notion_ref"])),
            request.data["notion_ref"], request.data["local_context_sha256"])
        try:
            with self.store.session(create=True):
                return self._execute_locked(request, ref, correlation)
        except LocalContributionPersistenceError as error:
            return ApplicationOutcome(outcome_status=OutcomeStatus.INDETERMINATE if error.uncertain else OutcomeStatus.FAILED,
                success=False, correlation_id=correlation,
                application_failure=ApplicationFailure(ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN if error.uncertain else ApplicationFailureKind.AF_PERSISTENCE,
                    message_key=error.code), side_effects=({"effect_state": "UNKNOWN" if error.uncertain else "NONE",
                        "original_mutations": False, "reconciliation_required": error.uncertain},))

    def _execute_locked(self, request: LocalContributionRequest, ref: Mapping[str, object], correlation: CorrelationId) -> ApplicationOutcome[object, object]:
        prior = object_data(self.store.inspect_operation(request.sha256, self.authority.sha256))
        if prior["state"] == "COMMITTED":
            record = LocalContributionRecord(object_data(prior["record"]))
            if record.data["operation_key"] != request.sha256 or record.data["binding_sha256"] != self.authority.sha256:
                raise ValueError("LOCAL_CONTRIBUTION_RECONCILE_REQUIRED")
            if (any(record.data[key] != request.data[key] for key in ("text", "utf8_bytes", "text_sha256", "title", "notion_ref"))
                    or record.as_dict()["provenance"] != self.provenance.as_dict()
                    or record.data["target_binding_sha256"] != self.authority.data["target_binding_sha256"]):
                raise ValueError("LOCAL_CONTRIBUTION_RECONCILE_REQUIRED")
            return self._success(record, correlation, replay=True)
        if prior["state"] != "ABSENT":
            # No new contribution is allocated, but the historical graph is uncertain.
            raise LocalContributionPersistenceError("LOCAL_CONTRIBUTION_RECONCILE_REQUIRED", uncertain=True)
        ids = {key: prefix + ":" + uuid4().hex for key, prefix in (("object_ref", "local-content"),
            ("version_ref", "local-version"), ("passage_ref", "local-passage"), ("provenance_ref", "local-provenance"))}
        record = LocalContributionRecord({"contract_id": "LOCAL-CONTRIBUTION-RECORD-1.0", **ids,
            **{key: request.data[key] for key in ("text", "utf8_bytes", "text_sha256", "title", "notion_ref")},
            "operation_key": request.sha256, "binding_sha256": self.authority.sha256,
            "target_binding_sha256": self.authority.data["target_binding_sha256"],
            "created_at": datetime.now(UTC).isoformat(), "provenance": self.provenance.as_dict(), "reference_snapshot": ref})
        intention = {"contract_id": "LOCAL-CONTRIBUTION-INTENT-1.0", "operation_key": request.sha256,
            "binding_sha256": self.authority.sha256, "record_sha256": record.sha256, "record": record.as_dict()}
        observed = self.store.append(record, intention)
        if observed.sha256 != record.sha256:
            raise LocalContributionPersistenceError("LOCAL_CONTRIBUTION_POSTCOMMIT_MISMATCH", uncertain=True)
        return self._success(observed, correlation, replay=False)

    @staticmethod
    def _success(record: LocalContributionRecord, correlation: CorrelationId, *, replay: bool) -> ApplicationOutcome[object, object]:
        return ApplicationOutcome(outcome_status=OutcomeStatus.SUCCESS, success=True, correlation_id=correlation,
            data={"state": "ALREADY_STORED" if replay else "STORED", "record": record.as_dict(),
                "record_sha256": record.sha256, "projection": record.source_snapshot(), "teacher_acceptance": "NOT_PERFORMED"},
            side_effects=({"effect_state": "COMMITTED", "already_confirmed": replay, "new_effect": not replay,
                "original_mutations": False, "provider_calls": 0},))
