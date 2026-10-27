"""Owner Application entry only; no HTTP or agent capability registration."""
from __future__ import annotations

from collections.abc import Mapping

from backend.core_contracts.outcome import ApplicationOutcome
from backend.modules.resource_library.application.commands.register_local_contribution import (
    RegisterLocalContribution,
)
from backend.modules.resource_library.application.queries.read_local_contribution import (
    ReadLocalContribution,
)
from backend.modules.resource_library.contracts.dto.local_contribution import (
    LocalContributionRead,
    LocalContributionRequest,
)
from backend.shared_kernel.correlation import CorrelationId


class LocalContributionInbound:
    def __init__(self, register: RegisterLocalContribution, reader: ReadLocalContribution) -> None:
        self._register, self._reader = register, reader

    def register(self, data: Mapping[str, object], *, correlation: str) -> ApplicationOutcome[object, object]:
        return self._register.execute(LocalContributionRequest(data), correlation=CorrelationId(correlation))

    def read(self, data: Mapping[str, object]) -> dict[str, object]:
        return self._reader.execute(LocalContributionRead(data))

    def inspect_operation(self, operation_key: str) -> Mapping[str, object]:
        return self._reader.inspect(operation_key)
