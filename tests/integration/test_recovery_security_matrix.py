from __future__ import annotations

from datetime import timedelta

import pytest

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    ReplayGuard,
    ReplayGuardDisposition,
    ReplayGuardReasonCode,
    SecurityRevalidationStatus,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from tests.support.reconciliation_fakes import make_finalized_record
from tests.support.retry_replay_fakes import NOW, make_none_record, make_preconditions


@pytest.mark.parametrize(
    ("effect_state", "expected_disposition", "expected_reason"),
    [
        (
            EffectState.NONE,
            ReplayGuardDisposition.BLOCKED,
            ReplayGuardReasonCode.SECURITY_INVALID,
        ),
        (
            EffectState.COMMITTED,
            ReplayGuardDisposition.BLOCKED,
            ReplayGuardReasonCode.EFFECT_COMMITTED,
        ),
        (
            EffectState.UNKNOWN,
            ReplayGuardDisposition.RECONCILE_FIRST,
            ReplayGuardReasonCode.EFFECT_UNKNOWN,
        ),
        (
            EffectState.PARTIAL,
            ReplayGuardDisposition.RECONCILE_FIRST,
            ReplayGuardReasonCode.EFFECT_PARTIAL,
        ),
    ],
)
def test_effect_state_dominates_current_security_except_for_safe_none_replay(
    effect_state: EffectState,
    expected_disposition: ReplayGuardDisposition,
    expected_reason: ReplayGuardReasonCode,
) -> None:
    if effect_state is EffectState.NONE:
        record = make_none_record()
    else:
        record = make_finalized_record(
            route=CapabilityExecutionRoute.UTILITY,
            effect_state=effect_state,
            created_at=NOW,
            expires_at=type(NOW)(NOW.value + timedelta(minutes=1)),
            finalized_at=type(NOW)(NOW.value + timedelta(seconds=1)),
        )
    preconditions = make_preconditions(identity=record.identity)
    preconditions = type(preconditions)(
        requested_identity=preconditions.requested_identity,
        permission_status=preconditions.permission_status,
        gate_status=preconditions.gate_status,
        budget_check=preconditions.budget_check,
        deadline_status=preconditions.deadline_status,
        snapshot_status=preconditions.snapshot_status,
        security_status=SecurityRevalidationStatus.INVALID,
    )

    decision = ReplayGuard().evaluate(record=record, preconditions=preconditions)

    assert decision.disposition is expected_disposition
    assert decision.reason_codes[0] is expected_reason
