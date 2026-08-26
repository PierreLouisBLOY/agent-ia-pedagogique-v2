from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import ActorKind, ActorRef, EffectState
from backend.agent_runtime.recovery import (
    EffectAttemptRecord,
    EffectLedgerError,
    EffectLedgerErrorCode,
    EffectLedgerLifecycle,
    EffectReservationDisposition,
    IdempotencyIdentity,
    IdempotencyKeyFingerprint,
    IdempotencyPolicy,
    IntentFingerprint,
    ReconciliationStatus,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
SOON = Instant(NOW.value + timedelta(seconds=30))
LATER = Instant(NOW.value + timedelta(minutes=1))
POLICY = IdempotencyPolicy()


def _identity(**changes: object) -> IdempotencyIdentity:
    values: dict[str, object] = {
        "principal": ActorRef(ActorKind.AGENT, "AG-03"),
        "run_id": "run-1",
        "step_id": "step-1",
        "capability_id": CapabilityId("CAP-T02"),
        "execution_route": CapabilityExecutionRoute.UTILITY,
        "target_id": "tool.render_document",
        "operation": "render",
        "intent_fingerprint": IntentFingerprint.from_value("intent"),
        "caller_key_fingerprint": IdempotencyKeyFingerprint.from_key("key"),
    }
    values.update(changes)
    return IdempotencyIdentity(**values)  # type: ignore[arg-type]


def _reserved(identity: IdempotencyIdentity | None = None):
    return POLICY.new_reservation(
        identity=identity or _identity(),
        now=NOW,
        reservation_expires_at=LATER,
    )


def _started():
    return POLICY.prepare_start(record=_reserved(), attempt=1, now=SOON)


def test_new_reservation_is_version_one_and_has_no_attempt() -> None:
    record = _reserved()
    result = POLICY.new_reservation_result(record)

    assert record.lifecycle is EffectLedgerLifecycle.RESERVED
    assert record.version == 1
    assert record.effect_state is EffectState.NONE
    assert record.attempt == 0
    assert result.disposition is EffectReservationDisposition.RESERVED_NEW


def test_same_reserved_or_in_progress_identity_is_duplicate_active() -> None:
    reserved = _reserved()
    started = POLICY.prepare_start(record=reserved, attempt=1, now=SOON)

    assert POLICY.classify_reservation(
        identity=reserved.identity, existing=reserved, now=SOON
    ).disposition is EffectReservationDisposition.DUPLICATE_ACTIVE
    assert POLICY.classify_reservation(
        identity=started.identity, existing=started, now=SOON
    ).disposition is EffectReservationDisposition.DUPLICATE_ACTIVE


def test_start_uses_cas_version_and_marks_effect_unknown() -> None:
    reserved = _reserved()
    started = POLICY.prepare_start(record=reserved, attempt=1, now=SOON)

    assert started.version == 2
    assert started.lifecycle is EffectLedgerLifecycle.IN_PROGRESS
    assert started.effect_state is EffectState.UNKNOWN
    assert started.reconciliation_status is ReconciliationStatus.PENDING
    assert started.attempt == 1


@pytest.mark.parametrize("effect_state", [EffectState.NONE, EffectState.COMMITTED])
def test_known_finalized_duplicate_never_requests_a_second_effect(
    effect_state: EffectState,
) -> None:
    finalized = POLICY.prepare_finalize(
        record=_started(),
        effect_state=effect_state,
        now=LATER,
        result_refs=("result-1",),
        error_code=("KNOWN_FAILURE" if effect_state is EffectState.NONE else None),
    )
    result = POLICY.classify_reservation(
        identity=finalized.identity,
        existing=finalized,
        now=LATER,
    )

    assert finalized.version == 3
    assert result.disposition is EffectReservationDisposition.DUPLICATE_FINALIZED
    assert result.record is finalized


@pytest.mark.parametrize("effect_state", [EffectState.UNKNOWN, EffectState.PARTIAL])
def test_unknown_and_partial_duplicates_require_reconciliation(
    effect_state: EffectState,
) -> None:
    finalized = POLICY.prepare_finalize(
        record=_started(),
        effect_state=effect_state,
        now=LATER,
    )

    assert finalized.reconciliation_status is ReconciliationStatus.PENDING
    assert POLICY.classify_reservation(
        identity=finalized.identity, existing=finalized, now=LATER
    ).disposition is EffectReservationDisposition.RECONCILIATION_REQUIRED


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("intent_fingerprint", IntentFingerprint.from_value("other")),
        ("capability_id", CapabilityId("CAP-T03")),
        ("execution_route", CapabilityExecutionRoute.APPLICATION),
        ("target_id", "application.export_artifact"),
        ("operation", "export"),
    ],
)
def test_same_scoped_caller_key_with_different_intent_is_collision(
    change: str, value: object
) -> None:
    existing = _reserved()
    requested = _identity(**{change: value})

    assert requested.collision_key == existing.identity.collision_key
    result = POLICY.classify_reservation(
        identity=requested,
        existing=existing,
        now=SOON,
    )
    assert result.disposition is EffectReservationDisposition.COLLISION
    assert result.record is None


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("principal", ActorRef(ActorKind.AGENT, "AG-04")),
        ("run_id", "run-2"),
        ("step_id", "step-2"),
    ],
)
def test_principal_run_and_step_partition_collision_scope(
    change: str, value: object
) -> None:
    assert _identity(**{change: value}).collision_key != _identity().collision_key


def test_unrelated_record_cannot_be_misclassified_as_a_scoped_collision() -> None:
    existing = _reserved()

    with pytest.raises(EffectLedgerError) as raised:
        POLICY.classify_reservation(
            identity=_identity(run_id="run-2"),
            existing=existing,
            now=SOON,
        )
    assert raised.value.code is EffectLedgerErrorCode.INVALID_RECORD


def test_expired_reserved_requires_explicit_abandon_cas() -> None:
    reserved = _reserved()

    result = POLICY.classify_reservation(
        identity=reserved.identity,
        existing=reserved,
        now=LATER,
    )
    abandoned = POLICY.prepare_abandon(record=reserved, now=LATER)

    assert result.disposition is EffectReservationDisposition.RESERVATION_EXPIRED
    assert abandoned.lifecycle is EffectLedgerLifecycle.ABANDONED
    assert abandoned.version == 2
    assert POLICY.classify_reservation(
        identity=abandoned.identity, existing=abandoned, now=LATER
    ).disposition is EffectReservationDisposition.ABANDONED
    with pytest.raises(EffectLedgerError) as raised:
        POLICY.prepare_start(record=abandoned, attempt=1, now=LATER)
    assert raised.value.code is EffectLedgerErrorCode.RESERVATION_NOT_ACTIVE


def test_in_progress_expiry_never_resets_or_abandons() -> None:
    started = _started()

    assert POLICY.classify_reservation(
        identity=started.identity, existing=started, now=LATER
    ).disposition is EffectReservationDisposition.RECONCILIATION_REQUIRED
    with pytest.raises(EffectLedgerError) as raised:
        POLICY.prepare_abandon(record=started, now=LATER)
    assert raised.value.code is EffectLedgerErrorCode.RESERVATION_NOT_ACTIVE


def test_stale_version_and_forged_replacement_fail_closed() -> None:
    reserved = _reserved()
    started = POLICY.prepare_start(record=reserved, attempt=1, now=SOON)

    with pytest.raises(EffectLedgerError) as stale:
        POLICY.validate_compare_and_set(
            current=reserved,
            expected_version=0,
            replacement=started,
        )
    assert stale.value.code is EffectLedgerErrorCode.VERSION_CONFLICT
    with pytest.raises(EffectLedgerError) as forged:
        POLICY.validate_compare_and_set(
            current=reserved,
            expected_version=1,
            replacement=replace(started, version=99),
        )
    assert forged.value.code is EffectLedgerErrorCode.VERSION_CONFLICT


def test_finalized_cannot_be_reopened_and_attempt_lineage_cannot_be_rewritten() -> None:
    finalized = POLICY.prepare_finalize(
        record=_started(),
        effect_state=EffectState.NONE,
        now=LATER,
        error_code="KNOWN_FAILURE",
    )
    reopened_attempt = EffectAttemptRecord(
        attempt=1,
        started_at=NOW,
        effect_state=EffectState.UNKNOWN,
    )
    reopened = replace(
        finalized,
        version=4,
        lifecycle=EffectLedgerLifecycle.IN_PROGRESS,
        effect_state=EffectState.UNKNOWN,
        reconciliation_status=ReconciliationStatus.PENDING,
        updated_at=LATER,
        attempts=(reopened_attempt,),
    )

    with pytest.raises(EffectLedgerError) as raised:
        POLICY.validate_compare_and_set(
            current=finalized,
            expected_version=3,
            replacement=reopened,
        )
    assert raised.value.code is EffectLedgerErrorCode.INVALID_TRANSITION


def test_error_messages_never_expose_identity_or_raw_key() -> None:
    identity = _identity()

    with pytest.raises(EffectLedgerError) as raised:
        POLICY.prepare_start(record=_reserved(identity), attempt=2, now=SOON)
    message = str(raised.value)
    assert identity.run_id not in message
    assert "key" not in message
