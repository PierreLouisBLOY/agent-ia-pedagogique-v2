from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import ActorKind, ActorRef, EffectState
from backend.agent_runtime.recovery import (
    EffectAttemptRecord,
    EffectLedgerLifecycle,
    EffectLedgerRecord,
    EffectReservationDisposition,
    EffectReservationResult,
    IdempotencyIdentity,
    IdempotencyKeyFingerprint,
    IntentFingerprint,
    ReconciliationStatus,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(minutes=1))


def _identity(**changes: object) -> IdempotencyIdentity:
    values: dict[str, object] = {
        "principal": ActorRef(ActorKind.AGENT, "AG-03"),
        "run_id": "run-1",
        "step_id": "step-1",
        "capability_id": CapabilityId("CAP-T02"),
        "execution_route": CapabilityExecutionRoute.UTILITY,
        "target_id": "tool.render_document",
        "operation": "render",
        "intent_fingerprint": IntentFingerprint.from_value("canonical intent"),
        "caller_key_fingerprint": IdempotencyKeyFingerprint.from_key("caller-key"),
    }
    values.update(changes)
    return IdempotencyIdentity(**values)  # type: ignore[arg-type]


def _record(
    *,
    lifecycle: EffectLedgerLifecycle = EffectLedgerLifecycle.RESERVED,
    effect_state: EffectState = EffectState.NONE,
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.NOT_REQUIRED,
    attempts: tuple[EffectAttemptRecord, ...] = (),
) -> EffectLedgerRecord:
    identity = _identity()
    return EffectLedgerRecord(
        record_id=identity.record_id,
        identity=identity,
        version=1,
        lifecycle=lifecycle,
        effect_state=effect_state,
        reconciliation_status=reconciliation_status,
        created_at=NOW,
        updated_at=NOW,
        reservation_expires_at=LATER,
        attempts=attempts,
    )


def test_fingerprints_are_stable_domain_separated_and_non_reversible_in_models() -> None:
    intent = IntentFingerprint.from_value("same input")
    key = IdempotencyKeyFingerprint.from_key("same input")

    assert intent == IntentFingerprint.from_value(b"same input")
    assert len(intent.value) == 64
    assert intent.value != key.value
    assert "same input" not in repr(intent)
    assert "same input" not in repr(key)


@pytest.mark.parametrize("value", ["", "A" * 64, "g" * 64, "0" * 63])
def test_fingerprint_value_objects_reject_malformed_digests(value: str) -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        IntentFingerprint(value)


def test_fingerprint_input_is_typed_non_empty_and_bounded() -> None:
    with pytest.raises(TypeError, match="str or bytes"):
        IntentFingerprint.from_value(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        IntentFingerprint.from_value("")
    with pytest.raises(ValueError, match="bounded size"):
        IntentFingerprint.from_value(b"x" * 65_537)


def test_identity_is_intention_not_attempt_or_plan_version() -> None:
    names = {field.name for field in fields(IdempotencyIdentity)}

    assert names == {
        "principal",
        "run_id",
        "step_id",
        "capability_id",
        "execution_route",
        "target_id",
        "operation",
        "intent_fingerprint",
        "caller_key_fingerprint",
    }
    assert "attempt" not in names
    assert "plan_version" not in names
    assert "payload" not in names


def test_record_and_collision_ids_are_stable_and_scope_collisions_correctly() -> None:
    identity = _identity()
    changed_intent = _identity(
        intent_fingerprint=IntentFingerprint.from_value("different intent")
    )
    changed_run = _identity(run_id="run-2")

    assert identity.record_id == _identity().record_id
    assert identity.record_id.startswith("effect:v1:")
    assert len(identity.record_id.removeprefix("effect:v1:")) == 64
    assert changed_intent.record_id != identity.record_id
    assert changed_intent.collision_key == identity.collision_key
    assert changed_run.collision_key != identity.collision_key
    assert "caller-key" not in identity.record_id
    assert "caller-key" not in identity.collision_key


@pytest.mark.parametrize("field_name", ["run_id", "step_id", "target_id", "operation"])
def test_identity_rejects_empty_or_unsafe_identifiers(field_name: str) -> None:
    with pytest.raises(ValueError, match="safe non-empty"):
        _identity(**{field_name: "../unsafe"})


def test_attempt_record_requires_contiguous_safe_terminal_data() -> None:
    active = EffectAttemptRecord(
        attempt=1,
        started_at=NOW,
        effect_state=EffectState.UNKNOWN,
    )
    terminal = EffectAttemptRecord(
        attempt=1,
        started_at=NOW,
        ended_at=LATER,
        effect_state=EffectState.NONE,
        error_code="TOOL_TIMEOUT",
    )

    assert active.ended_at is None
    assert terminal.error_code == "TOOL_TIMEOUT"
    with pytest.raises(ValueError, match="active attempt must have UNKNOWN"):
        EffectAttemptRecord(
            attempt=1,
            started_at=NOW,
            effect_state=EffectState.NONE,
        )
    with pytest.raises(ValueError, match="safe closed code"):
        EffectAttemptRecord(
            attempt=1,
            started_at=NOW,
            ended_at=LATER,
            effect_state=EffectState.NONE,
            error_code="raw payload: secret",
        )
    with pytest.raises(ValueError, match="opaque safe identifiers"):
        EffectAttemptRecord(
            attempt=1,
            started_at=NOW,
            ended_at=LATER,
            effect_state=EffectState.COMMITTED,
            result_refs=("C:\\private\\result.txt",),
        )


def test_reserved_and_abandoned_records_have_no_attempt_or_effect() -> None:
    reserved = _record()
    abandoned = _record(lifecycle=EffectLedgerLifecycle.ABANDONED)

    assert reserved.attempt == 0
    assert abandoned.result_refs == ()
    with pytest.raises(ValueError, match="cannot have attempts"):
        _record(
            attempts=(
                EffectAttemptRecord(
                    attempt=1,
                    started_at=NOW,
                    effect_state=EffectState.UNKNOWN,
                ),
            )
        )


def test_in_progress_is_conservatively_unknown_and_pending() -> None:
    attempt = EffectAttemptRecord(
        attempt=1,
        started_at=NOW,
        effect_state=EffectState.UNKNOWN,
    )
    record = _record(
        lifecycle=EffectLedgerLifecycle.IN_PROGRESS,
        effect_state=EffectState.UNKNOWN,
        reconciliation_status=ReconciliationStatus.PENDING,
        attempts=(attempt,),
    )

    assert record.attempt == 1
    with pytest.raises(ValueError, match="UNKNOWN effect"):
        _record(
            lifecycle=EffectLedgerLifecycle.IN_PROGRESS,
            reconciliation_status=ReconciliationStatus.PENDING,
            attempts=(attempt,),
        )


@pytest.mark.parametrize("effect_state", [EffectState.UNKNOWN, EffectState.PARTIAL])
def test_uncertain_finalized_effects_cannot_be_not_required(
    effect_state: EffectState,
) -> None:
    attempt = EffectAttemptRecord(
        attempt=1,
        started_at=NOW,
        ended_at=LATER,
        effect_state=effect_state,
    )

    with pytest.raises(ValueError, match="reconciliation"):
        _record(
            lifecycle=EffectLedgerLifecycle.FINALIZED,
            effect_state=effect_state,
            reconciliation_status=ReconciliationStatus.NOT_REQUIRED,
            attempts=(attempt,),
        )


def test_reservation_result_never_uses_authority_vocabulary() -> None:
    values = {item.value for item in EffectReservationDisposition}

    assert values.isdisjoint({"ALLOW", "REQUEST", "DELEGATE", "APPROVED"})
    with pytest.raises(ValueError, match="must not expose"):
        EffectReservationResult(
            EffectReservationDisposition.COLLISION,
            _record(),
        )
