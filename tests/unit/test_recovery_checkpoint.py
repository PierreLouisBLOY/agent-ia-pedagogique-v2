from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import (
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    RecommendedAction,
)
from backend.agent_runtime.recovery import (
    EffectLedgerLifecycle,
    IdempotencyPolicy,
    RecoveryCheckpoint,
    RecoveryCheckpointAction,
    RetryFailureFacts,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.reconciliation_fakes import make_identity

NOW = Instant(datetime(2026, 8, 27, 14, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(minutes=2))


def _error() -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="PROVIDER_TEMPORARY_FAILURE",
        category=ErrorCategory.TRANSIENT,
        source=ErrorSource.PROVIDER,
        retryable=True,
        severity=ErrorSeverity.ERROR,
        message="not persisted",
        step_id="step-reconcile",
        attempt=1,
        effect_state=EffectState.NONE,
        recommended_action=RecommendedAction.RETRY,
    )


def test_retry_failure_facts_round_trip_only_closed_fields() -> None:
    facts = RetryFailureFacts.from_error(_error())
    restored = facts.to_error(
        step_id="step-reconcile",
        attempt=1,
        effect_state=EffectState.NONE,
    )

    assert restored.error_code == "PROVIDER_TEMPORARY_FAILURE"
    assert restored.category is ErrorCategory.TRANSIENT
    assert restored.retryable is True
    assert restored.recommended_action is RecommendedAction.RETRY
    assert "not persisted" not in restored.message
    assert "not persisted" not in repr(facts)


def test_checkpoint_binds_record_attempt_ordinal_and_not_before() -> None:
    identity = make_identity(CapabilityExecutionRoute.UTILITY)
    checkpoint = RecoveryCheckpoint(
        action=RecoveryCheckpointAction.RETRY_SCHEDULED,
        step_id=identity.step_id,
        record_id=identity.record_id,
        record_version=3,
        next_attempt=2,
        retry_ordinal=1,
        not_before=LATER,
        reason_codes=("SAFE_RETRY",),
    )

    assert checkpoint.not_before is LATER
    with pytest.raises(ValueError, match="retry_ordinal"):
        replace(checkpoint, retry_ordinal=2)


def test_abandoned_reactivation_preserves_identity_record_and_attempt_zero() -> None:
    policy = IdempotencyPolicy()
    identity = make_identity(CapabilityExecutionRoute.UTILITY)
    expires = Instant(NOW.value + timedelta(seconds=1))
    reserved = policy.new_reservation(
        identity=identity,
        now=NOW,
        reservation_expires_at=expires,
    )
    abandoned_at = Instant(expires.value + timedelta(seconds=1))
    abandoned = policy.prepare_abandon(record=reserved, now=abandoned_at)
    renewed_expiry = Instant(abandoned_at.value + timedelta(minutes=1))
    reactivated = policy.reactivate_abandoned_reservation(
        record=abandoned,
        now=abandoned_at,
        reservation_expires_at=renewed_expiry,
    )

    assert reactivated.lifecycle is EffectLedgerLifecycle.RESERVED
    assert reactivated.record_id == abandoned.record_id
    assert reactivated.identity == abandoned.identity
    assert reactivated.version == abandoned.version + 1
    assert reactivated.attempt == 0


def test_finalized_none_retry_reservation_keeps_lineage() -> None:
    policy = IdempotencyPolicy()
    identity = make_identity(CapabilityExecutionRoute.UTILITY)
    reserved = policy.new_reservation(identity=identity, now=NOW)
    started = policy.prepare_start(record=reserved, attempt=1, now=NOW)
    facts = RetryFailureFacts.from_error(_error())
    finalized = policy.prepare_finalize(
        record=started,
        effect_state=EffectState.NONE,
        now=LATER,
        retry_failure_facts=facts,
    )
    retry_reserved = policy.prepare_retry_reservation(
        record=finalized,
        now=LATER,
        reservation_expires_at=Instant(LATER.value + timedelta(minutes=1)),
    )
    second = policy.prepare_start(record=retry_reserved, attempt=2, now=LATER)

    assert retry_reserved.attempt == 1
    assert retry_reserved.retry_failure_facts == facts
    assert second.attempt == 2
    assert second.attempts[0] == finalized.attempts[0]
