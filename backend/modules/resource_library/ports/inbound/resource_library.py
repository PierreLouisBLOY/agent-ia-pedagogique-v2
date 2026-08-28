from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.core_contracts.outcome import ApplicationOutcome
from backend.modules.resource_library.application.dto.input import GetResourceRequest
from backend.modules.resource_library.application.dto.output import ResourceView
from backend.shared_kernel.correlation import CorrelationId


@runtime_checkable
class ResourceLibraryInbound(Protocol):
    """Canonical IP-03 slice for UC-RESOURCE / READ-15 getResource."""

    def get_resource(
        self,
        *,
        request: GetResourceRequest,
        correlation_id: CorrelationId,
    ) -> ApplicationOutcome[ResourceView, object]:
        ...
