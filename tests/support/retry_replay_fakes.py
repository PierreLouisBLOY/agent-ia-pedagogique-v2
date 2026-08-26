from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    RecommendedAction,
)
from backend.agent_runtime.recovery import (
    AuthorityRevalidationStatus,
    BudgetCheckDisposition,
    BudgetCheckResult,
    BudgetDimension,
    BudgetState,
    DeadlineRevalidationStatus,
    EffectiveBudgetLimits,
    EffectLedgerRecord,
    IdempotencyIdentity,
    ReplayGuard,
    ReplayGuardDecision,
    ReplayPreconditions,
    SnapshotRevalidationStatus,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.reconciliation_fakes import (
    make_finalized_record,
    make_identity,
)

NOW = Instant(datetime(2026, 8, 27, 10, 0, tzinfo=UTC))
DEADLINE = Instant(NOW.value + timedelta(minutes=5))


def make_none_record() -> EffectLedgerRecord:
    return make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.NONE,
        created_at=Instant(NOW.value - timedelta(minutes=2)),
        expires_at=Instant(NOW.value - timedelta(minutes=1)),
        finalized_at=Instant(NOW.value - timedelta(seconds=30)),
    )


def make_budget_check(
    disposition: BudgetCheckDisposition = BudgetCheckDisposition.WITHIN_LIMIT,
) -> BudgetCheckResult:
    if disposition is BudgetCheckDisposition.LIMIT_EXCEEDED:
        return BudgetCheckResult(
            disposition=disposition,
            exceeded_dimensions=(BudgetDimension.RETRIES_PER_STEP,),
        )
    if disposition is BudgetCheckDisposition.USAGE_UNKNOWN:
        return BudgetCheckResult(
            disposition=disposition,
            unknown_dimensions=(BudgetDimension.TOKENS,),
        )
    return BudgetCheckResult(disposition=disposition)


def make_preconditions(
    *,
    identity: IdempotencyIdentity | None = None,
    permission: AuthorityRevalidationStatus = AuthorityRevalidationStatus.VALID,
    gate: AuthorityRevalidationStatus = AuthorityRevalidationStatus.VALID,
    budget: BudgetCheckDisposition = BudgetCheckDisposition.WITHIN_LIMIT,
    deadline: DeadlineRevalidationStatus = DeadlineRevalidationStatus.VALID,
    snapshot: SnapshotRevalidationStatus = SnapshotRevalidationStatus.CURRENT,
) -> ReplayPreconditions:
    return ReplayPreconditions(
        requested_identity=identity
        or make_identity(CapabilityExecutionRoute.UTILITY),
        permission_status=permission,
        gate_status=gate,
        budget_check=make_budget_check(budget),
        deadline_status=deadline,
        snapshot_status=snapshot,
    )


def make_replay_decision(
    record: EffectLedgerRecord | None = None,
) -> ReplayGuardDecision:
    target = record or make_none_record()
    return ReplayGuard().evaluate(
        record=target,
        preconditions=make_preconditions(identity=target.identity),
    )


def make_budget_state(
    *,
    retries_by_step: dict[str, int] | None = None,
    max_retries_per_envelope: int | None = 3,
    max_retries_per_step: int | None = 2,
    deadline: Instant | None = DEADLINE,
) -> BudgetState:
    return BudgetState(
        run_id="run-reconcile",
        version=1,
        limits=EffectiveBudgetLimits(
            max_retries_per_envelope=max_retries_per_envelope,
            max_retries_per_step=max_retries_per_step,
            deadline=deadline,
        ),
        created_at=Instant(NOW.value - timedelta(minutes=3)),
        updated_at=NOW,
        consumed_cost=Decimal("0"),
        retries_by_step=retries_by_step or {},
    )


def make_error(
    *,
    category: ErrorCategory = ErrorCategory.TRANSIENT,
    retryable: bool = True,
    action: RecommendedAction = RecommendedAction.RETRY,
    effect_state: EffectState = EffectState.NONE,
    attempt: int = 1,
    step_id: str = "step-reconcile",
) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="PROVIDER_TEMPORARY_FAILURE",
        category=category,
        source=ErrorSource.PROVIDER,
        retryable=retryable,
        severity=ErrorSeverity.ERROR,
        message="temporary failure",
        step_id=step_id,
        attempt=attempt,
        effect_state=effect_state,
        recommended_action=action,
    )
