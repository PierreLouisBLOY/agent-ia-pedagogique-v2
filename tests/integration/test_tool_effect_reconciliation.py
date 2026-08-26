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
)

NOW = Instant(datetime(2026, 8, 27, 9, 0, tzinfo=UTC))
FINISHED = Instant(NOW.value + timedelta(seconds=20))
LEASE_END = Instant(NOW.value + timedelta(minutes=1))
OBSERVED = Instant(NOW.value + timedelta(minutes=2))


def test_utility_route_uses_exactly_one_tool_probe_and_updates_ledger() -> None:
    record = make_finalized_record(
        route=CapabilityExecutionRoute.UTILITY,
        effect_state=EffectState.UNKNOWN,
        created_at=NOW,
        expires_at=LEASE_END,
        finalized_at=FINISHED,
        result_refs=("existing-ref",),
    )
    observation = ReconciliationObservation(
        record_id=record.record_id,
        record_version=record.version,
        attempt=record.attempt,
        disposition=ReconciliationObservationDisposition.COMMITTED,
        observed_result_refs=("existing-ref", "confirmed-ref"),
        observed_at=OBSERVED,
        observation_code="TOOL_EFFECT_CONFIRMED",
    )
    tool = RecordingToolEffectProbe(observation)
    application = RecordingApplicationEffectProbe(observation)
    policy = EffectReconciliationPolicy()
    ledger = InMemoryEffectLedgerFake(
        initial_records=(record,),
        cas_validator=policy.validate_compare_and_set,
    )
    engine = EffectReconciliationEngine(ledger, tool, application, policy)

    result = engine.reconcile(
        request=EffectReconciliationRequest(record.record_id, record.version),
        now=OBSERVED,
    )

    assert result.disposition is EffectReconciliationDisposition.RECONCILED
    assert result.record.effect_state is EffectState.COMMITTED
    assert result.record.reconciliation_status is ReconciliationStatus.RESOLVED
    assert result.record.result_refs == ("existing-ref", "confirmed-ref")
    assert result.current_version == record.version + 1
    assert len(tool.calls) == 1
    assert application.calls == []
    request = tool.calls[0]
    assert request.tool_id == record.identity.target_id
    assert request.capability_id == record.identity.capability_id
    assert request.intent_fingerprint == record.identity.intent_fingerprint
    assert ledger.get(record_id=record.record_id) == result.record
