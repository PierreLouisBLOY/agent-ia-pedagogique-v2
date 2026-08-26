from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    EffectReconciliationError,
    EffectReconciliationErrorCode,
    EffectReconciliationPolicy,
    IdempotencyPolicy,
    ReconciliationEligibility,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    ReconciliationStatus,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.reconciliation_fakes import (
    make_finalized_record,
    make_identity,
    make_in_progress_record,
)

NOW = Instant(datetime(2026, 8, 27, 9, 0, tzinfo=UTC))
FINISHED = Instant(NOW.value + timedelta(seconds=20))
LEASE_END = Instant(NOW.value + timedelta(minutes=1))
AFTER_EXPIRY = Instant(NOW.value + timedelta(minutes=2))
POLICY = EffectReconciliationPolicy()


def _finalized(
    effect_state: EffectState,
    status: ReconciliationStatus | None = None,
):
    return make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=effect_state,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
        reconciliation_status=status,
        result_refs=("existing-ref",),
    )


def _observation(
    record,
    disposition: ReconciliationObservationDisposition,
    *,
    refs: tuple[str, ...] = ("observed-ref",),
) -> ReconciliationObservation:
    return ReconciliationObservation(
        record_id=record.record_id,
        record_version=record.version,
        attempt=record.attempt,
        disposition=disposition,
        observed_result_refs=refs,
        observed_at=AFTER_EXPIRY,
    )


@pytest.mark.parametrize("effect_state", [EffectState.NONE, EffectState.COMMITTED])
def test_known_finalized_effect_is_not_reconciled(effect_state: EffectState) -> None:
    record = _finalized(effect_state)

    assert POLICY.classify_eligibility(
        record=record,
        now=AFTER_EXPIRY,
    ) is ReconciliationEligibility.NOT_REQUIRED


@pytest.mark.parametrize("effect_state", [EffectState.UNKNOWN, EffectState.PARTIAL])
def test_pending_unknown_or_partial_finalized_record_is_eligible(
    effect_state: EffectState,
) -> None:
    record = _finalized(effect_state)

    assert POLICY.classify_eligibility(
        record=record,
        now=AFTER_EXPIRY,
    ) is ReconciliationEligibility.ELIGIBLE


def test_resolved_partial_is_not_reprobed_and_remains_partial() -> None:
    record = _finalized(EffectState.PARTIAL, ReconciliationStatus.RESOLVED)

    assert POLICY.classify_eligibility(
        record=record,
        now=AFTER_EXPIRY,
    ) is ReconciliationEligibility.NOT_REQUIRED
    assert record.effect_state is EffectState.PARTIAL


@pytest.mark.parametrize("effect_state", [EffectState.UNKNOWN, EffectState.PARTIAL])
def test_manual_required_is_not_automatically_eligible(effect_state: EffectState) -> None:
    record = _finalized(effect_state, ReconciliationStatus.MANUAL_REQUIRED)

    assert POLICY.classify_eligibility(
        record=record,
        now=AFTER_EXPIRY,
    ) is ReconciliationEligibility.MANUAL_REQUIRED


def test_reserved_and_abandoned_records_are_not_eligible() -> None:
    idempotency = IdempotencyPolicy()
    reserved = idempotency.new_reservation(
        identity=make_identity(CapabilityExecutionRoute.UTILITY),
        now=NOW,
        reservation_expires_at=LEASE_END,
    )
    abandoned = idempotency.prepare_abandon(record=reserved, now=AFTER_EXPIRY)

    for record in (reserved, abandoned):
        assert POLICY.classify_eligibility(
            record=record,
            now=AFTER_EXPIRY,
        ) is ReconciliationEligibility.NOT_ELIGIBLE


def test_in_progress_active_is_blocked_and_expired_is_eligible() -> None:
    record = make_in_progress_record(
        route=CapabilityExecutionRoute.UTILITY,
        created_at=NOW,
        expires_at=LEASE_END,
    )

    assert POLICY.classify_eligibility(
        record=record,
        now=NOW,
    ) is ReconciliationEligibility.RECORD_STILL_ACTIVE
    assert POLICY.classify_eligibility(
        record=record,
        now=AFTER_EXPIRY,
    ) is ReconciliationEligibility.ELIGIBLE


@pytest.mark.parametrize(
    ("disposition", "effect_state", "status"),
    [
        (
            ReconciliationObservationDisposition.COMMITTED,
            EffectState.COMMITTED,
            ReconciliationStatus.RESOLVED,
        ),
        (
            ReconciliationObservationDisposition.NOT_COMMITTED,
            EffectState.NONE,
            ReconciliationStatus.RESOLVED,
        ),
        (
            ReconciliationObservationDisposition.PARTIAL,
            EffectState.PARTIAL,
            ReconciliationStatus.RESOLVED,
        ),
        (
            ReconciliationObservationDisposition.STILL_UNKNOWN,
            EffectState.UNKNOWN,
            ReconciliationStatus.PENDING,
        ),
        (
            ReconciliationObservationDisposition.MANUAL_REQUIRED,
            EffectState.UNKNOWN,
            ReconciliationStatus.MANUAL_REQUIRED,
        ),
    ],
)
def test_observation_mapping_is_exact(
    disposition: ReconciliationObservationDisposition,
    effect_state: EffectState,
    status: ReconciliationStatus,
) -> None:
    record = _finalized(EffectState.UNKNOWN)

    replacement = POLICY.prepare_replacement(
        record=record,
        observation=_observation(record, disposition),
    )

    assert replacement.effect_state is effect_state
    assert replacement.reconciliation_status is status
    assert replacement.version == record.version + 1


def test_manual_required_preserves_proven_partial_effect() -> None:
    record = _finalized(EffectState.PARTIAL)

    replacement = POLICY.prepare_replacement(
        record=record,
        observation=_observation(
            record,
            ReconciliationObservationDisposition.MANUAL_REQUIRED,
        ),
    )

    assert replacement.effect_state is EffectState.PARTIAL
    assert replacement.reconciliation_status is ReconciliationStatus.MANUAL_REQUIRED


def test_in_progress_reconciliation_closes_attempt_and_finalizes_record() -> None:
    record = make_in_progress_record(
        route=CapabilityExecutionRoute.UTILITY,
        created_at=NOW,
        expires_at=LEASE_END,
    )

    replacement = POLICY.prepare_replacement(
        record=record,
        observation=_observation(
            record,
            ReconciliationObservationDisposition.STILL_UNKNOWN,
        ),
    )

    assert replacement.lifecycle.value == "FINALIZED"
    assert replacement.attempts[-1].ended_at == AFTER_EXPIRY
    assert replacement.effect_state is EffectState.UNKNOWN
    assert replacement.reconciliation_status is ReconciliationStatus.PENDING


def test_finalized_reconciliation_does_not_create_attempt_and_merges_refs_stably() -> None:
    record = _finalized(EffectState.UNKNOWN)

    replacement = POLICY.prepare_replacement(
        record=record,
        observation=_observation(
            record,
            ReconciliationObservationDisposition.COMMITTED,
            refs=("existing-ref", "observed-ref", "existing-ref"),
        ),
    )

    assert len(replacement.attempts) == len(record.attempts)
    assert replacement.attempts[-1].ended_at == record.attempts[-1].ended_at
    assert replacement.result_refs == ("existing-ref", "observed-ref")


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        (
            {"record_id": "effect:v1:" + "f" * 64},
            EffectReconciliationErrorCode.OBSERVATION_RECORD_MISMATCH,
        ),
        (
            {"record_version": 999},
            EffectReconciliationErrorCode.OBSERVATION_VERSION_MISMATCH,
        ),
        (
            {"attempt": 999},
            EffectReconciliationErrorCode.OBSERVATION_ATTEMPT_MISMATCH,
        ),
    ],
)
def test_observation_coordinates_are_revalidated_fail_closed(
    changes: dict[str, object],
    code: EffectReconciliationErrorCode,
) -> None:
    record = _finalized(EffectState.UNKNOWN)
    observation = replace(
        _observation(record, ReconciliationObservationDisposition.COMMITTED),
        **changes,
    )

    with pytest.raises(EffectReconciliationError) as raised:
        POLICY.prepare_replacement(record=record, observation=observation)
    assert raised.value.code is code
