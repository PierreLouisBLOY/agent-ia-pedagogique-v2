"""Application inbound for bound readonly inspection; no agent route or authority."""
from __future__ import annotations

from collections.abc import Mapping

from backend.core_contracts.outcome import ApplicationOutcome
from backend.modules.work_orchestration.application.queries.inspect_p1_campaign import (
    InspectP1Campaign,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionRequest,
    P1CampaignInspectionView,
)
from backend.shared_kernel.correlation import CorrelationId


class P1CampaignInspectionInbound:
    def __init__(self, query: InspectP1Campaign) -> None:
        self.query = query

    def inspect(self, *, request: P1CampaignInspectionRequest | Mapping[str, object],
            correlation_id: CorrelationId) -> ApplicationOutcome[P1CampaignInspectionView, object]:
        if isinstance(request, P1CampaignInspectionRequest):
            if type(request) is not P1CampaignInspectionRequest:
                raise ValueError("P1_INSPECTION_TYPED_ARGUMENTS")
            typed = request
        elif isinstance(request, Mapping):
            typed = P1CampaignInspectionRequest.from_mapping(request)
        else:
            raise ValueError("P1_INSPECTION_TYPED_ARGUMENTS")
        return self.query.execute(request=typed, correlation_id=correlation_id)
