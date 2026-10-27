"""Application-only bounded inspection, without admission or persistence."""
from backend.modules.work_orchestration.contracts.dto.rejected_capture import (
    RejectedCapture,
    RejectedCaptureReader,
    RejectedCaptureRequest,
)


class ReadRejectedCapture:
    def __init__(self, reader: RejectedCaptureReader, binding: RejectedCaptureRequest) -> None:
        self.reader, self.binding = reader, binding

    def execute(self, request: RejectedCaptureRequest) -> RejectedCapture:
        if type(request) is not RejectedCaptureRequest or request != self.binding:
            raise ValueError("REJECTED_CAPTURE_APPLICATION_SCOPE")
        result = self.reader.read(request)
        if type(result) is not RejectedCapture or result.request != request:
            raise ValueError("REJECTED_CAPTURE_APPLICATION_BINDING")
        return result
