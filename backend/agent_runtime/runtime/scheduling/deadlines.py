from __future__ import annotations

from datetime import timedelta

from backend.agent_runtime.contracts import StepSpec
from backend.agent_runtime.policy import (
    BASELINE_AGENT_RUNTIME_POLICY,
    AgentRuntimePolicy,
)
from backend.agent_runtime.runtime.state import StepRuntimeStatus, StepState
from backend.shared_kernel.time import Instant


def effective_step_deadline(
    step: StepSpec,
    step_state: StepState,
    runtime_policy: AgentRuntimePolicy = BASELINE_AGENT_RUNTIME_POLICY,
) -> Instant:
    """Return the earliest absolute, step-budget, or default running deadline."""
    if not isinstance(step, StepSpec):
        raise TypeError("step must be a StepSpec")
    if not isinstance(step_state, StepState):
        raise TypeError("step_state must be a StepState")
    if not isinstance(runtime_policy, AgentRuntimePolicy):
        raise TypeError("runtime_policy must be an AgentRuntimePolicy")
    if step.step_id != step_state.step_id:
        raise ValueError("step.step_id must match step_state.step_id")
    if step_state.status is not StepRuntimeStatus.RUNNING:
        raise ValueError("step_state must be RUNNING")
    if step_state.started_at is None:
        raise ValueError("running step_state requires started_at")

    candidates = [
        Instant(
            step_state.started_at.value
            + timedelta(seconds=runtime_policy.step_deadline_default_seconds)
        )
    ]
    if step.budget is not None:
        if step.budget.deadline is not None:
            candidates.append(step.budget.deadline)
        if step.budget.max_runtime_seconds is not None:
            candidates.append(
                Instant(
                    step_state.started_at.value
                    + timedelta(seconds=step.budget.max_runtime_seconds)
                )
            )
    return min(candidates, key=lambda item: item.value)
