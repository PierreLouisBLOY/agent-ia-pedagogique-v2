import pytest

from backend.agent_runtime.contracts import EffectState
from backend.agent_runtime.recovery import (
    ReconciliationObservationDisposition,
    ReplayGuardDisposition,
)
from tests.e2e.core.transverse_adapters import (
    SafeTransverseReport,
    effect_record,
    fixture,
    observe_scn06,
    observe_scn08,
    promotion_identity,
    reconcile_promotion,
)


def test_f_uses_existing_golden_fixtures_without_extending_corpus() -> None:
    assert fixture("SCN-02").fixture_ref.value == "fixture.scn-02"
    assert fixture("SCN-03").adversarial_marker_ref is not None
    assert fixture("SCN-08").adversarial_marker_ref is not None


def test_cap_a02_identity_uses_canonical_application_route_and_caller_key() -> None:
    identity = promotion_identity()

    assert identity.capability_id.value == "CAP-A02"
    assert identity.target_id == "application.request_promotion"
    assert identity.operation == "request_promotion"
    assert identity.record_id.startswith("effect:v1:")
    assert len(identity.caller_key_fingerprint.value) == 64


@pytest.mark.parametrize(
    "state",
    (EffectState.UNKNOWN, EffectState.PARTIAL, EffectState.COMMITTED, EffectState.NONE),
)
def test_promotion_effect_records_are_owned_by_canonical_ledger_model(
    state: EffectState,
) -> None:
    record = effect_record(state)

    assert record.identity == promotion_identity()
    assert record.effect_state is state
    assert record.attempt == 1
    assert record.version == 3


def test_unknown_reconciliation_witness_counts_probe_not_replay() -> None:
    witness = reconcile_promotion(ReconciliationObservationDisposition.STILL_UNKNOWN)

    assert witness.replay_before.disposition is ReplayGuardDisposition.RECONCILE_FIRST
    assert witness.replay_after.disposition is ReplayGuardDisposition.RECONCILE_FIRST
    assert witness.probe_call_count == 1
    assert witness.executor_call_count == 0


def test_functional_projections_are_closed_and_deterministic() -> None:
    scn06 = observe_scn06("disabled").projection
    scn08 = observe_scn08("disabled").projection

    assert scn06.evaluation_verdict == "PASS"
    assert scn06.candidate_state == "candidate"
    assert scn08.evaluation_verdict == "PASS"
    assert scn08.gate_disposition == "APPROVED"
    assert scn08.promotion_route_call_count == 1


def test_safe_report_rejects_raw_or_unbounded_fields() -> None:
    with pytest.raises(ValueError, match="closed code"):
        SafeTransverseReport("SCN-02", "raw hostile text", "NONE", True, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="non-negative"):
        SafeTransverseReport("SCN-02", "ISOLATE", "NONE", True, -1, 0, 0, 0)
