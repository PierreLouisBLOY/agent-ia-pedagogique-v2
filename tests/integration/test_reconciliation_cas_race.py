from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    EffectLedgerSnapshotRef,
    EffectReconciliationEngine,
    EffectReconciliationError,
    EffectReconciliationErrorCode,
    EffectReconciliationPolicy,
    EffectReconciliationRequest,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.effect_ledger_fakes import InMemoryEffectLedgerFake
from tests.support.reconciliation_fakes import (
    RecordingApplicationEffectProbe,
    RecordingToolEffectProbe,
    make_finalized_record,
)

NOW = Instant(datetime(2026, 8, 27, 9, 0, tzinfo=UTC))
FINISHED = Instant(NOW.value + timedelta(seconds=20))
LEASE_END = Instant(NOW.value + timedelta(minutes=1))
OBSERVED = Instant(NOW.value + timedelta(minutes=2))


def _observation(record, disposition):
    return ReconciliationObservation(
        record_id=record.record_id,
        record_version=record.version,
        attempt=record.attempt,
        disposition=disposition,
        observed_result_refs=(),
        observed_at=OBSERVED,
    )


def test_cas_race_after_probe_never_overwrites_newer_record_or_reprobes() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )
    policy = EffectReconciliationPolicy()
    ledger = InMemoryEffectLedgerFake(
        initial_records=(record,),
        cas_validator=policy.validate_compare_and_set,
    )
    racer_replacement = policy.prepare_replacement(
        record=record,
        observation=_observation(
            record,
            ReconciliationObservationDisposition.STILL_UNKNOWN,
        ),
    )

    def win_race() -> None:
        ledger.compare_and_set(
            record_id=record.record_id,
            expected_version=record.version,
            replacement=racer_replacement,
        )

    primary = _observation(record, ReconciliationObservationDisposition.COMMITTED)
    tool = RecordingToolEffectProbe(primary, on_probe=win_race)
    application = RecordingApplicationEffectProbe(primary)
    engine = EffectReconciliationEngine(ledger, tool, application, policy)

    with pytest.raises(EffectReconciliationError) as raised:
        engine.reconcile(
            request=EffectReconciliationRequest(record.record_id, record.version),
            now=OBSERVED,
        )
    assert raised.value.code is EffectReconciliationErrorCode.LEDGER_VERSION_CONFLICT
    assert len(tool.calls) == 1
    assert application.calls == []
    assert ledger.get(record_id=record.record_id) == racer_replacement


def test_stale_snapshot_ledger_version_fails_before_probe() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )
    stale_ref = EffectLedgerSnapshotRef(record.record_id, record.version - 1)
    observation = _observation(
        record,
        ReconciliationObservationDisposition.COMMITTED,
    )
    tool = RecordingToolEffectProbe(observation)
    application = RecordingApplicationEffectProbe(observation)
    policy = EffectReconciliationPolicy()
    ledger = InMemoryEffectLedgerFake(
        initial_records=(record,),
        cas_validator=policy.validate_compare_and_set,
    )
    engine = EffectReconciliationEngine(ledger, tool, application, policy)

    with pytest.raises(EffectReconciliationError) as raised:
        engine.reconcile(
            request=EffectReconciliationRequest(
                stale_ref.record_id,
                stale_ref.version,
            ),
            now=OBSERVED,
        )
    assert raised.value.code is EffectReconciliationErrorCode.VERSION_MISMATCH
    assert tool.calls == []
    assert application.calls == []
    assert ledger.get(record_id=record.record_id) == record
