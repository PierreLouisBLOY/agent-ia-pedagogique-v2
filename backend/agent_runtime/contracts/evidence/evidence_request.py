from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.agent_runtime.contracts.common import ContractMeta, freeze_agent_safe_mapping
from backend.agent_runtime.contracts.invocation import InvocationStatus
from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class EvidenceRequest:
    """Declarative evidence-search intent; it performs no retrieval."""

    meta: ContractMeta[InvocationStatus]
    search_goal: str
    scope: Mapping[str, object] = field(default_factory=dict)
    source_policy: Mapping[str, object] = field(default_factory=dict)
    filters: Mapping[str, object] = field(default_factory=dict)
    required_authority: Mapping[str, object] | None = None
    max_items: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.meta, ContractMeta):
            raise TypeError("meta must be a ContractMeta")
        if not isinstance(self.meta.status, InvocationStatus):
            raise TypeError("meta.status must be an InvocationStatus")
        require_non_empty(self.search_goal, "search_goal")
        if self.max_items is not None:
            if not isinstance(self.max_items, int) or isinstance(self.max_items, bool):
                raise TypeError("max_items must be an integer")
            if self.max_items < 0:
                raise ValueError("max_items must be >= 0")
        object.__setattr__(self, "scope", freeze_agent_safe_mapping(self.scope))
        object.__setattr__(
            self, "source_policy", freeze_agent_safe_mapping(self.source_policy)
        )
        object.__setattr__(self, "filters", freeze_agent_safe_mapping(self.filters))
        if self.required_authority is not None:
            object.__setattr__(
                self,
                "required_authority",
                freeze_agent_safe_mapping(self.required_authority),
            )
