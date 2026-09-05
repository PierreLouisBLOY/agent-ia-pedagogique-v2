from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.core_contracts.outcome import ApplicationOutcome
from backend.modules.resource_library.application.dto.input.search_local import SearchLocalRequest
from backend.modules.resource_library.application.dto.output.local_search_view import (
    LocalSearchView,
)
from backend.shared_kernel.correlation import CorrelationId


@runtime_checkable
class LocalSearchInbound(Protocol):
    def search_local(
        self, *, request: SearchLocalRequest, correlation_id: CorrelationId,
    ) -> ApplicationOutcome[LocalSearchView, object]: ...
