"""Application composition for the pilot same-need policy, permanently OFF."""
from __future__ import annotations

from collections.abc import Mapping

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.outbound.generation.openai.p0_pilot_same_need_off import (
    P0PilotSameNeedOffGeneration,
    PilotHistoricalObservationPort,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService


class P0PilotSameNeedOffComposition:
    def __init__(self, *, plan: Mapping[str, object], historical: PilotHistoricalObservationPort) -> None:
        self.generation = P0PilotSameNeedOffGeneration(plan=plan, historical=historical)

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        # A real original-LOCK observation is required before this Application
        # composition can be displayed as a bounded local pilot.
        self.generation.inspect()
        service.generation = self.generation
        endpoint.generation_bound = False
        endpoint.consent_execute = None
        endpoint.campaign_snapshot = self.generation.inspect

        def preview(payload: Mapping[str, object]) -> dict[str, object]:
            data = object_data(payload, {"command_id", "preparation_ref", "preparation_sha256"})
            ref, pin = data["preparation_ref"], data["preparation_sha256"]
            if (type(data["command_id"]) is not str or len(data["command_id"]) != 32
                or any(char not in "0123456789abcdef" for char in data["command_id"])
                or type(ref) is not str or not ref.startswith("prep:")
                or type(pin) is not str or len(pin) != 64):
                raise ValueError("P1_PILOT_OFF_PREVIEW_IDENTITY")
            request = service.prepared.get(ref)
            if request is None or fingerprint(request) != pin:
                raise ValueError("P0_PREPARATION_CHANGED")
            return self.generation.preview(request=request,
                preparation_ref=ref, preparation_sha256=pin)

        endpoint.pilot_preview_execute = preview
