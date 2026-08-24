from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.shared_kernel._safe_data import freeze_safe_mapping
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.references import TypedEntityRef


@dataclass(frozen=True, slots=True)
class UseCaseContext:
    """Transport-neutral context accompanying an application use-case call."""

    correlation_id: CorrelationId
    session_ref: TypedEntityRef | None = None
    task_ref: TypedEntityRef | None = None
    pedagogical_context_ref: TypedEntityRef | None = None
    context_snapshot: Mapping[str, object] | None = None
    operation_ref: TypedEntityRef | None = None
    actor_ref: TypedEntityRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")
        if self.context_snapshot is not None:
            object.__setattr__(
                self,
                "context_snapshot",
                freeze_safe_mapping(self.context_snapshot),
            )
