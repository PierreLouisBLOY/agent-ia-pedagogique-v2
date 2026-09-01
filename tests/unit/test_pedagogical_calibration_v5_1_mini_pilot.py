from __future__ import annotations

from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

import pytest

import tests.calibration.pedagogical.semantic_mini_pilot_v5_1 as mini_pilot
from tests.calibration.pedagogical.scorer_contract_v5 import V5PairwiseDecision
from tests.calibration.pedagogical.semantic_mini_pilot_v5_1 import (
    APPROVED_MINI_PILOT_CEILING_USD,
    EXPECTED_MINI_PILOT_CALL_SPEC_SHA256_BY_ID,
    EXPECTED_MINI_PILOT_TRANSFER_PROJECTION_SHA256_BY_ID,
    LIVE_MICRO_CANARY_CARRY_FORWARD_RECORD,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    MICRO_CANARY_CARRY_FORWARD,
    MINI_PILOT_LOGICAL_CALL_IDS,
    MINI_PILOT_LOGICAL_OBSERVATION_COUNT,
    MINI_PILOT_NEW_CALL_COUNT,
    MINI_PILOT_NEW_CALL_IDS,
    PROPOSED_MINI_PILOT_CEILING_USD,
    V51MiniPilotAuthorization,
    V51MiniPilotGate,
    V51MiniPilotGateError,
    V51MiniPilotGateErrorCode,
    V51MiniPilotSafeObservation,
    V51MiniPilotVerdict,
    build_mini_pilot_call_specs,
    build_mini_pilot_new_calls,
    build_mini_pilot_transfer_envelopes,
    estimate_mini_pilot_budget,
    evaluate_mini_pilot_semantic_gates,
    micro_canary_carry_forward_audit,
    validate_mini_pilot_preparation_offline,
)
from tests.calibration.pedagogical.semantic_parser_adapter_v5_1 import (
    EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
)

ROOT = Path(__file__).resolve().parents[2]


def _safe_observations() -> dict[str, V51MiniPilotSafeObservation]:
    common = {
        "parser_schema_pass": True,
        "evidence_first_present": True,
        "transfer_provenance_pass": True,
    }
    return {
        MINI_PILOT_LOGICAL_CALL_IDS[0]: V51MiniPilotSafeObservation(
            call_id=MINI_PILOT_LOGICAL_CALL_IDS[0], score_level=4, **common
        ),
        MINI_PILOT_LOGICAL_CALL_IDS[1]: V51MiniPilotSafeObservation(
            call_id=MINI_PILOT_LOGICAL_CALL_IDS[1], score_level=2, **common
        ),
        MINI_PILOT_LOGICAL_CALL_IDS[2]: V51MiniPilotSafeObservation(
            call_id=MINI_PILOT_LOGICAL_CALL_IDS[2], score_level=1, **common
        ),
        MINI_PILOT_LOGICAL_CALL_IDS[3]: V51MiniPilotSafeObservation(
            call_id=MINI_PILOT_LOGICAL_CALL_IDS[3],
            pairwise_decision=V5PairwiseDecision.A_BETTER,
            **common,
        ),
        MINI_PILOT_LOGICAL_CALL_IDS[4]: V51MiniPilotSafeObservation(
            call_id=MINI_PILOT_LOGICAL_CALL_IDS[4],
            pairwise_decision=V5PairwiseDecision.A_BETTER,
            **common,
        ),
    }


def _authorization(*, live: bool = True) -> V51MiniPilotAuthorization:
    identities = build_mini_pilot_call_specs()
    return V51MiniPilotAuthorization(
        baseline_commit_sha="a" * 40,
        parser_v5_1_sha256=EXPECTED_V5_1_PARSER_CONTRACT_SHA256,
        scorer_contract_sha256=identities[0].scorer_contract_sha256,
        matrix_sha256=identities[0].matrix_sha256,
        pricing_sha256=identities[0].pricing_sha256,
        transfer_scope_sha256=identities[0].transfer_scope_sha256,
        call_spec_sha256_by_id=tuple(
            (item.call_id, item.sha256()) for item in identities
        ),
        transfer_projection_sha256_by_id=tuple(
            (item.call_id, item.transfer_projection_sha256) for item in identities
        ),
        approved_ceiling_usd=PROPOSED_MINI_PILOT_CEILING_USD,
        maximum_new_call_count=MINI_PILOT_NEW_CALL_COUNT,
        provider="anthropic",
        live_provider_recalibration_authorized=live,
    )


def test_mini_pilot_selection_is_the_exact_methodological_minimum() -> None:
    calls = build_mini_pilot_new_calls()
    assert MINI_PILOT_LOGICAL_OBSERVATION_COUNT == 5
    assert MINI_PILOT_NEW_CALL_COUNT == len(calls) == 4
    assert len(MINI_PILOT_LOGICAL_CALL_IDS) == 5
    assert tuple(item.call.call_id for item in calls) == MINI_PILOT_NEW_CALL_IDS
    assert {item.call.scenario_code for item in calls} == {"SCN-01", "SCN-06"}
    assert sum(".mixed." in item.call.call_id for item in calls) == 1
    assert sum(".weak." in item.call.call_id for item in calls) == 1
    assert sum(item.expected_pairwise_decision is not None for item in calls) == 2


def test_micro_canary_carry_forward_satisfies_every_strict_identity() -> None:
    audit = micro_canary_carry_forward_audit()
    assert MICRO_CANARY_CARRY_FORWARD is True
    assert audit.eligible is True
    assert all(asdict(audit).values())


def test_micro_canary_carry_forward_fails_on_any_drift() -> None:
    cases: tuple[tuple[str, str | int], ...] = (
        ("call_spec_sha256", "0" * 64),
        ("parser_v5_1_sha256", "0" * 64),
        ("scorer_contract_sha256", "0" * 64),
        ("matrix_sha256", "0" * 64),
        ("pricing_sha256", "0" * 64),
        ("transfer_scope_sha256", "0" * 64),
        ("transfer_projection_sha256", "0" * 64),
        ("criterion_ref", "scn-06.quality.assessment-clarity"),
        ("anchor_ref", "anchor:wrong"),
        ("provider", "openai"),
        ("model", "wrong-model"),
        ("max_input_tokens", 7_999),
        ("max_output_tokens", 2_047),
    )
    for field, replacement in cases:
        changed = replace(
            LIVE_MICRO_CANARY_CARRY_FORWARD_RECORD,
            **{field: replacement},
        )
        assert micro_canary_carry_forward_audit(changed).eligible is False


def test_call_spec_and_projection_hashes_are_frozen() -> None:
    identities = build_mini_pilot_call_specs()
    envelopes = build_mini_pilot_transfer_envelopes()
    assert {item.call_id: item.sha256() for item in identities} == (
        EXPECTED_MINI_PILOT_CALL_SPEC_SHA256_BY_ID
    )
    assert {item.call_id: item.transfer_payload_sha256() for item in envelopes} == (
        EXPECTED_MINI_PILOT_TRANSFER_PROJECTION_SHA256_BY_ID
    )
    assert all(item.provider == "anthropic" for item in identities)
    assert all(item.model == "claude-sonnet-5" for item in identities)
    assert all(item.max_output_tokens == 2_048 for item in identities)


def test_budget_is_per_call_exact_and_not_micro_canary_times_four() -> None:
    budget = estimate_mini_pilot_budget()
    assert budget.new_call_count == 4
    assert tuple(item.maximum_input_tokens for item in budget.items) == (
        8_000,
        8_000,
        12_000,
        12_000,
    )
    assert tuple(item.maximum_output_tokens for item in budget.items) == (
        2_048,
        2_048,
        2_048,
        2_048,
    )
    assert tuple(item.maximum_before_margin_usd for item in budget.items) == (
        Decimal("0.036480"),
        Decimal("0.036480"),
        Decimal("0.044480"),
        Decimal("0.044480"),
    )
    assert tuple(item.proposed_ceiling_usd for item in budget.items) == (
        Decimal("0.045600"),
        Decimal("0.045600"),
        Decimal("0.055600"),
        Decimal("0.055600"),
    )
    assert budget.maximum_before_margin_usd == Decimal("0.161920")
    assert budget.safety_margin_usd == Decimal("0.040480")
    assert budget.proposed_ceiling_usd == Decimal("0.202400")
    assert budget.proposed_ceiling_usd != Decimal("0.045600") * 4
    assert budget.approved_ceiling_usd is APPROVED_MINI_PILOT_CEILING_USD is None


def test_semantic_gates_cover_low_mid_high_pairwise_and_provenance() -> None:
    passing = _safe_observations()
    report = evaluate_mini_pilot_semantic_gates(passing)
    assert report.verdict is V51MiniPilotVerdict.PASS
    assert report.strict_low_mid_high is True
    assert report.intermediate_score_present is True
    assert report.pairwise_expected_pass is True
    assert report.false_tie_absent is True
    assert report.evidence_first_pass is True
    assert report.transfer_provenance_pass is True

    incomplete = evaluate_mini_pilot_semantic_gates(
        {key: value for key, value in passing.items() if key != MINI_PILOT_LOGICAL_CALL_IDS[-1]}
    )
    assert incomplete.verdict is V51MiniPilotVerdict.INCONCLUSIVE

    inverted = dict(passing)
    inverted[MINI_PILOT_LOGICAL_CALL_IDS[2]] = replace(
        inverted[MINI_PILOT_LOGICAL_CALL_IDS[2]], score_level=3
    )
    failed = evaluate_mini_pilot_semantic_gates(inverted)
    assert failed.verdict is V51MiniPilotVerdict.FAIL
    assert "LOW_MID_HIGH_ORDER" in failed.failures

    tied = dict(passing)
    tied[MINI_PILOT_LOGICAL_CALL_IDS[3]] = replace(
        tied[MINI_PILOT_LOGICAL_CALL_IDS[3]],
        pairwise_decision=V5PairwiseDecision.TIE,
    )
    tie_report = evaluate_mini_pilot_semantic_gates(tied)
    assert "FALSE_TIE" in tie_report.failures


def test_live_gate_is_closed_and_future_sequence_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = V51MiniPilotGate()
    authorization = _authorization()
    with pytest.raises(V51MiniPilotGateError) as closed:
        gate.authorize_next_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=authorization,
            call_id=MINI_PILOT_NEW_CALL_IDS[0],
            completed_new_call_ids=(),
            safe_observations={},
        )
    assert closed.value.code is V51MiniPilotGateErrorCode.LIVE_EXECUTION_FORBIDDEN

    monkeypatch.setattr(mini_pilot, "LIVE_PROVIDER_RECALIBRATION_AUTHORIZED", True)
    first = gate.authorize_next_before_credentials(
        observed_baseline_commit_sha="a" * 40,
        authorization=authorization,
        call_id=MINI_PILOT_NEW_CALL_IDS[0],
        completed_new_call_ids=(),
        safe_observations={},
    )
    assert first.call_id == MINI_PILOT_NEW_CALL_IDS[0]

    with pytest.raises(V51MiniPilotGateError) as fanout:
        gate.authorize_next_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=authorization,
            call_id=MINI_PILOT_NEW_CALL_IDS[1],
            completed_new_call_ids=(),
            safe_observations={},
        )
    assert fanout.value.code is V51MiniPilotGateErrorCode.CALL_ORDER_INVALID

    observations = _safe_observations()
    second = gate.authorize_next_before_credentials(
        observed_baseline_commit_sha="a" * 40,
        authorization=authorization,
        call_id=MINI_PILOT_NEW_CALL_IDS[1],
        completed_new_call_ids=MINI_PILOT_NEW_CALL_IDS[:1],
        safe_observations=observations,
    )
    assert second.call_id == MINI_PILOT_NEW_CALL_IDS[1]

    broken = dict(observations)
    broken[MINI_PILOT_NEW_CALL_IDS[1]] = replace(
        broken[MINI_PILOT_NEW_CALL_IDS[1]], score_level=3
    )
    with pytest.raises(V51MiniPilotGateError) as semantic:
        gate.authorize_next_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=authorization,
            call_id=MINI_PILOT_NEW_CALL_IDS[2],
            completed_new_call_ids=MINI_PILOT_NEW_CALL_IDS[:2],
            safe_observations=broken,
        )
    assert semantic.value.code is V51MiniPilotGateErrorCode.SEMANTIC_GATE_FAILED

    with pytest.raises(V51MiniPilotGateError) as rerun:
        gate.authorize_next_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=authorization,
            call_id=MINI_PILOT_NEW_CALL_IDS[0],
            completed_new_call_ids=MINI_PILOT_NEW_CALL_IDS[:1],
            safe_observations=observations,
        )
    assert rerun.value.code is V51MiniPilotGateErrorCode.CALL_ALREADY_COMPLETED


def test_offline_preparation_has_no_provider_boundary() -> None:
    validate_mini_pilot_preparation_offline()
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
    source = (
        ROOT
        / "tests/calibration/pedagogical/semantic_mini_pilot_v5_1.py"
    ).read_text(encoding="utf-8")
    assert all(
        marker not in source
        for marker in (
            "EnvironmentProviderSecretResolver",
            "ProviderCredentialRef",
            "AnthropicSDKScoringTransport",
            "OpenAI",
            "httpx",
            "requests",
        )
    )
