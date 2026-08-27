from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from backend.agent_runtime.contracts import ErrorEnvelope, StepSpec
from backend.agent_runtime.contracts.common import (
    ContractRef,
    freeze_agent_safe_mapping,
    require_agent_safe_ref,
    require_contract_ref,
)
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus
from backend.shared_kernel.time import Instant

_RUNNER_RESULT_STATUSES = frozenset(
    {
        StepRuntimeStatus.SUCCEEDED,
        StepRuntimeStatus.PARTIAL,
        StepRuntimeStatus.FAILED,
        StepRuntimeStatus.CANCELLED,
    }
)


@dataclass(frozen=True, slots=True)
class StepExecutionResult:
    status: StepRuntimeStatus
    result_refs: tuple[ContractRef, ...] = ()
    metrics: Mapping[str, object] = field(default_factory=dict)
    error: ErrorEnvelope | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, StepRuntimeStatus):
            raise TypeError("status must be a StepRuntimeStatus")
        if self.status not in _RUNNER_RESULT_STATUSES:
            raise ValueError("status must be a terminal runner result status")
        result_refs = tuple(self.result_refs)
        if len(result_refs) > 64:
            raise ValueError("result_refs must contain at most 64 items")
        for result_ref in result_refs:
            require_contract_ref(result_ref, "result_ref")
            require_agent_safe_ref(result_ref, field_name="result_ref")
        if self.error is not None and not isinstance(self.error, ErrorEnvelope):
            raise TypeError("error must be an ErrorEnvelope or None")
        if self.status is StepRuntimeStatus.SUCCEEDED and self.error is not None:
            raise ValueError("SUCCEEDED must not have an error")
        if self.status is StepRuntimeStatus.FAILED and self.error is None:
            raise ValueError("FAILED requires an error")
        object.__setattr__(self, "result_refs", result_refs)
        object.__setattr__(self, "metrics", freeze_agent_safe_mapping(self.metrics))


@runtime_checkable
class StepRunner(Protocol):
    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult: ...
