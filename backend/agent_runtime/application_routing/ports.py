from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from backend.agent_runtime.contracts import UseCaseRequest, UseCaseResult
from backend.shared_kernel._strings import require_non_empty


@runtime_checkable
class ApplicationInboundPort(Protocol):
    def invoke(
        self,
        *,
        request: UseCaseRequest,
    ) -> UseCaseResult[object, object]:
        ...


@dataclass(frozen=True, slots=True)
class UseCaseInboundBinding:
    use_case_id: str
    inbound: ApplicationInboundPort

    def __post_init__(self) -> None:
        require_non_empty(self.use_case_id, "use_case_id")
        if not isinstance(self.inbound, ApplicationInboundPort):
            raise TypeError("inbound must implement ApplicationInboundPort")


class UnknownUseCaseInboundBindingError(LookupError):
    def __init__(self, use_case_id: str) -> None:
        require_non_empty(use_case_id, "use_case_id")
        self.use_case_id = use_case_id
        super().__init__("unknown use-case inbound binding")


@dataclass(frozen=True, slots=True)
class UseCaseInboundBindings:
    _bindings: tuple[UseCaseInboundBinding, ...]
    _by_use_case_id: MappingProxyType[str, ApplicationInboundPort]

    def __init__(self, bindings: Iterable[UseCaseInboundBinding]) -> None:
        normalized = tuple(bindings)
        if any(type(binding) is not UseCaseInboundBinding for binding in normalized):
            raise TypeError("bindings must contain UseCaseInboundBinding values")
        use_case_ids = tuple(binding.use_case_id for binding in normalized)
        if len(use_case_ids) != len(set(use_case_ids)):
            raise ValueError("duplicate use-case inbound binding")
        object.__setattr__(self, "_bindings", normalized)
        object.__setattr__(
            self,
            "_by_use_case_id",
            MappingProxyType(
                {binding.use_case_id: binding.inbound for binding in normalized}
            ),
        )

    def get(self, use_case_id: str) -> ApplicationInboundPort:
        require_non_empty(use_case_id, "use_case_id")
        try:
            return self._by_use_case_id[use_case_id]
        except KeyError as error:
            raise UnknownUseCaseInboundBindingError(use_case_id) from error

    def contains(self, use_case_id: str) -> bool:
        require_non_empty(use_case_id, "use_case_id")
        return use_case_id in self._by_use_case_id

    def all(self) -> tuple[UseCaseInboundBinding, ...]:
        return self._bindings
