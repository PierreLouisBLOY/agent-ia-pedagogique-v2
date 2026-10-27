"""One bound readonly inspection; no recovery, bookkeeping or provider operation."""
from __future__ import annotations

from backend.core_contracts.outcome import (
    ApplicationFailure,
    ApplicationFailureKind,
    ApplicationOutcome,
    OutcomeStatus,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionPortError,
    P1CampaignInspectionReader,
    P1CampaignInspectionRequest,
    P1CampaignInspectionView,
)
from backend.shared_kernel._value_safety import require_safe_structured_value
from backend.shared_kernel.correlation import CorrelationId


class InspectP1Campaign:
    def __init__(self, reader: P1CampaignInspectionReader, *, inspection_ref: str, expected_plan_or_profile_sha256: str) -> None:
        self.reader = reader
        self.binding = P1CampaignInspectionRequest(inspection_ref, expected_plan_or_profile_sha256)

    def execute(self, *, request: P1CampaignInspectionRequest,
            correlation_id: CorrelationId) -> ApplicationOutcome[P1CampaignInspectionView, object]:
        if type(request) is not P1CampaignInspectionRequest or type(correlation_id) is not CorrelationId:
            raise ValueError("P1_INSPECTION_TYPED_ARGUMENTS")
        require_safe_structured_value(correlation_id, root_location="p1_inspection_correlation")
        if request != self.binding:
            return self._failure(ApplicationFailureKind.AF_MAPPING_CORRUPTION, correlation_id)
        try:
            raw = self.reader.inspect(inspection_ref=request.inspection_ref,
                expected_plan_or_profile_sha256=request.expected_plan_or_profile_sha256)
        except P1CampaignInspectionPortError as error:
            return self._failure(error.kind, correlation_id)
        except ValueError:
            return self._failure(ApplicationFailureKind.AF_MAPPING_CORRUPTION, correlation_id)
        except Exception:
            return self._failure(ApplicationFailureKind.AF_PORT_UNAVAILABLE, correlation_id)
        try:
            view = P1CampaignInspectionView.from_mapping(raw)
        except (TypeError, ValueError):
            return self._failure(ApplicationFailureKind.AF_MAPPING_CORRUPTION, correlation_id)
        return ApplicationOutcome(outcome_status=OutcomeStatus.SUCCESS, success=True,
            correlation_id=correlation_id, data=view, side_effects=())

    @staticmethod
    def _failure(kind: ApplicationFailureKind, correlation_id: CorrelationId) -> ApplicationOutcome[P1CampaignInspectionView, object]:
        unknown = kind is ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN
        return ApplicationOutcome(outcome_status=OutcomeStatus.INDETERMINATE if unknown else OutcomeStatus.FAILED,
            success=False, correlation_id=correlation_id,
            application_failure=ApplicationFailure(kind, message_key="P1_CAMPAIGN_INSPECTION_" + kind.value), side_effects=())
