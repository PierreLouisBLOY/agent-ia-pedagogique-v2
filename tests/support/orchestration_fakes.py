from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.agent_runtime.contracts import StepSpec
from backend.agent_runtime.orchestration import (
    CoordinationAction,
    CoordinationDecision,
    OrchestrationCoordinator,
    WorkflowCompletionDecision,
)
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    ExecutionCycleResult,
    Plan,
    PlanExecutor,
    PreLaunchDecision,
    PreLaunchDisposition,
    RunState,
    StepExecutionResult,
    StepRuntimeStatus,
)
from backend.shared_kernel.time import Instant


class FakePreLaunchGuard:
    """Deterministic test-only guard with explicit per-step dispositions."""

    def __init__(
        self,
        dispositions: Mapping[str, PreLaunchDisposition] | None = None,
    ) -> None:
        self.dispositions = dict(dispositions or {})
        self.calls: list[str] = []

    def check(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision:
        del plan, run_state, now
        self.calls.append(step.step_id)
        disposition = self.dispositions.get(step.step_id, PreLaunchDisposition.ALLOW)
        if disposition is PreLaunchDisposition.ALLOW:
            return PreLaunchDecision(disposition)
        return PreLaunchDecision(
            disposition,
            f"FAKE_{disposition.value}_{step.step_id}",
        )


class RecordingStepRunner:
    """Side-effect-free test runner returning configured technical results."""

    def __init__(
        self,
        results: Mapping[str, StepExecutionResult] | None = None,
    ) -> None:
        self.results = dict(results or {})
        self.calls: list[tuple[str, int]] = []

    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        del plan, run_state, now
        self.calls.append((step.step_id, attempt))
        return self.results.get(
            step.step_id,
            StepExecutionResult(
                status=StepRuntimeStatus.SUCCEEDED,
                result_refs=(f"result-{step.step_id}",),
            ),
        )


class FakeWorkflowCompletionEvaluator:
    """Test-only completion port with no success-criteria interpretation."""

    def __init__(self, decision: WorkflowCompletionDecision) -> None:
        if not isinstance(decision, WorkflowCompletionDecision):
            raise TypeError("decision must be a WorkflowCompletionDecision")
        self.decision = decision
        self.calls: list[tuple[Plan, RunState]] = []

    def evaluate(
        self,
        *,
        plan: Plan,
        run_state: RunState,
    ) -> WorkflowCompletionDecision:
        self.calls.append((plan, run_state))
        return self.decision


@dataclass(frozen=True, slots=True)
class HarnessCycleResult:
    cycle: ExecutionCycleResult
    decision: CoordinationDecision


def execute_and_coordinate_once(
    *,
    plan: Plan,
    run_state: RunState,
    now: Instant,
    guard: FakePreLaunchGuard,
    runner: RecordingStepRunner,
    completion_evaluator: FakeWorkflowCompletionEvaluator,
) -> HarnessCycleResult:
    executor = PlanExecutor(
        scheduler=DeterministicScheduler(),
        prelaunch_guard=guard,
        runner=runner,
    )
    cycle = executor.execute_cycle(plan=plan, run_state=run_state, now=now)
    decision = OrchestrationCoordinator(completion_evaluator).coordinate(
        plan=plan,
        cycle=cycle,
        now=now,
    )
    return HarnessCycleResult(cycle, decision)


def run_until_decisive(
    *,
    plan: Plan,
    run_state: RunState,
    now: Instant,
    guard: FakePreLaunchGuard,
    runner: RecordingStepRunner,
    completion_evaluator: FakeWorkflowCompletionEvaluator,
    max_cycles: int = 32,
) -> tuple[HarnessCycleResult, ...]:
    """Explicitly bounded test harness; production owns no orchestration loop."""
    if type(max_cycles) is not int or max_cycles < 1:
        raise ValueError("max_cycles must be a positive integer")
    results: list[HarnessCycleResult] = []
    current = run_state
    for _ in range(max_cycles):
        result = execute_and_coordinate_once(
            plan=plan,
            run_state=current,
            now=now,
            guard=guard,
            runner=runner,
            completion_evaluator=completion_evaluator,
        )
        results.append(result)
        if result.decision.action is not CoordinationAction.CONTINUE:
            return tuple(results)
        current = result.decision.run_state
    raise AssertionError("bounded orchestration harness exhausted max_cycles")
