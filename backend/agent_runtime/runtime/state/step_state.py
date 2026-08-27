from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_agent_safe_ref,
    require_agent_safe_text,
    require_contract_ref,
)
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant


class StepRuntimeStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


_NOT_STARTED_STATUSES = frozenset(
    {StepRuntimeStatus.PENDING, StepRuntimeStatus.READY}
)
_TERMINAL_STATUSES = frozenset(
    {
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.FAILED,
        StepRuntimeStatus.CANCELLED,
        StepRuntimeStatus.SKIPPED,
    }
)


@dataclass(frozen=True, slots=True)
class StepState:
    step_id: str
    status: StepRuntimeStatus
    parent_step_id: str | None = None
    context_slice_ref: ContractRef | None = None
    started_at: Instant | None = None
    ended_at: Instant | None = None
    attempt_count: int = 0
    result_refs: tuple[ContractRef, ...] = ()
    metrics: Mapping[str, object] = field(default_factory=dict)
    error_ref: ContractRef | None = None
    block_reason: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.step_id, "step_id")
        require_agent_safe_text(self.step_id, field_name="step_id", max_length=128)
        if not isinstance(self.status, StepRuntimeStatus):
            raise TypeError("status must be a StepRuntimeStatus")
        if self.parent_step_id is not None:
            require_non_empty(self.parent_step_id, "parent_step_id")
            require_agent_safe_text(
                self.parent_step_id, field_name="parent_step_id", max_length=128
            )
            if self.parent_step_id == self.step_id:
                raise ValueError("parent_step_id must differ from step_id")
        if self.context_slice_ref is not None:
            require_contract_ref(self.context_slice_ref, "context_slice_ref")
        if self.started_at is not None and not isinstance(self.started_at, Instant):
            raise TypeError("started_at must be an Instant or None")
        if self.ended_at is not None and not isinstance(self.ended_at, Instant):
            raise TypeError("ended_at must be an Instant or None")
        if (
            self.started_at is not None
            and self.ended_at is not None
            and self.ended_at.value < self.started_at.value
        ):
            raise ValueError("ended_at must be >= started_at")
        if type(self.attempt_count) is not int:
            raise TypeError("attempt_count must be an integer")
        if self.attempt_count < 0:
            raise ValueError("attempt_count must be >= 0")
        if not isinstance(self.result_refs, tuple):
            raise TypeError("result_refs must be a tuple")
        if len(self.result_refs) > 64:
            raise ValueError("result_refs must contain at most 64 items")
        for result_ref in self.result_refs:
            require_contract_ref(result_ref, "result_ref")
            require_agent_safe_ref(result_ref, field_name="result_ref")
        if self.error_ref is not None:
            require_contract_ref(self.error_ref, "error_ref")
            require_agent_safe_ref(self.error_ref, field_name="error_ref")
        if self.block_reason is not None:
            require_non_empty(self.block_reason, "block_reason")
            require_agent_safe_text(
                self.block_reason, field_name="block_reason", max_length=512
            )

        if self.status in _NOT_STARTED_STATUSES and (
            self.started_at is not None or self.ended_at is not None
        ):
            raise ValueError("pending and ready steps must not have timestamps")
        if self.status is StepRuntimeStatus.RUNNING and (
            self.started_at is None or self.ended_at is not None
        ):
            raise ValueError("running steps require started_at and forbid ended_at")
        if self.status in _TERMINAL_STATUSES and self.ended_at is None:
            raise ValueError("terminal steps require ended_at")
        if (
            self.status is StepRuntimeStatus.FAILED
            and self.error_ref is None
            and self.block_reason is None
        ):
            raise ValueError("failed steps require error_ref or block_reason")
        if self.status is StepRuntimeStatus.BLOCKED and self.block_reason is None:
            raise ValueError("blocked steps require block_reason")

        object.__setattr__(self, "metrics", freeze_agent_safe_mapping(self.metrics))
