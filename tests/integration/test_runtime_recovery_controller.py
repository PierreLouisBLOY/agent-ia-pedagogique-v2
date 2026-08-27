from __future__ import annotations

from backend.agent_runtime.application_routing import BASELINE_USE_CASE_REGISTRY
from backend.agent_runtime.contracts import ExecutorKind, StepKind, WorkflowStatus
from backend.agent_runtime.orchestration.coordination import (
    CompletionDisposition,
    OrchestrationCoordinator,
    WorkflowCompletionDecision,
)
from backend.agent_runtime.recovery import (
    BudgetState,
    CircuitBreakerEngine,
    EffectiveBudgetLimits,
    EffectReconciliationEngine,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    RecoveryAction,
    RecoveryAwareStepRunner,
    RecoveryCoordinator,
    RecoveryPreLaunchGuard,
    RecoveryRuntimeController,
    resolve_recovery_execution_context,
)
from backend.agent_runtime.registry import BASELINE_TOOL_REGISTRY
from backend.agent_runtime.runtime import DeterministicScheduler, PlanExecutor
from tests.support.budget_state_fakes import InMemoryBudgetStatePort
from tests.support.circuit_breaker_fakes import (
    CONFIG,
    InMemoryCircuitBreakerStore,
)
from tests.support.effect_ledger_fakes import InMemoryEffectLedgerFake
from tests.support.orchestration_fakes import FakeWorkflowCompletionEvaluator
from tests.support.reconciliation_fakes import (
    RecordingApplicationEffectProbe,
    RecordingToolEffectProbe,
)
from tests.support.runtime_recovery_fakes import (
    PortBackedRecoveryReferenceResolver,
    RecordingRecoveryRuntimeResolver,
)
from tests.support.runtime_routing_fakes import (
    NOW,
    make_plan,
    make_run_state,
    make_runtime_harness,
    make_step,
)
from tests.support.snapshot_store_fakes import InMemoryStateSnapshotStore


def test_controller_composes_exactly_one_successful_runtime_cycle() -> None:
    step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    plan = make_plan(step)
    run_state = make_run_state(plan, ready_step_id=step.step_id)
    harness = make_runtime_harness(step)
    resolver = RecordingRecoveryRuntimeResolver()
    context = resolve_recovery_execution_context(
        plan=plan,
        step=step,
        run_state=run_state,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    assert context.identity is not None
    ledger = InMemoryEffectLedgerFake()
    budget = BudgetState(
        run_id=plan.run_id,
        version=1,
        limits=EffectiveBudgetLimits(max_retries_per_step=2),
        created_at=NOW,
        updated_at=NOW,
    )
    budget_port = InMemoryBudgetStatePort(budget)
    snapshot_store = InMemoryStateSnapshotStore()
    circuit_store = InMemoryCircuitBreakerStore()
    circuit_engine = CircuitBreakerEngine(circuit_store, CONFIG)
    prelaunch = RecoveryPreLaunchGuard(
        inner=harness.guard,
        recovery_resolver=resolver,
        circuit_engine=circuit_engine,
        snapshot_store=snapshot_store,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    runner = RecoveryAwareStepRunner(
        inner=harness.runner,
        recovery_resolver=resolver,
        ledger=ledger,
        budget_port=budget_port,
        circuit_engine=circuit_engine,
        snapshot_store=snapshot_store,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    observation = ReconciliationObservation(
        record_id=context.identity.record_id,
        record_version=1,
        attempt=1,
        disposition=ReconciliationObservationDisposition.STILL_UNKNOWN,
        observed_result_refs=(),
        observed_at=NOW,
    )
    references = PortBackedRecoveryReferenceResolver(
        ledger=ledger,
        circuit_store=circuit_store,
        record_ids=(context.identity.record_id,),
        circuit_ids=(context.circuit_key.circuit_id,),
    )
    recovery_coordinator = RecoveryCoordinator(
        authority_guard=harness.guard,
        routing_resolver=harness.resolver,
        recovery_resolver=resolver,
        reference_resolver=references,
        ledger=ledger,
        budget_port=budget_port,
        snapshot_store=snapshot_store,
        reconciliation_engine=EffectReconciliationEngine(
            ledger,
            RecordingToolEffectProbe(observation),
            RecordingApplicationEffectProbe(observation),
        ),
        circuit_engine=circuit_engine,
        tool_registry=BASELINE_TOOL_REGISTRY,
        use_case_registry=BASELINE_USE_CASE_REGISTRY,
    )
    controller = RecoveryRuntimeController(
        executor=PlanExecutor(
            scheduler=DeterministicScheduler(),
            prelaunch_guard=prelaunch,
            runner=runner,
        ),
        orchestration_coordinator=OrchestrationCoordinator(
            FakeWorkflowCompletionEvaluator(
                WorkflowCompletionDecision(
                    CompletionDisposition.SUCCEEDED,
                    "WORKFLOW_COMPLETE",
                )
            )
        ),
        recovery_coordinator=recovery_coordinator,
    )

    result = controller.execute_cycle(plan=plan, run_state=run_state, now=NOW)
    record = ledger.get(record_id=context.identity.record_id)

    assert result.run_state.status is WorkflowStatus.SUCCEEDED
    assert result.recovery_action is RecoveryAction.NO_ACTION
    assert result.execution_cycle.launched_step_ids == (step.step_id,)
    assert len(harness.tool_executor.calls) == 1
    assert record is not None
    assert result.snapshot.effect_ledger_refs[0].version == record.version
    assert result.snapshot.recovery_checkpoint is None
