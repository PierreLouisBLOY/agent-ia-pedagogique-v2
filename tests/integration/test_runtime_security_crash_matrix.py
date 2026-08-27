from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts import ExecutorKind, StepKind, StepSpec
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    Plan,
    PlanExecutor,
    RunState,
    StepExecutionResult,
)
from backend.agent_runtime.runtime.execution import ExecutionDirectiveCode
from backend.agent_runtime.security.runtime_composition import (
    RuntimeSecurityAssessment,
    RuntimeSecurityDisposition,
    RuntimeSecurityFailureStage,
    RuntimeSecurityReasonCode,
    RuntimeSecurityViolation,
)
from backend.shared_kernel.time import Instant
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)


@dataclass(slots=True)
class PostEffectRejectingRunner:
    delegate: object
    stage: RuntimeSecurityFailureStage = RuntimeSecurityFailureStage.POST_EFFECT

    def run(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        if self.stage is RuntimeSecurityFailureStage.POST_EFFECT:
            result = self.delegate.run(
                plan=plan,
                step=step,
                run_state=run_state,
                attempt=attempt,
                now=now,
            )
            assert type(result) is StepExecutionResult
        raise RuntimeSecurityViolation(
            RuntimeSecurityAssessment(
                RuntimeSecurityDisposition.DENY,
                (RuntimeSecurityReasonCode.POST_RESULT_REJECTED,),
            ),
            stage=self.stage,
        )


def test_post_effect_security_rejection_never_claims_none_or_retries() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    harness = make_runtime_harness(step)
    runner = PostEffectRejectingRunner(harness.runner)

    result = PlanExecutor(
        DeterministicScheduler(), harness.guard, runner
    ).execute_cycle(
        plan=plan,
        run_state=make_run_state(plan, ready_step_id=step.step_id),
        now=NOW,
    )

    assert len(harness.tool_executor.calls) == 1
    assert result.completed_step_ids == ()
    assert result.directives[-1].code is ExecutionDirectiveCode.RECONCILIATION_REQUIRED
    assert (
        result.directives[-1].reason_code
        == "POST_EFFECT_SECURITY_REJECTION_EFFECT_UNKNOWN"
    )


def test_late_pre_effect_detection_restores_non_launched_state() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    harness = make_runtime_harness(step)
    runner = PostEffectRejectingRunner(
        harness.runner, RuntimeSecurityFailureStage.PRE_EFFECT
    )

    result = PlanExecutor(
        DeterministicScheduler(), harness.guard, runner
    ).execute_cycle(
        plan=plan,
        run_state=make_run_state(plan, ready_step_id=step.step_id),
        now=NOW,
    )

    assert harness.tool_executor.calls == []
    assert result.launched_step_ids == ()
    assert result.run_state.step_states[step.step_id].attempt_count == 0
    assert result.directives[0].code is ExecutionDirectiveCode.PRELAUNCH_DENIED
