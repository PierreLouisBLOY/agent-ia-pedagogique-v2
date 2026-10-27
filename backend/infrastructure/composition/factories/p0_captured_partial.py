"""Isolated readonly binding; reuses the adopted inspection composition."""
from datetime import UTC, datetime

from backend.adapters.inbound.application.p0_captured_partial import CapturedPartialInbound
from backend.adapters.outbound.persistence.p0_captured_partial_reader import P0CapturedPartialReader
from backend.infrastructure.composition.factories.p0_pilot_command_inspection import (
    P0PilotCommandInspectionComposition,
)
from backend.modules.work_orchestration.application.queries.read_captured_partial import (
    ReadCapturedPartial,
)
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import (
    CapturedPartialRequest,
)


def bind_captured_partial(inspection: P0PilotCommandInspectionComposition, *,
                         request: CapturedPartialRequest) -> CapturedPartialInbound:
    if (inspection.request.expected_plan_or_profile_sha256 != request.profile_sha256
            or inspection._command_id != request.command_id):
        raise ValueError("P0_CAPTURED_PARTIAL_COMPOSITION_CHANGED")
    reader = P0CapturedPartialReader(loader=inspection._validate, binding=request,
        clock=lambda: datetime.now(UTC))
    return CapturedPartialInbound(ReadCapturedPartial(reader, request))
