from __future__ import annotations

from datetime import timedelta

import pytest

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    EffectLedgerRecord,
    EffectReconciliationPolicy,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    ReplayGuard,
    ReplayGuardDisposition,
    RetryDisposition,
    RetryPolicy,
    RetryPolicyRequest,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.reconciliation_fakes import make_finalized_record
from tests.support.retry_replay_fakes import (
    NOW,
    make_budget_check,
    make_budget_state,
    make_error,
    make_preconditions,
)


def _unknown_record() -> EffectLedgerRecord:
    return make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=Instant(NOW.value - timedelta(minutes=2)),
        expires_at=Instant(NOW.value - timedelta(minutes=1)),
        finalized_at=Instant(NOW.value - timedelta(seconds=30)),
    )


def _reconcile(
    disposition: ReconciliationObservationDisposition,
) -> EffectLedgerRecord:
    record = _unknown_record()
    observation = ReconciliationObservation(
        record_id=record.record_id,
        record_version=record.version,
        attempt=record.attempt,
        disposition=disposition,
        observed_result_refs=(),
        observed_at=NOW,
    )
    return EffectReconciliationPolicy().prepare_replacement(
        record=record,
        observation=observation,
    )


@pytest.mark.parametrize(
    ("observation", "guard_expected", "retry_expected"),
    [
        (
            ReconciliationObservationDisposition.NOT_COMMITTED,
            ReplayGuardDisposition.ELIGIBLE,
            RetryDisposition.RETRY,
        ),
        (
            ReconciliationObservationDisposition.COMMITTED,
            ReplayGuardDisposition.BLOCKED,
            RetryDisposition.NO_RETRY,
        ),
        (
            ReconciliationObservationDisposition.PARTIAL,
            ReplayGuardDisposition.BLOCKED,
            RetryDisposition.STOP,
        ),
    ],
)
def test_retry_policy_uses_reconciled_effect_as_authoritative_state(
    observation: ReconciliationObservationDisposition,
    guard_expected: ReplayGuardDisposition,
    retry_expected: RetryDisposition,
) -> None:
    record = _reconcile(observation)
    preconditions = make_preconditions(identity=record.identity)
    guard = ReplayGuard().evaluate(
        record=record,
        preconditions=preconditions,
    )

    retry = RetryPolicy().decide(
        RetryPolicyRequest(
            error=make_error(
                attempt=record.attempt,
                effect_state=EffectState.UNKNOWN,
            ),
            record=record,
            budget_state=make_budget_state(),
            budget_check=make_budget_check(),
            replay_decision=guard,
            now=NOW,
        )
    )

    assert guard.disposition is guard_expected
    assert retry.disposition is retry_expected
    assert retry.requires_circuit_check is True
    if retry_expected is RetryDisposition.RETRY:
        assert retry.next_attempt == record.attempt + 1
        assert retry.not_before is not None
    else:
        assert retry.next_attempt is None
        assert retry.not_before is None
