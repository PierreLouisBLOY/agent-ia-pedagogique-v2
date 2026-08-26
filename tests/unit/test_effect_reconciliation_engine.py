from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    EffectReconciliationDisposition,
    EffectReconciliationEngine,
    EffectReconciliationError,
    EffectReconciliationErrorCode,
    EffectReconciliationPolicy,
    EffectReconciliationRequest,
    IdempotencyPolicy,
    ReconciliationObservation,
    ReconciliationObservationDisposition,
    ReconciliationStatus,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.shared_kernel.time import Instant
from tests.support.effect_ledger_fakes import InMemoryEffectLedgerFake
from tests.support.reconciliation_fakes import (
    RecordingApplicationEffectProbe,
    RecordingToolEffectProbe,
    make_finalized_record,
    make_identity,
    make_in_progress_record,
)

NOW = Instant(datetime(2026, 8, 27, 9, 0, tzinfo=UTC))
FINISHED = Instant(NOW.value + timedelta(seconds=20))
LEASE_END = Instant(NOW.value + timedelta(minutes=1))
AFTER_EXPIRY = Instant(NOW.value + timedelta(minutes=2))
POLICY = EffectReconciliationPolicy()


def _observation(record) -> ReconciliationObservation:
    return ReconciliationObservation(
        record_id=record.record_id,
        record_version=record.version,
        attempt=max(1, record.attempt),
        disposition=ReconciliationObservationDisposition.COMMITTED,
        observed_result_refs=("confirmed-ref",),
        observed_at=AFTER_EXPIRY,
    )


def _engine(record, tool_probe=None, application_probe=None):
    tool = tool_probe or RecordingToolEffectProbe(_observation(record))
    application = application_probe or RecordingApplicationEffectProbe(
        _observation(record)
    )
    ledger = InMemoryEffectLedgerFake(
        initial_records=(record,),
        cas_validator=POLICY.validate_compare_and_set,
    )
    return EffectReconciliationEngine(ledger, tool, application), ledger, tool, application


@pytest.mark.parametrize("effect_state", [EffectState.NONE, EffectState.COMMITTED])
def test_known_finalized_record_returns_not_required_without_probe(
    effect_state: EffectState,
) -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=effect_state,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )
    engine, _, tool, application = _engine(record)

    result = engine.reconcile(
        request=EffectReconciliationRequest(record.record_id, record.version),
        now=AFTER_EXPIRY,
    )

    assert result.disposition is EffectReconciliationDisposition.NOT_REQUIRED
    assert result.current_version == record.version
    assert tool.calls == []
    assert application.calls == []


@pytest.mark.parametrize("abandoned", [False, True])
def test_reserved_or_abandoned_record_returns_not_eligible_without_probe(
    abandoned: bool,
) -> None:
    idempotency = IdempotencyPolicy()
    record = idempotency.new_reservation(
        identity=make_identity(CapabilityExecutionRoute.UTILITY),
        now=NOW,
        reservation_expires_at=LEASE_END,
    )
    if abandoned:
        record = idempotency.prepare_abandon(record=record, now=AFTER_EXPIRY)
    engine, _, tool, application = _engine(record)

    result = engine.reconcile(
        request=EffectReconciliationRequest(record.record_id, record.version),
        now=AFTER_EXPIRY,
    )

    assert result.disposition is EffectReconciliationDisposition.NOT_ELIGIBLE
    assert tool.calls == []
    assert application.calls == []


def test_unknown_record_fails_before_probe() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )
    tool = RecordingToolEffectProbe(_observation(record))
    application = RecordingApplicationEffectProbe(_observation(record))
    ledger = InMemoryEffectLedgerFake(
        cas_validator=POLICY.validate_compare_and_set,
    )
    engine = EffectReconciliationEngine(ledger, tool, application, POLICY)

    with pytest.raises(EffectReconciliationError) as raised:
        engine.reconcile(
            request=EffectReconciliationRequest(record.record_id, record.version),
            now=AFTER_EXPIRY,
        )
    assert raised.value.code is EffectReconciliationErrorCode.UNKNOWN_RECORD
    assert tool.calls == []
    assert application.calls == []


def test_manual_required_returns_without_automatic_probe() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
        reconciliation_status=ReconciliationStatus.MANUAL_REQUIRED,
    )
    engine, _, tool, application = _engine(record)

    result = engine.reconcile(
        request=EffectReconciliationRequest(record.record_id, record.version),
        now=AFTER_EXPIRY,
    )

    assert result.disposition is EffectReconciliationDisposition.MANUAL_REQUIRED
    assert tool.calls == []
    assert application.calls == []


def test_active_in_progress_record_fails_without_probe() -> None:
    record = make_in_progress_record(
        route=CapabilityExecutionRoute.UTILITY,
        created_at=NOW,
        expires_at=LEASE_END,
    )
    engine, _, tool, application = _engine(record)

    with pytest.raises(EffectReconciliationError) as raised:
        engine.reconcile(
            request=EffectReconciliationRequest(record.record_id, record.version),
            now=NOW,
        )
    assert raised.value.code is EffectReconciliationErrorCode.RECORD_STILL_ACTIVE
    assert tool.calls == []
    assert application.calls == []


def test_stale_request_version_fails_before_probe() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )
    engine, _, tool, application = _engine(record)

    with pytest.raises(EffectReconciliationError) as raised:
        engine.reconcile(
            request=EffectReconciliationRequest(record.record_id, record.version - 1),
            now=AFTER_EXPIRY,
        )
    assert raised.value.code is EffectReconciliationErrorCode.VERSION_MISMATCH
    assert tool.calls == []
    assert application.calls == []


@pytest.mark.parametrize(
    "route",
    [CapabilityExecutionRoute.AGENT, CapabilityExecutionRoute.RUNTIME],
)
def test_unsupported_routes_fail_without_calling_either_probe(
    route: CapabilityExecutionRoute,
) -> None:
    record = make_finalized_record(
        route=route,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )
    engine, _, tool, application = _engine(record)

    with pytest.raises(EffectReconciliationError) as raised:
        engine.reconcile(
            request=EffectReconciliationRequest(record.record_id, record.version),
            now=AFTER_EXPIRY,
        )
    assert raised.value.code is EffectReconciliationErrorCode.UNSUPPORTED_ROUTE
    assert tool.calls == []
    assert application.calls == []


def test_probe_failure_does_not_mutate_ledger_or_retry() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )
    probe = RecordingToolEffectProbe(_observation(record), error=RuntimeError("boom"))
    engine, ledger, tool, application = _engine(record, tool_probe=probe)

    with pytest.raises(EffectReconciliationError) as raised:
        engine.reconcile(
            request=EffectReconciliationRequest(record.record_id, record.version),
            now=AFTER_EXPIRY,
        )
    assert raised.value.code is EffectReconciliationErrorCode.PROBE_FAILED
    assert len(tool.calls) == 1
    assert application.calls == []
    assert ledger.get(record_id=record.record_id) == record


def test_probe_returning_untyped_observation_fails_without_write() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )

    class InvalidToolProbe:
        def __init__(self) -> None:
            self.calls = 0

        def probe(self, *, request):
            self.calls += 1
            return {"raw": "provider response"}

    probe = InvalidToolProbe()
    application = RecordingApplicationEffectProbe(_observation(record))
    ledger = InMemoryEffectLedgerFake(
        initial_records=(record,),
        cas_validator=POLICY.validate_compare_and_set,
    )
    engine = EffectReconciliationEngine(ledger, probe, application, POLICY)  # type: ignore[arg-type]

    with pytest.raises(EffectReconciliationError) as raised:
        engine.reconcile(
            request=EffectReconciliationRequest(record.record_id, record.version),
            now=AFTER_EXPIRY,
        )
    assert raised.value.code is EffectReconciliationErrorCode.INVALID_OBSERVATION
    assert probe.calls == 1
    assert ledger.get(record_id=record.record_id) == record


def test_forged_observation_fails_without_ledger_write() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )
    forged = ReconciliationObservation(
        record_id="effect:v1:" + "f" * 64,
        record_version=record.version,
        attempt=record.attempt,
        disposition=ReconciliationObservationDisposition.COMMITTED,
        observed_result_refs=(),
        observed_at=AFTER_EXPIRY,
    )
    probe = RecordingToolEffectProbe(forged)
    engine, ledger, tool, application = _engine(record, tool_probe=probe)

    with pytest.raises(EffectReconciliationError) as raised:
        engine.reconcile(
            request=EffectReconciliationRequest(record.record_id, record.version),
            now=AFTER_EXPIRY,
        )
    assert raised.value.code is EffectReconciliationErrorCode.OBSERVATION_RECORD_MISMATCH
    assert len(tool.calls) == 1
    assert application.calls == []
    assert ledger.get(record_id=record.record_id) == record
