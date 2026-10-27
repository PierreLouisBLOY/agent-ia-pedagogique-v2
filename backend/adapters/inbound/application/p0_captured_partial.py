"""Local Application entry point; no HTTP route or business-store authority."""
from backend.core_contracts.outcome import ApplicationOutcome
from backend.modules.work_orchestration.application.queries.read_captured_partial import (
    ReadCapturedPartial,
)
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import (
    CapturedPartial,
    CapturedPartialRequest,
)
from backend.shared_kernel.correlation import CorrelationId


class CapturedPartialInbound:
    def __init__(self, query: ReadCapturedPartial) -> None:
        self.query = query

    def read(self, *, request: CapturedPartialRequest,
             correlation_id: CorrelationId) -> ApplicationOutcome[CapturedPartial, object]:
        return self.query.execute(request=request, correlation_id=correlation_id)
