from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from tests.calibration.pedagogical import semantic_gate_v5_2 as gate_v5_2
from tests.calibration.pedagogical.scorer_contract_v5 import V5PairwiseDecision
from tests.calibration.pedagogical.semantic_gate_v5_2 import (
    APPROVED_V5_2_MINI_PILOT_CEILING_USD,
    EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID,
    EXPECTED_V5_2_GATE_CONTRACT_SHA256,
    EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID,
    INTERMEDIATE_ANCHOR_AVAILABLE,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    MIXED_CALL_ID,
    MIXED_HISTORICAL_RESULT,
    PROPOSED_V5_2_MINI_PILOT_CEILING_USD,
    SCN_01_PAIRWISE_CALL_ID,
    SCN_06_PAIRWISE_CALL_ID,
    STRONG_HISTORICAL_RESULT,
    V5_2_CARRY_FORWARD_CALL_IDS,
    V5_2_EXPECTATION_BY_CALL_ID,
    V5_2_INTERMEDIATE_ANCHOR_PROPOSAL,
    V5_2_LOGICAL_CALL_IDS,
    V5_2_NEW_CALL_IDS,
    WEAK_CALL_ID,
    V52AnchorRole,
    V52Authorization,
    V52GateError,
    V52GateErrorCode,
    V52MiniPilotGate,
    V52SafeObservation,
    V52Verdict,
    audit_intermediate_anchor_availability,
    build_v5_2_call_specs,
    build_v5_2_new_calls,
    build_v5_2_transfer_envelopes,
    carry_forward_audit,
    carry_forward_observations,
    estimate_v5_2_budget,
    evaluate_v5_2_semantic_gate,
    expected_score_from_checks,
    mixed_carry_forward_audit,
    strong_carry_forward_audit,
    v5_2_gate_contract_sha256,
    validate_v5_2_preparation_offline,
)
from tests.calibration.pedagogical.semantic_micro_canary_v5_1 import (
    MICRO_CANARY_CALL_ID,
)

ROOT = Path(__file__).resolve().parents[2]


def _complete_observations() -> dict[str, V52SafeObservation]:
    observations = carry_forward_observations()
    weak_expectation = V5_2_EXPECTATION_BY_CALL_ID[WEAK_CALL_ID]
    observations[WEAK_CALL_ID] = V52SafeObservation(
        call_id=WEAK_CALL_ID,
        parser_schema_pass=True,
        evidence_first_present=True,
        transfer_provenance_pass=True,
        satisfied_check_ids=weak_expectation.expected_semantic_checks,
        score_level=1,
    )
    for call_id in (SCN_06_PAIRWISE_CALL_ID, SCN_01_PAIRWISE_CALL_ID):
        observations[call_id] = V52SafeObservation(
            call_id=call_id,
            parser_schema_pass=True,
            evidence_first_present=True,
            transfer_provenance_pass=True,
            pairwise_decision=V5PairwiseDecision.A_BETTER,
        )
    return observations


def _authorization(
    *,
    live: bool = True,
    ceiling: Decimal | None = PROPOSED_V5_2_MINI_PILOT_CEILING_USD,
) -> V52Authorization:
    identities = build_v5_2_call_specs()
    return V52Authorization(
        baseline_commit_sha="a" * 40,
        gate_contract_sha256=EXPECTED_V5_2_GATE_CONTRACT_SHA256,
        parser_v5_1_sha256=identities[0].parser_v5_1_sha256,
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
        approved_ceiling_usd=ceiling,
        maximum_new_call_count=3,
        provider="anthropic",
        live_provider_recalibration_authorized=live,
    )


def test_expectation_model_is_explicit_versioned_and_provenanced() -> None:
    assert v5_2_gate_contract_sha256() == EXPECTED_V5_2_GATE_CONTRACT_SHA256
    assert tuple(V5_2_EXPECTATION_BY_CALL_ID) == V5_2_LOGICAL_CALL_IDS
    for expectation in V5_2_EXPECTATION_BY_CALL_ID.values():
        assert expectation.anchor_ids
        assert expectation.scenario_code.startswith("SCN-")
        assert expectation.criterion_ref.startswith("scn-")
        assert expectation.human_prevalidation_sources
        assert all(len(item.sha256) == 64 for item in expectation.human_prevalidation_sources)


def test_scn_06_scores_and_order_derive_from_checks_not_roles_or_names() -> None:
    strong = V5_2_EXPECTATION_BY_CALL_ID[MICRO_CANARY_CALL_ID]
    mixed = V5_2_EXPECTATION_BY_CALL_ID[MIXED_CALL_ID]
    weak = V5_2_EXPECTATION_BY_CALL_ID[WEAK_CALL_ID]
    assert mixed.anchor_role is weak.anchor_role is (
        V52AnchorRole.NON_DELIVERABLE_NEGATIVE_CONTROL
    )
    assert (
        expected_score_from_checks(strong),
        expected_score_from_checks(mixed),
        expected_score_from_checks(weak),
    ) == (4, 0, 1)
    ordered = tuple(
        item.call_id
        for item in sorted(
            (strong, mixed, weak),
            key=expected_score_from_checks,
            reverse=True,
        )
    )
    assert ordered == (MICRO_CANARY_CALL_ID, WEAK_CALL_ID, MIXED_CALL_ID)


def test_module_contains_no_tier_name_score_inference() -> None:
    source = (
        ROOT / "tests/calibration/pedagogical/semantic_gate_v5_2.py"
    ).read_text(encoding="utf-8")
    assert 'if ".mixed."' not in source
    assert "if tier" not in source
    assert "expected_score_from_checks" in source


def test_intermediate_anchor_is_not_fabricated_or_selected() -> None:
    audit = audit_intermediate_anchor_availability()
    assert INTERMEDIATE_ANCHOR_AVAILABLE is audit.available is False
    assert audit.reviewed_historical_anchor_count == 24
    assert audit.human_check_validated_intermediate_anchor_ids == ()
    assert audit.proposal is V5_2_INTERMEDIATE_ANCHOR_PROPOSAL
    assert audit.proposal.target_score == len(audit.proposal.target_semantic_checks) == 2
    assert audit.proposal.status == "PROPOSED_REQUIRES_HUMAN_PREVALIDATION"
    assert audit.proposal.proposal_id not in V5_2_LOGICAL_CALL_IDS


def test_strong_and_mixed_carry_forward_use_explicit_versioned_compatibility() -> None:
    for audit in (strong_carry_forward_audit(), mixed_carry_forward_audit()):
        assert audit.historical_call_spec_identical_to_v5_2_gate_identity is False
        assert audit.versioned_compatibility is True
        assert audit.provider_call_spec_equal is True
        assert audit.parser_equal is True
        assert audit.scorer_equal is True
        assert audit.matrix_equal is True
        assert audit.pricing_equal is True
        assert audit.transfer_scope_equal is True
        assert audit.transfer_projection_equal is True
        assert audit.expected_score_match is True
        assert audit.expected_check_count_match is True
        assert audit.provenance_intact is True
        assert audit.eligible is True
    assert V5_2_CARRY_FORWARD_CALL_IDS == (MICRO_CANARY_CALL_ID, MIXED_CALL_ID)


def test_carry_forward_fails_closed_on_identity_result_or_provenance_drift() -> None:
    cases = (
        replace(MIXED_HISTORICAL_RESULT, historical_wrapper_call_spec_sha256="0" * 64),
        replace(MIXED_HISTORICAL_RESULT, provider_call_spec_sha256="0" * 64),
        replace(MIXED_HISTORICAL_RESULT, parser_v5_1_sha256="0" * 64),
        replace(MIXED_HISTORICAL_RESULT, scorer_contract_sha256="0" * 64),
        replace(MIXED_HISTORICAL_RESULT, matrix_sha256="0" * 64),
        replace(MIXED_HISTORICAL_RESULT, pricing_sha256="0" * 64),
        replace(MIXED_HISTORICAL_RESULT, transfer_scope_sha256="0" * 64),
        replace(MIXED_HISTORICAL_RESULT, transfer_projection_sha256="0" * 64),
        replace(MIXED_HISTORICAL_RESULT, model="wrong-model"),
        replace(MIXED_HISTORICAL_RESULT, max_output_tokens=2_047),
        replace(MIXED_HISTORICAL_RESULT, score_level=1),
        replace(MIXED_HISTORICAL_RESULT, transfer_provenance_pass=False),
        replace(MIXED_HISTORICAL_RESULT, parser_schema_status="FAIL"),
        replace(MIXED_HISTORICAL_RESULT, raw_response_persistence="RAW"),
    )
    assert all(carry_forward_audit(item).eligible is False for item in cases)
    assert carry_forward_audit(STRONG_HISTORICAL_RESULT).eligible is True


def test_mini_pilot_selection_hashes_and_two_scenario_coverage_are_exact() -> None:
    calls = build_v5_2_new_calls()
    identities = build_v5_2_call_specs()
    envelopes = build_v5_2_transfer_envelopes()
    assert len(V5_2_LOGICAL_CALL_IDS) == 5
    assert tuple(item.call.call_id for item in calls) == V5_2_NEW_CALL_IDS
    assert {item.call.scenario_code for item in calls} == {"SCN-01", "SCN-06"}
    assert {item.call_id: item.sha256() for item in identities} == (
        EXPECTED_V5_2_CALL_SPEC_SHA256_BY_ID
    )
    assert {item.call_id: item.transfer_payload_sha256() for item in envelopes} == (
        EXPECTED_V5_2_TRANSFER_PROJECTION_SHA256_BY_ID
    )
    assert all(item.provider == "anthropic" for item in identities)
    assert all(item.model == "claude-sonnet-5" for item in identities)


def test_budget_is_recalculated_for_three_new_calls_only() -> None:
    budget = estimate_v5_2_budget()
    assert budget.new_call_count == 3
    assert tuple(item.maximum_input_tokens for item in budget.items) == (
        8_000,
        12_000,
        12_000,
    )
    assert tuple(item.maximum_before_margin_usd for item in budget.items) == (
        Decimal("0.036480"),
        Decimal("0.044480"),
        Decimal("0.044480"),
    )
    assert tuple(item.proposed_ceiling_usd for item in budget.items) == (
        Decimal("0.045600"),
        Decimal("0.055600"),
        Decimal("0.055600"),
    )
    assert budget.maximum_before_margin_usd == Decimal("0.125440")
    assert budget.safety_margin_usd == Decimal("0.031360")
    assert budget.proposed_ceiling_usd == Decimal("0.156800")
    assert budget.proposed_ceiling_usd != Decimal("0.202400")
    assert budget.approved_ceiling_usd is APPROVED_V5_2_MINI_PILOT_CEILING_USD is None


def test_semantic_gate_uses_checks_relations_distribution_and_provenance() -> None:
    passing = _complete_observations()
    report = evaluate_v5_2_semantic_gate(passing)
    assert report.verdict is V52Verdict.PASS
    assert report.semantic_checks_pass is True
    assert report.score_expectations_pass is True
    assert report.pairwise_expectations_pass is True
    assert report.intermediate_anchor_required is False
    assert report.intermediate_score_present is False
    assert report.distribution_non_degenerate is True
    assert report.evidence_first_pass is True
    assert report.transfer_provenance_pass is True

    incomplete = dict(passing)
    incomplete.pop(SCN_01_PAIRWISE_CALL_ID)
    assert evaluate_v5_2_semantic_gate(incomplete).verdict is V52Verdict.INCONCLUSIVE

    wrong_checks = dict(passing)
    wrong_checks[WEAK_CALL_ID] = replace(
        wrong_checks[WEAK_CALL_ID],
        satisfied_check_ids=(),
    )
    check_report = evaluate_v5_2_semantic_gate(wrong_checks)
    assert check_report.verdict is V52Verdict.FAIL
    assert "SEMANTIC_CHECKS" in check_report.failures

    wrong_pairwise = dict(passing)
    wrong_pairwise[SCN_06_PAIRWISE_CALL_ID] = replace(
        wrong_pairwise[SCN_06_PAIRWISE_CALL_ID],
        pairwise_decision=V5PairwiseDecision.TIE,
    )
    pairwise_report = evaluate_v5_2_semantic_gate(wrong_pairwise)
    assert "PAIRWISE_EXPECTATIONS" in pairwise_report.failures


def test_live_gate_is_closed_and_future_sequence_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = V52MiniPilotGate()
    authorization = _authorization()
    with pytest.raises(V52GateError) as closed:
        gate.authorize_next_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=authorization,
            call_id=WEAK_CALL_ID,
            completed_new_call_ids=(),
            new_observations={},
        )
    assert closed.value.code is V52GateErrorCode.LIVE_EXECUTION_FORBIDDEN

    monkeypatch.setattr(gate_v5_2, "LIVE_PROVIDER_RECALIBRATION_AUTHORIZED", True)
    first = gate.authorize_next_before_credentials(
        observed_baseline_commit_sha="a" * 40,
        authorization=authorization,
        call_id=WEAK_CALL_ID,
        completed_new_call_ids=(),
        new_observations={},
    )
    assert first.call_id == WEAK_CALL_ID

    observations = _complete_observations()
    new_only = {call_id: observations[call_id] for call_id in V5_2_NEW_CALL_IDS}
    second = gate.authorize_next_before_credentials(
        observed_baseline_commit_sha="a" * 40,
        authorization=authorization,
        call_id=SCN_06_PAIRWISE_CALL_ID,
        completed_new_call_ids=(WEAK_CALL_ID,),
        new_observations=new_only,
    )
    assert second.call_id == SCN_06_PAIRWISE_CALL_ID

    broken = dict(new_only)
    broken[WEAK_CALL_ID] = replace(broken[WEAK_CALL_ID], score_level=2)
    with pytest.raises(V52GateError) as semantic:
        gate.authorize_next_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=authorization,
            call_id=SCN_06_PAIRWISE_CALL_ID,
            completed_new_call_ids=(WEAK_CALL_ID,),
            new_observations=broken,
        )
    assert semantic.value.code is V52GateErrorCode.SEMANTIC_GATE_FAILED

    with pytest.raises(V52GateError) as order:
        gate.authorize_next_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=authorization,
            call_id=SCN_01_PAIRWISE_CALL_ID,
            completed_new_call_ids=(WEAK_CALL_ID,),
            new_observations=new_only,
        )
    assert order.value.code is V52GateErrorCode.CALL_ORDER_INVALID


def test_gate_rejects_missing_ceiling_and_frozen_identity_drift() -> None:
    gate = V52MiniPilotGate()
    with pytest.raises(V52GateError) as ceiling:
        gate.authorize_next_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=_authorization(ceiling=None),
            call_id=WEAK_CALL_ID,
            completed_new_call_ids=(),
            new_observations={},
        )
    assert ceiling.value.code is V52GateErrorCode.APPROVED_CEILING_MISSING

    drifted = replace(_authorization(), gate_contract_sha256="0" * 64)
    with pytest.raises(V52GateError) as identity:
        gate.authorize_next_before_credentials(
            observed_baseline_commit_sha="a" * 40,
            authorization=drifted,
            call_id=WEAK_CALL_ID,
            completed_new_call_ids=(),
            new_observations={},
        )
    assert identity.value.code is V52GateErrorCode.IDENTITY_MISMATCH


def test_offline_validation_has_no_provider_boundary_and_live_stays_closed() -> None:
    validate_v5_2_preparation_offline()
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
    source = (
        ROOT / "tests/calibration/pedagogical/semantic_gate_v5_2.py"
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
    assert strong_carry_forward_audit().eligible is True
