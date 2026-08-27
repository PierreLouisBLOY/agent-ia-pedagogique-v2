from __future__ import annotations

from dataclasses import replace

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    ReplayGuard,
    ReplayGuardDisposition,
    ReplayGuardReasonCode,
    SecurityRevalidationStatus,
)
from tests.support.retry_replay_fakes import make_none_record, make_preconditions


def test_replay_refuses_a_current_security_failure() -> None:
    record = make_none_record()
    decision = ReplayGuard().evaluate(
        record=record,
        preconditions=replace(
            make_preconditions(identity=record.identity),
            security_status=SecurityRevalidationStatus.INVALID,
        ),
    )

    assert decision.disposition is ReplayGuardDisposition.BLOCKED
    assert decision.reason_codes == (ReplayGuardReasonCode.SECURITY_INVALID,)


def test_committed_effect_still_dominates_security_revalidation() -> None:
    none_record = make_none_record()
    committed_attempt = replace(
        none_record.attempts[-1], effect_state=EffectState.COMMITTED
    )
    record = replace(
        none_record,
        effect_state=EffectState.COMMITTED,
        attempts=(committed_attempt,),
    )
    decision = ReplayGuard().evaluate(
        record=record,
        preconditions=replace(
            make_preconditions(identity=record.identity),
            security_status=SecurityRevalidationStatus.INVALID,
        ),
    )

    assert decision.disposition is ReplayGuardDisposition.BLOCKED
    assert decision.reason_codes == (ReplayGuardReasonCode.EFFECT_COMMITTED,)
