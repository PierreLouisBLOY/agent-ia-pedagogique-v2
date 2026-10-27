"""One explicitly bound partial capture, without restoration of execution rights."""
from backend.core_contracts.outcome import (
    ApplicationFailure,
    ApplicationFailureKind,
    ApplicationOutcome,
    OutcomeStatus,
)
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import (
    CapturedPartial,
    CapturedPartialReader,
    CapturedPartialRequest,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionPortError,
)
from backend.shared_kernel.correlation import CorrelationId


class ReadCapturedPartial:
    def __init__(self, reader: CapturedPartialReader, binding: CapturedPartialRequest) -> None:
        self.reader, self.binding = reader, binding

    def execute(self, *, request: CapturedPartialRequest,
                correlation_id: CorrelationId) -> ApplicationOutcome[CapturedPartial, object]:
        if type(request) is not CapturedPartialRequest or type(correlation_id) is not CorrelationId:
            raise ValueError("P0_CAPTURED_PARTIAL_TYPED_ARGUMENTS")
        kind = ApplicationFailureKind.AF_MAPPING_CORRUPTION
        if request == self.binding:
            try:
                capture = self.reader.read(request)
                if type(capture) is not CapturedPartial or capture.request != request:
                    raise ValueError("P0_CAPTURED_PARTIAL_BINDING")
                return ApplicationOutcome(outcome_status=OutcomeStatus.SUCCESS, success=True,
                    correlation_id=correlation_id, data=capture)
            except P1CampaignInspectionPortError as error:
                kind = error.kind
            except (ValueError, TypeError):
                pass
            except Exception:
                kind = ApplicationFailureKind.AF_PORT_UNAVAILABLE
        return ApplicationOutcome(outcome_status=OutcomeStatus.FAILED, success=False,
            correlation_id=correlation_id, application_failure=ApplicationFailure(kind,
                message_key="P0_CAPTURED_PARTIAL_" + kind.value))
