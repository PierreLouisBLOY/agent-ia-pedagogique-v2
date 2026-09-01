from __future__ import annotations

import json
from decimal import Decimal

import pytest

from tests.calibration.pedagogical.offline_calibration_v5 import (
    build_v5_synthetic_pairwise_fixtures,
    build_v5_synthetic_score_fixtures,
)
from tests.calibration.pedagogical.pricing import pricing_snapshot_sha256
from tests.calibration.pedagogical.repair_tranche_v4_2 import (
    V42_LOGICAL_CALL_MATRIX,
    CallIdentityVersion,
    call_spec_sha256,
)
from tests.calibration.pedagogical.scorer_contract_v5 import (
    V5Confidence,
    V5DifferenceSignificance,
    V5FavoredCandidate,
    V5PairwiseDecision,
    V5PairwiseDifference,
    V5PairwiseOutcome,
    V5ScoreLevel,
    V5ScorerOutcome,
    V5ScoreStatus,
)
from tests.calibration.pedagogical.semantic_integration_v5 import (
    APPROVED_PILOT_CEILING_USD,
    EXPECTED_V5_SCORER_CONTRACT_SHA256,
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    MINIMAL_PILOT_CALL_IDS,
    ROBUST_PILOT_CALL_IDS,
    V5_BASELINE_COMMIT_SHA,
    V5_LOGICAL_CALL_MATRIX,
    V5_OFFLINE_MANIFEST_SHA256,
    V5CallContract,
    V5DiffReason,
    V5IntegrationError,
    V5IntegrationErrorCode,
    V5PairwiseObservation,
    V5PilotBudgetGuard,
    V5PilotVerdict,
    V5ScorerObservation,
    build_minimal_pilot,
    build_robust_pilot,
    build_semantic_pilot_report,
    build_v5_observation,
    build_v42_to_v5_diff,
    estimate_pilot_budget,
    evaluate_canary_gate,
    parse_v5_call_result,
    v5_call_spec_sha256,
    v5_logical_matrix_sha256,
    validate_offline_integration,
    validate_offline_preflight,
)


def _score(level: int) -> V5ScorerOutcome:
    return V5ScorerOutcome(
        status=V5ScoreStatus.SCORED,
        evidence=(),
        defects=(),
        score_level=V5ScoreLevel(level),
        confidence=V5Confidence.HIGH,
        rationale=f"Niveau synthétique {level} pour le test d'intégration.",
    )


def _pairwise(decision: V5PairwiseDecision) -> V5PairwiseOutcome:
    favored = {
        V5PairwiseDecision.A_BETTER: V5FavoredCandidate.A,
        V5PairwiseDecision.B_BETTER: V5FavoredCandidate.B,
        V5PairwiseDecision.TIE: V5FavoredCandidate.NEITHER,
    }[decision]
    significance = (
        V5DifferenceSignificance.NON_MATERIAL
        if decision is V5PairwiseDecision.TIE
        else V5DifferenceSignificance.MATERIAL
    )
    return V5PairwiseOutcome(
        differences=(
            V5PairwiseDifference(
                "candidate-a",
                "candidate-b",
                "Différence pédagogique contrôlée pour le test.",
                significance,
                favored,
            ),
        ),
        decision=decision,
        confidence=V5Confidence.HIGH,
        rationale="Décision comparative synthétique cohérente.",
    )


def _score_json() -> tuple[str, str]:
    fixture = build_v5_synthetic_score_fixtures()[0]
    outcome = fixture.outcome
    payload = {
        "status": outcome.status.value,
        "evidence": [
            {
                "check_id": item.check_id,
                "locator": item.locator,
                "observation": item.observation,
            }
            for item in outcome.evidence
        ],
        "defects": [
            {
                "check_id": item.check_id,
                "locator": item.locator,
                "observation": item.observation,
                "severity": item.severity.value,
            }
            for item in outcome.defects
        ],
        "score_level": int(outcome.score_level) if outcome.score_level is not None else None,
        "confidence": outcome.confidence.value,
        "rationale": outcome.rationale,
    }
    return fixture.criterion_ref, json.dumps(payload)


def _pairwise_json() -> str:
    outcome = build_v5_synthetic_pairwise_fixtures()[0].outcome
    return json.dumps(
        {
            "differences": [
                {
                    "locator_a": item.locator_a,
                    "locator_b": item.locator_b,
                    "observation": item.observation,
                    "significance": item.significance.value,
                    "favored_candidate": item.favored_candidate.value,
                }
                for item in outcome.differences
            ],
            "decision": outcome.decision.value,
            "confidence": outcome.confidence.value,
            "rationale": outcome.rationale,
        }
    )


def test_v5_matrix_integrates_absolute_and_direct_pairwise_without_mutating_v42() -> None:
    assert len(V42_LOGICAL_CALL_MATRIX) == 102
    assert len(V5_LOGICAL_CALL_MATRIX) == 113
    assert len({item.call.call_id for item in V5_LOGICAL_CALL_MATRIX}) == 113
    assert sum(
        item.contract is V5CallContract.V42_UNCHANGED
        for item in V5_LOGICAL_CALL_MATRIX
    ) == 20
    assert sum(
        item.contract is V5CallContract.V5_ABSOLUTE_SCORE
        for item in V5_LOGICAL_CALL_MATRIX
    ) == 82
    assert sum(
        item.contract is V5CallContract.V5_DIRECT_PAIRWISE
        for item in V5_LOGICAL_CALL_MATRIX
    ) == 11
    assert v5_logical_matrix_sha256() == (
        "3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c"
    )


def test_v42_to_v5_diff_covers_every_canonical_property_and_carry_forward() -> None:
    audit = build_v42_to_v5_diff()
    assert len(audit) == 102
    unchanged = tuple(item for item in audit if item.call_spec_unchanged)
    changed = tuple(item for item in audit if not item.call_spec_unchanged)
    assert len(unchanged) == sum(item.carry_forward_eligible for item in audit) == 20
    assert len(changed) == 82
    assert {item.reason for item in unchanged} == {V5DiffReason.UNCHANGED}
    assert {item.reason for item in changed} == {
        V5DiffReason.SCORER_CONTRACT_AND_PROMPT_CHANGED
    }
    assert all(item.source_terminal_status == "COMPLETED" for item in audit)
    assert all(
        item.provider_unchanged
        and item.model_unchanged
        and item.model_profile_unchanged
        and item.role_unchanged
        and item.workload_unchanged
        and item.scenario_unchanged
        and item.task_kind_unchanged
        and item.repetition_unchanged
        and item.dependencies_unchanged
        and item.criterion_refs_unchanged
        and item.token_budget_unchanged
        and item.declared_input_refs_unchanged
        and item.pricing_identity_unchanged
        for item in audit
    )
    assert all(
        not item.prompt_input_unchanged
        and not item.scorer_parser_contract_unchanged
        for item in changed
    )


def test_unchanged_openai_identity_is_exactly_the_v42_identity() -> None:
    by_id = {item.call.call_id: item for item in V5_LOGICAL_CALL_MATRIX}
    for old in V42_LOGICAL_CALL_MATRIX:
        if old.provider.value != "openai":
            continue
        assert v5_call_spec_sha256(by_id[old.call_id]) == call_spec_sha256(
            old, CallIdentityVersion.V42_CORRECTIVE
        )


def test_minimal_and_robust_pilots_are_small_anthropic_only_canary_first() -> None:
    minimal = build_minimal_pilot()
    robust = build_robust_pilot()
    assert tuple(item.call.call_id for item in minimal.calls) == MINIMAL_PILOT_CALL_IDS
    assert tuple(item.call.call_id for item in robust.calls) == ROBUST_PILOT_CALL_IDS
    assert len(minimal.calls) == 4
    assert len(robust.calls) == 21
    assert robust.canary_call_ids == MINIMAL_PILOT_CALL_IDS
    assert len(robust.fanout_call_ids) == 17
    assert all(item.call.provider.value == "anthropic" for item in (*minimal.calls, *robust.calls))


def test_pilot_budgets_use_canonical_pricing_and_have_no_approval() -> None:
    minimal = estimate_pilot_budget(build_minimal_pilot())
    robust = estimate_pilot_budget(build_robust_pilot())
    assert minimal.openai_call_count == robust.openai_call_count == 0
    assert minimal.anthropic_call_count == 4
    assert robust.anthropic_call_count == 21
    assert minimal.estimate.estimated_base_usd == Decimal("0.058960")
    assert minimal.estimate.estimated_maximum_before_margin_usd == Decimal("0.153920")
    assert minimal.safety_margin_usd == Decimal("0.038480")
    assert minimal.proposed_pilot_ceiling_usd == Decimal("0.192400")
    assert robust.estimate.estimated_base_usd == Decimal("0.311040")
    assert robust.estimate.estimated_maximum_before_margin_usd == Decimal("0.814080")
    assert robust.safety_margin_usd == Decimal("0.203520")
    assert robust.proposed_pilot_ceiling_usd == Decimal("1.017600")
    assert minimal.approved_pilot_ceiling_usd is robust.approved_pilot_ceiling_usd is None
    assert APPROVED_PILOT_CEILING_USD is None


def test_preflight_fails_closed_on_every_frozen_identity() -> None:
    mismatches = (
        ("observed_baseline_commit_sha", V5IntegrationErrorCode.BASELINE_MISMATCH),
        ("observed_matrix_sha256", V5IntegrationErrorCode.MATRIX_MISMATCH),
        ("observed_pricing_sha256", V5IntegrationErrorCode.PRICING_MISMATCH),
        ("observed_manifest_sha256", V5IntegrationErrorCode.MANIFEST_MISMATCH),
        ("observed_contract_sha256", V5IntegrationErrorCode.CONTRACT_MISMATCH),
    )
    for field, expected_code in mismatches:
        values = {
            "observed_baseline_commit_sha": V5_BASELINE_COMMIT_SHA,
            "observed_matrix_sha256": v5_logical_matrix_sha256(),
            "observed_pricing_sha256": pricing_snapshot_sha256(),
            "observed_manifest_sha256": V5_OFFLINE_MANIFEST_SHA256,
            "observed_contract_sha256": EXPECTED_V5_SCORER_CONTRACT_SHA256,
        }
        values[field] = "0" * 64
        with pytest.raises(V5IntegrationError) as error:
            validate_offline_preflight(
                observed_baseline_commit_sha=values[
                    "observed_baseline_commit_sha"
                ],
                observed_matrix_sha256=values["observed_matrix_sha256"],
                observed_pricing_sha256=values["observed_pricing_sha256"],
                observed_manifest_sha256=values["observed_manifest_sha256"],
                observed_contract_sha256=values["observed_contract_sha256"],
            )
        assert error.value.code is expected_code


def test_budget_guard_blocks_fanout_rerun_missing_ceiling_and_live() -> None:
    guard = V5PilotBudgetGuard()
    plan = build_robust_pilot()
    common = {
        "plan": plan,
        "completed_call_ids": (),
        "canary_passed": True,
        "approved_ceiling_usd": Decimal("1.017600"),
        "observed_baseline_commit_sha": V5_BASELINE_COMMIT_SHA,
        "observed_matrix_sha256": v5_logical_matrix_sha256(),
        "observed_pricing_sha256": pricing_snapshot_sha256(),
        "observed_manifest_sha256": V5_OFFLINE_MANIFEST_SHA256,
        "observed_contract_sha256": EXPECTED_V5_SCORER_CONTRACT_SHA256,
    }
    fanout_id = plan.fanout_call_ids[0]
    with pytest.raises(V5IntegrationError) as fanout:
        guard.authorize_next(**{**common, "call_id": fanout_id, "canary_passed": False})
    assert fanout.value.code is V5IntegrationErrorCode.CANARY_FANOUT_FORBIDDEN

    canary_id = plan.canary_call_ids[0]
    with pytest.raises(V5IntegrationError) as rerun:
        guard.authorize_next(
            **{**common, "call_id": canary_id, "completed_call_ids": (canary_id,)}
        )
    assert rerun.value.code is V5IntegrationErrorCode.CALL_ALREADY_COMPLETED

    with pytest.raises(V5IntegrationError) as ceiling:
        guard.authorize_next(
            **{**common, "call_id": canary_id, "approved_ceiling_usd": None}
        )
    assert ceiling.value.code is V5IntegrationErrorCode.APPROVED_CEILING_MISSING

    with pytest.raises(V5IntegrationError) as live:
        guard.authorize_next(**{**common, "call_id": canary_id})
    assert live.value.code is V5IntegrationErrorCode.LIVE_EXECUTION_FORBIDDEN


def test_observation_builders_are_blind_and_require_minimized_output_projection() -> None:
    minimal = build_minimal_pilot()
    absolute = build_v5_observation(minimal.calls[0])
    pairwise = build_v5_observation(minimal.calls[-1])
    assert type(absolute) is V5ScorerObservation
    assert type(pairwise) is V5PairwiseObservation
    payload = json.dumps(pairwise.as_payload(), ensure_ascii=False).casefold()
    assert all(marker not in payload for marker in ("provider", "model", "strong", "mixed"))

    output_pair = next(
        item
        for item in V5_LOGICAL_CALL_MATRIX
        if item.call.call_id
        == "cal.v5.pairwise.output.scn-03.primary-vs-fallback.clarity.r1"
    )
    with pytest.raises(ValueError, match="projection"):
        build_v5_observation(output_pair)
    projected = build_v5_observation(
        output_pair,
        {
            "cal.generation.course.primary.r1": "[content] Projection A.",
            "cal.generation.course.fallback.r1": "[content] Projection B.",
        },
    )
    assert type(projected) is V5PairwiseObservation


def test_real_parser_dispatch_uses_the_integrated_v5_contracts() -> None:
    criterion_ref, score_json = _score_json()
    score_spec = next(
        item
        for item in V5_LOGICAL_CALL_MATRIX
        if item.contract is V5CallContract.V5_ABSOLUTE_SCORE
        and item.call.criterion_refs == (criterion_ref,)
    )
    assert type(parse_v5_call_result(score_spec, score_json)) is V5ScorerOutcome
    pairwise_spec = build_minimal_pilot().calls[-1]
    assert type(parse_v5_call_result(pairwise_spec, _pairwise_json())) is V5PairwiseOutcome


def test_canary_gate_requires_strict_triplet_intermediate_and_correct_pairwise() -> None:
    outcomes = {
        MINIMAL_PILOT_CALL_IDS[0]: _score(4),
        MINIMAL_PILOT_CALL_IDS[1]: _score(2),
        MINIMAL_PILOT_CALL_IDS[2]: _score(1),
        MINIMAL_PILOT_CALL_IDS[3]: _pairwise(V5PairwiseDecision.A_BETTER),
    }
    assert evaluate_canary_gate(outcomes) is True
    outcomes[MINIMAL_PILOT_CALL_IDS[1]] = _score(1)
    outcomes[MINIMAL_PILOT_CALL_IDS[2]] = _score(2)
    assert evaluate_canary_gate(outcomes) is False


def test_report_tracks_provenance_distribution_monotonicity_and_verdicts() -> None:
    plan = build_minimal_pilot()
    pass_outcomes = {
        MINIMAL_PILOT_CALL_IDS[0]: _score(4),
        MINIMAL_PILOT_CALL_IDS[1]: _score(2),
        MINIMAL_PILOT_CALL_IDS[2]: _score(1),
        MINIMAL_PILOT_CALL_IDS[3]: _pairwise(V5PairwiseDecision.A_BETTER),
    }
    report = build_semantic_pilot_report(plan, pass_outcomes)
    assert report.verdict is V5PilotVerdict.PASS
    assert report.carry_forward_count == 20
    assert report.intermediate_score_count == 2
    assert report.intermediate_score_rate == "2/3"
    assert report.extreme_score_count == 1
    assert report.extreme_score_rate == "1/3"
    assert report.strict_monotonicity_count == report.covered_triplet_count == 1
    assert report.inversion_count == 0
    assert report.pairwise_correct_count == report.pairwise_expected_count == 1
    assert report.canary_passed is True
    assert report.safe_payload()["candidate_content_included"] is False

    incomplete = build_semantic_pilot_report(plan, {})
    assert incomplete.verdict is V5PilotVerdict.INCONCLUSIVE
    failed = build_semantic_pilot_report(
        plan,
        {
            **pass_outcomes,
            MINIMAL_PILOT_CALL_IDS[1]: _score(1),
            MINIMAL_PILOT_CALL_IDS[2]: _score(2),
        },
    )
    assert failed.verdict is V5PilotVerdict.FAIL
    assert failed.inversion_count == 1


def test_offline_integration_closes_with_live_default_false() -> None:
    validate_offline_integration()
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
    assert APPROVED_PILOT_CEILING_USD is None
