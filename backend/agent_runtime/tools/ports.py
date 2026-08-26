from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from backend.agent_runtime.tools.model import PreparedToolExecution, ToolExecutionOutcome
from backend.shared_kernel._strings import require_non_empty


@runtime_checkable
class ToolExecutorPort(Protocol):
    def execute(
        self,
        *,
        execution: PreparedToolExecution,
    ) -> ToolExecutionOutcome:
        ...


@dataclass(frozen=True, slots=True)
class ToolExecutorBinding:
    tool_id: str
    executor: ToolExecutorPort

    def __post_init__(self) -> None:
        require_non_empty(self.tool_id, "tool_id")
        if not isinstance(self.executor, ToolExecutorPort):
            raise TypeError("executor must implement ToolExecutorPort")


class UnknownToolExecutorBindingError(LookupError):
    def __init__(self, tool_id: str) -> None:
        require_non_empty(tool_id, "tool_id")
        self.tool_id = tool_id
        super().__init__("unknown tool executor binding")


@dataclass(frozen=True, slots=True)
class ToolExecutorBindings:
    _bindings: tuple[ToolExecutorBinding, ...]
    _by_tool_id: MappingProxyType[str, ToolExecutorPort]

    def __init__(self, bindings: Iterable[ToolExecutorBinding]) -> None:
        normalized = tuple(bindings)
        if any(type(binding) is not ToolExecutorBinding for binding in normalized):
            raise TypeError("bindings must contain ToolExecutorBinding values")
        tool_ids = tuple(binding.tool_id for binding in normalized)
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("duplicate tool executor binding")
        object.__setattr__(self, "_bindings", normalized)
        object.__setattr__(
            self,
            "_by_tool_id",
            MappingProxyType(
                {binding.tool_id: binding.executor for binding in normalized}
            ),
        )

    def get(self, tool_id: str) -> ToolExecutorPort:
        require_non_empty(tool_id, "tool_id")
        try:
            return self._by_tool_id[tool_id]
        except KeyError as error:
            raise UnknownToolExecutorBindingError(tool_id) from error

    def contains(self, tool_id: str) -> bool:
        require_non_empty(tool_id, "tool_id")
        return tool_id in self._by_tool_id

    def all(self) -> tuple[ToolExecutorBinding, ...]:
        return self._bindings
