from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import ActorKind, ActorRef
from backend.agent_runtime.recovery import (
    EffectLedgerError,
    EffectLedgerErrorCode,
    EffectLedgerPort,
    EffectReservationDisposition,
    IdempotencyIdentity,
    IdempotencyKeyFingerprint,
    IdempotencyPolicy,
    IntentFingerprint,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant
from tests.support.effect_ledger_fakes import InMemoryEffectLedgerFake

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(minutes=1))


def _identity() -> IdempotencyIdentity:
    return IdempotencyIdentity(
        principal=ActorRef(ActorKind.AGENT, "AG-03"),
        run_id="run-atomic",
        step_id="step-atomic",
        capability_id=CapabilityId("CAP-T02"),
        execution_route=CapabilityExecutionRoute.UTILITY,
        target_id="tool.render_document",
        operation="render",
        intent_fingerprint=IntentFingerprint.from_value("atomic intent"),
        caller_key_fingerprint=IdempotencyKeyFingerprint.from_key("atomic-key"),
    )


def test_fake_implements_the_provider_neutral_port() -> None:
    assert isinstance(InMemoryEffectLedgerFake(), EffectLedgerPort)


def test_two_concurrent_reservations_create_exactly_one_record() -> None:
    ledger = InMemoryEffectLedgerFake()
    identity = _identity()

    def reserve():
        return ledger.reserve(
            identity=identity,
            now=NOW,
            reservation_expires_at=LATER,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: reserve(), range(2)))

    dispositions = tuple(result.disposition for result in results)
    assert dispositions.count(EffectReservationDisposition.RESERVED_NEW) == 1
    assert dispositions.count(EffectReservationDisposition.DUPLICATE_ACTIVE) == 1
    stored = ledger.get(record_id=identity.record_id)
    assert stored is not None
    assert stored.version == 1


def test_compare_and_set_accepts_current_version_and_rejects_stale_version() -> None:
    policy = IdempotencyPolicy()
    ledger = InMemoryEffectLedgerFake(policy)
    identity = _identity()
    reserved = ledger.reserve(
        identity=identity,
        now=NOW,
        reservation_expires_at=LATER,
    ).record
    assert reserved is not None
    started = policy.prepare_start(record=reserved, attempt=1, now=NOW)

    assert ledger.compare_and_set(
        record_id=reserved.record_id,
        expected_version=1,
        replacement=started,
    ) is started
    with pytest.raises(EffectLedgerError) as raised:
        ledger.compare_and_set(
            record_id=reserved.record_id,
            expected_version=1,
            replacement=started,
        )
    assert raised.value.code is EffectLedgerErrorCode.VERSION_CONFLICT


def test_collision_index_blocks_same_scoped_key_with_different_intent() -> None:
    ledger = InMemoryEffectLedgerFake()
    identity = _identity()
    ledger.reserve(identity=identity, now=NOW)
    conflicting = IdempotencyIdentity(
        principal=identity.principal,
        run_id=identity.run_id,
        step_id=identity.step_id,
        capability_id=CapabilityId("CAP-T03"),
        execution_route=identity.execution_route,
        target_id="tool.convert_format",
        operation="convert",
        intent_fingerprint=IntentFingerprint.from_value("other intent"),
        caller_key_fingerprint=identity.caller_key_fingerprint,
    )

    result = ledger.reserve(identity=conflicting, now=NOW)

    assert result.disposition is EffectReservationDisposition.COLLISION
    assert result.record is None
