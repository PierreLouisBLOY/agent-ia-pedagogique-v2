from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    EffectReconciliationDisposition,
    EffectReconciliationEngine,
    EffectReconciliationPolicy,
    EffectReconciliationRequest,
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
    make_in_progress_record,
)

NOW = Instant(datetime(2026, 8, 27, 9, 0, tzinfo=UTC))
FINISHED = Instant(NOW.value + timedelta(seconds=20))
LEASE_END = Instant(NOW.value + timedelta(minutes=1))
OBSERVED = Instant(NOW.value + timedelta(minutes=2))


def _engine(record, disposition):
    observation = ReconciliationObservation(
        record_id=record.record_id,
        record_version=record.version,
        attempt=record.attempt,
        disposition=disposition,
        observed_result_refs=("application-result",),
        observed_at=OBSERVED,
        observation_code="APPLICATION_EFFECT_OBSERVED",
    )
    tool = RecordingToolEffectProbe(observation)
    application = RecordingApplicationEffectProbe(observation)
    policy = EffectReconciliationPolicy()
    ledger = InMemoryEffectLedgerFake(
        initial_records=(record,),
        cas_validator=policy.validate_compare_and_set,
    )
    return (
        EffectReconciliationEngine(ledger, tool, application, policy),
        ledger,
        tool,
        application,
    )


def test_application_route_uses_exactly_one_application_probe() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.APPLICATION,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
    )
    engine, ledger, tool, application = _engine(
        record,
        ReconciliationObservationDisposition.NOT_COMMITTED,
    )

    result = engine.reconcile(
        request=EffectReconciliationRequest(record.record_id, record.version),
        now=OBSERVED,
    )

    assert result.disposition is EffectReconciliationDisposition.RECONCILED
    assert result.record.effect_state is EffectState.NONE
    assert result.record.reconciliation_status is ReconciliationStatus.RESOLVED
    assert tool.calls == []
    assert len(application.calls) == 1
    request = application.calls[0]
    assert request.use_case_id == record.identity.target_id
    assert request.capability_id == record.identity.capability_id
    assert ledger.get(record_id=record.record_id) == result.record


def test_expired_application_in_progress_is_closed_as_partial() -> None:
    record = make_in_progress_record(
        route=CapabilityExecutionRoute.APPLICATION,
        created_at=NOW,
        expires_at=LEASE_END,
    )
    engine, _, tool, application = _engine(
        record,
        ReconciliationObservationDisposition.PARTIAL,
    )

    result = engine.reconcile(
        request=EffectReconciliationRequest(record.record_id, record.version),
        now=OBSERVED,
    )

    assert result.record.lifecycle.value == "FINALIZED"
    assert result.record.effect_state is EffectState.PARTIAL
    assert result.record.reconciliation_status is ReconciliationStatus.RESOLVED
    assert result.record.attempts[-1].ended_at == OBSERVED
    assert tool.calls == []
    assert len(application.calls) == 1
