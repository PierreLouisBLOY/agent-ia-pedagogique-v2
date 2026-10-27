"""Explicit local inspection boundary; not a recovery or effect command."""
from backend.modules.work_orchestration.application.queries.read_rejected_capture import (
    ReadRejectedCapture,
)
from backend.modules.work_orchestration.contracts.dto.rejected_capture import (
    RejectedCapture,
    RejectedCaptureRequest,
)


class RejectedCaptureInbound:
    def __init__(self, query: ReadRejectedCapture) -> None:
        self.query = query

    def read(self, request: RejectedCaptureRequest) -> RejectedCapture:
        return self.query.execute(request)
