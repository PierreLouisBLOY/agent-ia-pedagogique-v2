"""Application-owned CAP-R02 typed read boundary."""
from typing import Protocol, runtime_checkable

from backend.core_contracts.outcome import ApplicationOutcome
from backend.modules.work_orchestration.application.dto.input.read_production import (
    ReadProductionRequest,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.shared_kernel.correlation import CorrelationId


@runtime_checkable
class ProductionReadInbound(Protocol):
    def execute(self, request: ReadProductionRequest, *, conversation_id: str,
                correlation_id: CorrelationId) -> ApplicationOutcome[ProductionReadView, object]: ...
