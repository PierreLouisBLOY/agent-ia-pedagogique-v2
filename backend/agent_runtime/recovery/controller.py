from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.orchestration.coordination import (
    CoordinationDecision,
    OrchestrationCoordinator,
)
from backend.agent_runtime.recovery.budget import BudgetState
from backend.agent_runtime.recovery.coordinator import (
    RecoveryAction,
    RecoveryCoordinator,
    RecoveryDecisionResult,
)
from backend.agent_runtime.recovery.reconciliation import (
    EffectReconciliationResult,
)
from backend.agent_runtime.recovery.retry import RetryDecision
from backend.agent_runtime.recovery.snapshot import StateSnapshot
from backend.agent_runtime.runtime.execution import (
    ExecutionCycleResult,
    PlanExecutor,
)
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.state import RunState
from backend.shared_kernel.time import Instant


@dataclass(frozen=True, slots=True)
class RecoveryCycleResult:
    plan: Plan
    run_state: RunState
    execution_cycle: ExecutionCycleResult
    coordination_decision: CoordinationDecision
    recovery_action: RecoveryAction
    budget_state: BudgetState
    snapshot: StateSnapshot
    retry_decision: RetryDecision | None = None
    reconciliation_result: EffectReconciliationResult | None = None

    @classmethod
    def from_decision(
        cls,
        *,
        cycle: ExecutionCycleResult,
        decision: RecoveryDecisionResult,
    ) -> RecoveryCycleResult:
        return cls(
            plan=decision.plan,
            run_state=decision.run_state,
            execution_cycle=cycle,
            coordination_decision=decision.coordination_decision,
            recovery_action=decision.recovery_action,
            budget_state=decision.budget_state,
            snapshot=decision.snapshot,
            retry_decision=decision.retry_decision,
            reconciliation_result=decision.reconciliation_result,
        )


@dataclass(frozen=True, slots=True)
class RecoveryRuntimeController:
    """Exactly one execution, coordination, recovery decision, and checkpoint."""

    executor: PlanExecutor
    orchestration_coordinator: OrchestrationCoordinator
    recovery_coordinator: RecoveryCoordinator

    def __post_init__(self) -> None:
        if not isinstance(self.executor, PlanExecutor):
            raise TypeError("executor must be a PlanExecutor")
        if not isinstance(
            self.orchestration_coordinator, OrchestrationCoordinator
        ):
            raise TypeError(
                "orchestration_coordinator must be an OrchestrationCoordinator"
            )
        if not isinstance(self.recovery_coordinator, RecoveryCoordinator):
            raise TypeError("recovery_coordinator must be a RecoveryCoordinator")

    def execute_cycle(
        self,
        *,
        plan: Plan,
        run_state: RunState,
        now: Instant,
    ) -> RecoveryCycleResult:
        cycle = self.executor.execute_cycle(
            plan=plan,
            run_state=run_state,
            now=now,
        )
        coordination = self.orchestration_coordinator.coordinate(
            plan=plan,
            cycle=cycle,
            now=now,
        )
        recovery = self.recovery_coordinator.recover(
            plan=plan,
            coordination_decision=coordination,
            now=now,
        )
        return RecoveryCycleResult.from_decision(cycle=cycle, decision=recovery)
