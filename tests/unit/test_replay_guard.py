from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    AuthorityRevalidationStatus,
    BudgetCheckDisposition,
    DeadlineRevalidationStatus,
    EffectLedgerRecord,
    IdempotencyPolicy,
    ReconciliationStatus,
    ReplayGuard,
    ReplayGuardDecision,
    ReplayGuardDisposition,
    ReplayGuardReasonCode,
    SnapshotRevalidationStatus,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.reconciliation_fakes import (
    make_finalized_record,
    make_identity,
    make_in_progress_record,
)
from tests.support.retry_replay_fakes import (
    NOW,
    make_none_record,
    make_preconditions,
)

GUARD = ReplayGuard()


def _evaluate(
    record: EffectLedgerRecord,
    **changes: object,
) -> ReplayGuardDecision:
    return GUARD.evaluate(
        record=record,
        preconditions=make_preconditions(identity=record.identity, **changes),
    )


def _finalized(
    effect_state: EffectState,
    status: ReconciliationStatus | None = None,
) -> EffectLedgerRecord:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=effect_state,
        created_at=Instant(NOW.value - timedelta(minutes=2)),
        expires_at=Instant(NOW.value - timedelta(minutes=1)),
        finalized_at=Instant(NOW.value - timedelta(seconds=30)),
    )
    return replace(record, reconciliation_status=status) if status else record


def test_exact_identity_is_required() -> None:
    record = make_none_record()
    changed_identity = make_identity(
        CapabilityExecutionRoute.UTILITY,
        target_id="tool.other_target",
    )

    decision = GUARD.evaluate(
        record=record,
        preconditions=make_preconditions(identity=changed_identity),
    )

    assert decision.disposition is ReplayGuardDisposition.REPLAN_REQUIRED
    assert decision.reason_codes == (ReplayGuardReasonCode.IDENTITY_MISMATCH,)


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        (
            {"permission": AuthorityRevalidationStatus.INVALID},
            ReplayGuardReasonCode.PERMISSION_INVALID,
        ),
        (
            {"gate": AuthorityRevalidationStatus.INVALID},
            ReplayGuardReasonCode.GATE_INVALID,
        ),
        (
            {"budget": BudgetCheckDisposition.LIMIT_EXCEEDED},
            ReplayGuardReasonCode.BUDGET_EXCEEDED,
        ),
        (
            {"budget": BudgetCheckDisposition.USAGE_UNKNOWN},
            ReplayGuardReasonCode.BUDGET_USAGE_UNKNOWN,
        ),
        (
            {"deadline": DeadlineRevalidationStatus.EXPIRED},
            ReplayGuardReasonCode.DEADLINE_EXPIRED,
        ),
        (
            {"snapshot": SnapshotRevalidationStatus.STALE},
            ReplayGuardReasonCode.SNAPSHOT_STALE,
        ),
    ],
)
def test_revalidation_failure_blocks_replay(changes, reason) -> None:  # type: ignore[no-untyped-def]
    decision = _evaluate(make_none_record(), **changes)

    assert decision.disposition is ReplayGuardDisposition.BLOCKED
    assert reason in decision.reason_codes


def test_plan_mismatch_requires_replan() -> None:
    decision = _evaluate(
        make_none_record(),
        snapshot=SnapshotRevalidationStatus.PLAN_MISMATCH,
    )

    assert decision.disposition is ReplayGuardDisposition.REPLAN_REQUIRED
    assert decision.reason_codes == (ReplayGuardReasonCode.PLAN_MISMATCH,)


def test_reserved_in_progress_and_abandoned_records_are_fail_closed() -> None:
    policy = IdempotencyPolicy()
    created = Instant(NOW.value - timedelta(minutes=2))
    expires = Instant(NOW.value - timedelta(minutes=1))
    reserved = policy.new_reservation(
        identity=make_identity(CapabilityExecutionRoute.UTILITY),
        now=created,
        reservation_expires_at=expires,
    )
    in_progress = make_in_progress_record(
        route=CapabilityExecutionRoute.UTILITY,
        created_at=created,
        expires_at=expires,
    )
    abandoned = policy.prepare_abandon(record=reserved, now=NOW)

    assert _evaluate(reserved).disposition is ReplayGuardDisposition.BLOCKED
    assert (
        _evaluate(in_progress).disposition
        is ReplayGuardDisposition.RECONCILE_FIRST
    )
    assert _evaluate(abandoned).disposition is ReplayGuardDisposition.BLOCKED


@pytest.mark.parametrize(
    ("effect", "status", "expected"),
    [
        (
            EffectState.UNKNOWN,
            ReconciliationStatus.PENDING,
            ReplayGuardDisposition.RECONCILE_FIRST,
        ),
        (
            EffectState.UNKNOWN,
            ReconciliationStatus.MANUAL_REQUIRED,
            ReplayGuardDisposition.MANUAL_REQUIRED,
        ),
        (
            EffectState.PARTIAL,
            ReconciliationStatus.PENDING,
            ReplayGuardDisposition.RECONCILE_FIRST,
        ),
        (
            EffectState.PARTIAL,
            ReconciliationStatus.RESOLVED,
            ReplayGuardDisposition.BLOCKED,
        ),
        (
            EffectState.PARTIAL,
            ReconciliationStatus.MANUAL_REQUIRED,
            ReplayGuardDisposition.MANUAL_REQUIRED,
        ),
        (
            EffectState.COMMITTED,
            ReconciliationStatus.NOT_REQUIRED,
            ReplayGuardDisposition.BLOCKED,
        ),
        (
            EffectState.NONE,
            ReconciliationStatus.NOT_REQUIRED,
            ReplayGuardDisposition.ELIGIBLE,
        ),
        (
            EffectState.NONE,
            ReconciliationStatus.RESOLVED,
            ReplayGuardDisposition.ELIGIBLE,
        ),
    ],
)
def test_effect_and_reconciliation_matrix_is_closed(
    effect: EffectState,
    status: ReconciliationStatus,
    expected: ReplayGuardDisposition,
) -> None:
    assert _evaluate(_finalized(effect, status)).disposition is expected


def test_circuit_requirement_is_fixed_and_not_caller_controlled() -> None:
    decision = _evaluate(make_none_record())

    assert decision.requires_circuit_check is True
    with pytest.raises(TypeError):
        ReplayGuardDecision(
            disposition=ReplayGuardDisposition.ELIGIBLE,
            reason_codes=(),
            record_id=decision.record_id,
            record_version=decision.record_version,
            requires_circuit_check=False,  # type: ignore[call-arg]
        )


def test_replay_guard_does_not_mutate_ledger_record() -> None:
    record = make_none_record()
    before = record

    _evaluate(record)

    assert record == before
