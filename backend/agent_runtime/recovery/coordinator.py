from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from backend.agent_runtime.application_routing import UseCaseRegistry
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    EffectState,
    StepSpec,
)
from backend.agent_runtime.orchestration.coordination import (
    CoordinationAction,
    CoordinationDecision,
)
from backend.agent_runtime.recovery.budget import (
    BudgetAccountingPolicy,
    BudgetCheckDisposition,
    BudgetState,
)
from backend.agent_runtime.recovery.budget_ports import BudgetStatePort
from backend.agent_runtime.recovery.checkpoint import (
    RecoveryCheckpoint,
    RecoveryCheckpointAction,
)
from backend.agent_runtime.recovery.circuit_breaker import (
    CircuitCheckRequest,
    CircuitPreflightDisposition,
)
from backend.agent_runtime.recovery.circuit_breaker_engine import CircuitBreakerEngine
from backend.agent_runtime.recovery.idempotency import IdempotencyPolicy
from backend.agent_runtime.recovery.model import (
    EffectLedgerLifecycle,
    EffectLedgerRecord,
)
from backend.agent_runtime.recovery.ports import EffectLedgerPort
from backend.agent_runtime.recovery.reconciliation import (
    EffectReconciliationDisposition,
    EffectReconciliationRequest,
    EffectReconciliationResult,
)
from backend.agent_runtime.recovery.reconciliation_engine import (
    EffectReconciliationEngine,
)
from backend.agent_runtime.recovery.replay import (
    AuthorityRevalidationStatus,
    DeadlineRevalidationStatus,
    ReplayGuard,
    ReplayPreconditions,
    SecurityRevalidationStatus,
    SnapshotRevalidationStatus,
)
from backend.agent_runtime.recovery.retry import (
    RetryDecision,
    RetryDisposition,
    RetryPolicy,
    RetryPolicyRequest,
)
from backend.agent_runtime.recovery.runtime_integration import (
    RecoveryExecutionContext,
    RecoveryRuntimeError,
    RecoveryRuntimeErrorCode,
    plan_fingerprint,
    resolve_recovery_execution_context,
)
from backend.agent_runtime.recovery.runtime_ports import (
    RecoveryReferenceResolverPort,
    RecoveryReferences,
    RecoveryRuntimeResolverPort,
)
from backend.agent_runtime.recovery.snapshot import (
    CircuitBreakerSnapshotRef,
    EffectLedgerSnapshotRef,
    SnapshotFreshnessIssue,
    StateSnapshot,
    assess_snapshot_freshness,
)
from backend.agent_runtime.recovery.snapshot_ports import StateSnapshotStorePort
from backend.agent_runtime.registry import ToolRegistry
from backend.agent_runtime.runtime.execution import PreLaunchDisposition
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.routing import (
    RoutingPreLaunchGuard,
    RuntimeRoutingResolverPort,
)
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus
from backend.shared_kernel.time import Instant


class RecoveryAction(StrEnum):
    NO_ACTION = "NO_ACTION"
    RECONCILE = "RECONCILE"
    WAIT_BACKOFF = "WAIT_BACKOFF"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    STOP = "STOP"
    ESCALATE = "ESCALATE"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"
    RESULT_RECOVERY_REQUIRED = "RESULT_RECOVERY_REQUIRED"
    RESUME = "RESUME"


@dataclass(frozen=True, slots=True)
class RecoveryDecisionResult:
    plan: Plan
    run_state: RunState
    coordination_decision: CoordinationDecision
    recovery_action: RecoveryAction
    budget_state: BudgetState
    snapshot: StateSnapshot
    retry_decision: RetryDecision | None = None
    reconciliation_result: EffectReconciliationResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(self.run_state, RunState):
            raise TypeError("run_state must be a RunState")
        if not isinstance(self.coordination_decision, CoordinationDecision):
            raise TypeError("coordination_decision must be a CoordinationDecision")
        if not isinstance(self.recovery_action, RecoveryAction):
            raise TypeError("recovery_action must be a RecoveryAction")
        if not isinstance(self.budget_state, BudgetState):
            raise TypeError("budget_state must be a BudgetState")
        if not isinstance(self.snapshot, StateSnapshot):
            raise TypeError("snapshot must be a StateSnapshot")
        if self.snapshot.run_state != self.run_state:
            raise ValueError("snapshot must capture the returned run_state")
        if self.retry_decision is not None and not isinstance(
            self.retry_decision, RetryDecision
        ):
            raise TypeError("retry_decision must be a RetryDecision or None")
        if self.reconciliation_result is not None and not isinstance(
            self.reconciliation_result, EffectReconciliationResult
        ):
            raise TypeError(
                "reconciliation_result must be an EffectReconciliationResult or None"
            )


@dataclass(frozen=True, slots=True)
class RecoveryCoordinator:
    """One-decision recovery controller outside PlanExecutor."""

    authority_guard: RoutingPreLaunchGuard
    routing_resolver: RuntimeRoutingResolverPort
    recovery_resolver: RecoveryRuntimeResolverPort
    reference_resolver: RecoveryReferenceResolverPort
    ledger: EffectLedgerPort
    budget_port: BudgetStatePort
    snapshot_store: StateSnapshotStorePort
    reconciliation_engine: EffectReconciliationEngine
    circuit_engine: CircuitBreakerEngine
    tool_registry: ToolRegistry
    use_case_registry: UseCaseRegistry
    replay_guard: ReplayGuard = field(default_factory=ReplayGuard)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    budget_policy: BudgetAccountingPolicy = field(default_factory=BudgetAccountingPolicy)
    idempotency_policy: IdempotencyPolicy = field(default_factory=IdempotencyPolicy)

    def __post_init__(self) -> None:
        if not isinstance(self.authority_guard, RoutingPreLaunchGuard):
            raise TypeError("authority_guard must be a RoutingPreLaunchGuard")
        if not isinstance(self.routing_resolver, RuntimeRoutingResolverPort):
            raise TypeError("routing_resolver must implement RuntimeRoutingResolverPort")
        if not isinstance(self.recovery_resolver, RecoveryRuntimeResolverPort):
            raise TypeError(
                "recovery_resolver must implement RecoveryRuntimeResolverPort"
            )
        if not isinstance(self.reference_resolver, RecoveryReferenceResolverPort):
            raise TypeError(
                "reference_resolver must implement RecoveryReferenceResolverPort"
            )
        if not isinstance(self.ledger, EffectLedgerPort):
            raise TypeError("ledger must implement EffectLedgerPort")
        if not isinstance(self.budget_port, BudgetStatePort):
            raise TypeError("budget_port must implement BudgetStatePort")
        if not isinstance(self.snapshot_store, StateSnapshotStorePort):
            raise TypeError("snapshot_store must implement StateSnapshotStorePort")
        if not isinstance(self.reconciliation_engine, EffectReconciliationEngine):
            raise TypeError(
                "reconciliation_engine must be an EffectReconciliationEngine"
            )
        if not isinstance(self.circuit_engine, CircuitBreakerEngine):
            raise TypeError("circuit_engine must be a CircuitBreakerEngine")

    def recover(
        self,
        *,
        plan: Plan,
        coordination_decision: CoordinationDecision,
        now: Instant,
    ) -> RecoveryDecisionResult:
        if not isinstance(plan, Plan):
            raise TypeError("plan must be a Plan")
        if not isinstance(coordination_decision, CoordinationDecision):
            raise TypeError("coordination_decision must be a CoordinationDecision")
        if not isinstance(now, Instant):
            raise TypeError("now must be an Instant")
        run_state = coordination_decision.run_state
        budget_state = self.budget_port.get(run_id=plan.run_id)
        if budget_state is None:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RETRY_BUDGET_CONFLICT
            )

        action = _pass_through_action(coordination_decision.action)
        retry_decision: RetryDecision | None = None
        reconciliation_result: EffectReconciliationResult | None = None
        checkpoint: RecoveryCheckpoint | None = None
        decisive_record: EffectLedgerRecord | None = None

        if coordination_decision.action in {
            CoordinationAction.RETRY_REQUIRED,
            CoordinationAction.RECONCILIATION_REQUIRED,
        }:
            step = _decisive_step(plan, coordination_decision)
            context = resolve_recovery_execution_context(
                plan=plan,
                step=step,
                run_state=run_state,
                routing_resolver=self.routing_resolver,
                recovery_resolver=self.recovery_resolver,
                tool_registry=self.tool_registry,
                use_case_registry=self.use_case_registry,
            )
            decisive_record = _record_for_context(self.ledger, context)
            if coordination_decision.action is CoordinationAction.RECONCILIATION_REQUIRED:
                if decisive_record.lifecycle in {
                    EffectLedgerLifecycle.RESERVED,
                    EffectLedgerLifecycle.ABANDONED,
                }:
                    action, run_state, decisive_record = (
                        self._recover_crash_reservation(
                            plan=plan,
                            step=step,
                            run_state=run_state,
                            context=context,
                            record=decisive_record,
                            budget_state=budget_state,
                            now=now,
                        )
                    )
                else:
                    reconciliation_result = self.reconciliation_engine.reconcile(
                        request=EffectReconciliationRequest(
                            record_id=decisive_record.record_id,
                            expected_version=decisive_record.version,
                        ),
                        now=now,
                    )
                    decisive_record = reconciliation_result.record
                    action = _reconciliation_action(reconciliation_result)
            if decisive_record.effect_state is EffectState.NONE and (
                coordination_decision.action is CoordinationAction.RETRY_REQUIRED
                or reconciliation_result is not None
            ):
                action, retry_decision, run_state, checkpoint = self._decide_retry(
                    plan=plan,
                    step=step,
                    run_state=run_state,
                    record=decisive_record,
                    budget_state=budget_state,
                    now=now,
                )
            elif decisive_record.effect_state is EffectState.COMMITTED:
                action = RecoveryAction.RESULT_RECOVERY_REQUIRED
            elif decisive_record.effect_state is EffectState.PARTIAL:
                action = RecoveryAction.MANUAL_REQUIRED
            elif decisive_record.effect_state is EffectState.UNKNOWN:
                action = (
                    RecoveryAction.MANUAL_REQUIRED
                    if reconciliation_result is not None
                    and reconciliation_result.disposition
                    is EffectReconciliationDisposition.MANUAL_REQUIRED
                    else RecoveryAction.RECONCILE
                )

        references = self.reference_resolver.resolve_recovery_references(
            run_id=plan.run_id
        )
        references = _merge_decisive_record(references, decisive_record)
        snapshot = self._capture_snapshot(
            plan=plan,
            run_state=run_state,
            budget_state=budget_state,
            references=references,
            checkpoint=checkpoint,
            now=now,
        )
        return RecoveryDecisionResult(
            plan=plan,
            run_state=run_state,
            coordination_decision=coordination_decision,
            recovery_action=action,
            budget_state=budget_state,
            snapshot=snapshot,
            retry_decision=retry_decision,
            reconciliation_result=reconciliation_result,
        )

    def _recover_crash_reservation(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        context: RecoveryExecutionContext,
        record: EffectLedgerRecord,
        budget_state: BudgetState,
        now: Instant,
    ) -> tuple[RecoveryAction, RunState, EffectLedgerRecord]:
        if record.attempt != 0:
            return RecoveryAction.MANUAL_REQUIRED, run_state, record
        if record.lifecycle is EffectLedgerLifecycle.RESERVED:
            expires_at = record.reservation_expires_at
            if expires_at is None or now.value < expires_at.value:
                return RecoveryAction.WAIT_BACKOFF, run_state, record
            replacement = self.idempotency_policy.prepare_abandon(
                record=record,
                now=now,
            )
            try:
                stored = self.ledger.compare_and_set(
                    record_id=record.record_id,
                    expected_version=record.version,
                    replacement=replacement,
                )
            except Exception as error:
                raise RecoveryRuntimeError(
                    RecoveryRuntimeErrorCode.LEDGER_VERSION_CONFLICT
                ) from error
            return RecoveryAction.RECONCILE, run_state, stored
        state = run_state.step_states[step.step_id]
        if state.attempt_count != 0:
            return RecoveryAction.MANUAL_REQUIRED, run_state, record
        authority = self.authority_guard.check(
            plan=plan,
            step=step,
            run_state=run_state,
            now=now,
        )
        if authority.disposition is not PreLaunchDisposition.ALLOW:
            return RecoveryAction.STOP, run_state, record
        if (
            self.budget_policy.evaluate(state=budget_state, now=now).disposition
            is not BudgetCheckDisposition.WITHIN_LIMIT
        ):
            return RecoveryAction.STOP, run_state, record
        if (
            self._snapshot_status(plan=plan, budget_state=budget_state)
            is not SnapshotRevalidationStatus.CURRENT
        ):
            return RecoveryAction.STOP, run_state, record
        circuit = self.circuit_engine.inspect(
            request=CircuitCheckRequest(
                key=context.circuit_key,
                run_id=plan.run_id,
                step_id=step.step_id,
                attempt=1,
            ),
            now=now,
        )
        if circuit.disposition in {
            CircuitPreflightDisposition.OPEN_BLOCKED,
            CircuitPreflightDisposition.HALF_OPEN_BUSY,
        }:
            return RecoveryAction.WAIT_BACKOFF, run_state, record
        replacement = self.idempotency_policy.reactivate_abandoned_reservation(
            record=record,
            now=now,
            reservation_expires_at=context.reservation_expires_at(now),
        )
        try:
            stored = self.ledger.compare_and_set(
                record_id=record.record_id,
                expected_version=record.version,
                replacement=replacement,
            )
        except Exception as error:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.LEDGER_VERSION_CONFLICT
            ) from error
        pending = replace(
            state,
            status=StepRuntimeStatus.PENDING,
            started_at=None,
            ended_at=None,
            result_refs=(),
            metrics={},
            error_ref=None,
            block_reason=None,
        )
        states = dict(run_state.step_states)
        states[step.step_id] = pending
        return RecoveryAction.RESUME, replace(run_state, step_states=states), stored

    def _decide_retry(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        record: EffectLedgerRecord,
        budget_state: BudgetState,
        now: Instant,
    ) -> tuple[
        RecoveryAction,
        RetryDecision | None,
        RunState,
        RecoveryCheckpoint | None,
    ]:
        facts = record.retry_failure_facts
        if facts is None:
            return RecoveryAction.STOP, None, run_state, None
        canonical_authority = self.authority_guard.check(
            plan=plan,
            step=step,
            run_state=run_state,
            now=now,
        )
        security_assessment = canonical_authority.security_assessment
        security_invalid = (
            security_assessment is not None
            and not security_assessment.launchable
        )
        authority_status = (
            AuthorityRevalidationStatus.VALID
            if canonical_authority.disposition is PreLaunchDisposition.ALLOW
            or security_invalid
            else AuthorityRevalidationStatus.INVALID
        )
        security_status = (
            SecurityRevalidationStatus.INVALID
            if security_invalid
            else (
                SecurityRevalidationStatus.VALID
                if canonical_authority.disposition is PreLaunchDisposition.ALLOW
                else SecurityRevalidationStatus.NOT_REQUIRED
            )
        )
        budget_check = self.budget_policy.evaluate(state=budget_state, now=now)
        snapshot_status = self._snapshot_status(
            plan=plan,
            budget_state=budget_state,
        )
        deadline = budget_state.limits.deadline
        deadline_status = (
            DeadlineRevalidationStatus.EXPIRED
            if deadline is not None and now.value >= deadline.value
            else DeadlineRevalidationStatus.VALID
        )
        replay = self.replay_guard.evaluate(
            record=record,
            preconditions=ReplayPreconditions(
                requested_identity=record.identity,
                permission_status=authority_status,
                gate_status=authority_status,
                budget_check=budget_check,
                deadline_status=deadline_status,
                snapshot_status=snapshot_status,
                security_status=security_status,
            ),
        )
        error = facts.to_error(
            step_id=step.step_id,
            attempt=record.attempt,
            effect_state=record.effect_state,
        )
        decision = self.retry_policy.decide(
            RetryPolicyRequest(
                error=error,
                record=record,
                budget_state=budget_state,
                budget_check=budget_check,
                replay_decision=replay,
                now=now,
            )
        )
        action = _retry_action(decision)
        if decision.disposition is not RetryDisposition.RETRY:
            return action, decision, run_state, None
        if decision.next_attempt is None or decision.schedule is None:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            )
        state = run_state.step_states[step.step_id]
        if state.attempt_count != record.attempt:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
            )
        pending = replace(
            state,
            status=StepRuntimeStatus.PENDING,
            started_at=None,
            ended_at=None,
            result_refs=(),
            metrics={},
            error_ref=None,
            block_reason=None,
        )
        states = dict(run_state.step_states)
        states[step.step_id] = pending
        updated_run = replace(run_state, step_states=states)
        checkpoint = RecoveryCheckpoint(
            action=RecoveryCheckpointAction.RETRY_SCHEDULED,
            step_id=step.step_id,
            record_id=record.record_id,
            record_version=record.version,
            next_attempt=decision.next_attempt,
            retry_ordinal=decision.schedule.retry_ordinal,
            not_before=decision.schedule.not_before,
            reason_codes=tuple(item.value for item in decision.reason_codes),
        )
        return RecoveryAction.RETRY_SCHEDULED, decision, updated_run, checkpoint

    def _snapshot_status(
        self,
        *,
        plan: Plan,
        budget_state: BudgetState,
    ) -> SnapshotRevalidationStatus:
        snapshot = self.snapshot_store.load_latest(run_id=plan.run_id)
        if snapshot is None:
            return SnapshotRevalidationStatus.NOT_REQUIRED
        references = self.reference_resolver.resolve_recovery_references(
            run_id=plan.run_id
        )
        assessment = assess_snapshot_freshness(
            snapshot=snapshot,
            current_budget=budget_state,
            current_ledger_records={
                item.record_id: item for item in references.effect_records
            },
            current_plan_fingerprint=plan_fingerprint(plan),
            current_circuit_states={
                item.circuit_id: item for item in references.circuit_states
            },
        )
        if SnapshotFreshnessIssue.PLAN_MISMATCH in assessment.issues:
            return SnapshotRevalidationStatus.PLAN_MISMATCH
        if assessment.issues:
            return SnapshotRevalidationStatus.STALE
        return SnapshotRevalidationStatus.CURRENT

    def _capture_snapshot(
        self,
        *,
        plan: Plan,
        run_state: RunState,
        budget_state: BudgetState,
        references: RecoveryReferences,
        checkpoint: RecoveryCheckpoint | None,
        now: Instant,
    ) -> StateSnapshot:
        previous = self.snapshot_store.load_latest(run_id=plan.run_id)
        sequence = 1 if previous is None else previous.sequence + 1
        snapshot = StateSnapshot.capture(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            sequence=sequence,
            run_id=plan.run_id,
            plan_id=plan.plan_id,
            plan_version=plan.plan_version,
            plan_fingerprint=plan_fingerprint(plan),
            run_state=run_state,
            budget_state=budget_state,
            effect_ledger_refs=tuple(
                EffectLedgerSnapshotRef(item.record_id, item.version)
                for item in sorted(
                    references.effect_records, key=lambda value: value.record_id
                )
            ),
            circuit_breaker_refs=tuple(
                CircuitBreakerSnapshotRef(item.circuit_id, item.version)
                for item in sorted(
                    references.circuit_states, key=lambda value: value.circuit_id
                )
            ),
            recovery_checkpoint=checkpoint,
            captured_at=now,
        )
        try:
            return self.snapshot_store.save(
                snapshot=snapshot,
                expected_previous_sequence=(
                    None if previous is None else previous.sequence
                ),
            )
        except Exception as error:
            raise RecoveryRuntimeError(
                RecoveryRuntimeErrorCode.SNAPSHOT_CONFLICT
            ) from error


def _decisive_step(plan: Plan, decision: CoordinationDecision) -> StepSpec:
    if len(decision.affected_step_ids) != 1:
        raise RecoveryRuntimeError(
            RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
        )
    step_id = decision.affected_step_ids[0]
    try:
        return next(item for item in plan.steps if item.step_id == step_id)
    except StopIteration as error:
        raise RecoveryRuntimeError(
            RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
        ) from error


def _record_for_context(
    ledger: EffectLedgerPort,
    context: RecoveryExecutionContext,
) -> EffectLedgerRecord:
    identity = context.identity
    if identity is None:
        raise RecoveryRuntimeError(
            RecoveryRuntimeErrorCode.UNSUPPORTED_RECOVERY_ROUTE
        )
    record = ledger.get(record_id=identity.record_id)
    if record is None or record.identity != identity:
        raise RecoveryRuntimeError(
            RecoveryRuntimeErrorCode.RECOVERY_CONTEXT_MISMATCH
        )
    return record


def _merge_decisive_record(
    references: RecoveryReferences,
    record: EffectLedgerRecord | None,
) -> RecoveryReferences:
    if record is None:
        return references
    by_id = {item.record_id: item for item in references.effect_records}
    by_id[record.record_id] = record
    return RecoveryReferences(
        effect_records=tuple(by_id.values()),
        circuit_states=references.circuit_states,
    )


def _retry_action(decision: RetryDecision) -> RecoveryAction:
    return {
        RetryDisposition.RETRY: RecoveryAction.RETRY_SCHEDULED,
        RetryDisposition.NO_RETRY: RecoveryAction.STOP,
        RetryDisposition.RECONCILE_FIRST: RecoveryAction.RECONCILE,
        RetryDisposition.REPLAN: RecoveryAction.REPLAN_REQUIRED,
        RetryDisposition.STOP: RecoveryAction.STOP,
        RetryDisposition.ESCALATE: RecoveryAction.ESCALATE,
    }[decision.disposition]


def _reconciliation_action(
    result: EffectReconciliationResult,
) -> RecoveryAction:
    if result.disposition is EffectReconciliationDisposition.STILL_UNKNOWN:
        return RecoveryAction.RECONCILE
    if result.disposition is EffectReconciliationDisposition.MANUAL_REQUIRED:
        return RecoveryAction.MANUAL_REQUIRED
    if result.record.effect_state is EffectState.COMMITTED:
        return RecoveryAction.RESULT_RECOVERY_REQUIRED
    if result.record.effect_state is EffectState.PARTIAL:
        return RecoveryAction.MANUAL_REQUIRED
    return RecoveryAction.NO_ACTION


def _pass_through_action(action: CoordinationAction) -> RecoveryAction:
    return {
        CoordinationAction.CONTINUE: RecoveryAction.NO_ACTION,
        CoordinationAction.COMPLETE: RecoveryAction.NO_ACTION,
        CoordinationAction.WAIT_GATE: RecoveryAction.NO_ACTION,
        CoordinationAction.WAIT_CONDITION: RecoveryAction.NO_ACTION,
        CoordinationAction.RETRY_REQUIRED: RecoveryAction.STOP,
        CoordinationAction.RECONCILIATION_REQUIRED: RecoveryAction.RECONCILE,
        CoordinationAction.REPLAN_REQUIRED: RecoveryAction.REPLAN_REQUIRED,
        CoordinationAction.REVIEW_PARTIAL: RecoveryAction.MANUAL_REQUIRED,
        CoordinationAction.ESCALATE: RecoveryAction.ESCALATE,
        CoordinationAction.STOP: RecoveryAction.STOP,
    }[action]
