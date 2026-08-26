from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.contracts import StepSpec
from backend.agent_runtime.runtime.execution import StepExecutionResult
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.routing.model import (
    ResolvedAgentInput,
    ResolvedGateInput,
    ResolvedToolInput,
    ResolvedUseCaseInput,
)
from backend.agent_runtime.runtime.state import RunState
from backend.shared_kernel.time import Instant


@runtime_checkable
class RuntimeRoutingResolverPort(Protocol):
    """Trusted, typed resolution only; implementations do not grant authority."""

    def resolve_use_case_input(
        self, *, plan: Plan, step: StepSpec, run_state: RunState
    ) -> ResolvedUseCaseInput: ...

    def resolve_tool_input(
        self, *, plan: Plan, step: StepSpec, run_state: RunState
    ) -> ResolvedToolInput: ...

    def resolve_gate_input(
        self, *, plan: Plan, step: StepSpec, run_state: RunState
    ) -> ResolvedGateInput: ...

    def resolve_agent_input(
        self, *, plan: Plan, step: StepSpec, run_state: RunState
    ) -> ResolvedAgentInput: ...


@runtime_checkable
class AgentStepExecutionPort(Protocol):
    def execute(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult: ...


@runtime_checkable
class RuntimeControlStepRunnerPort(Protocol):
    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult: ...
