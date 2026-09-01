from __future__ import annotations

import json
from fractions import Fraction
from typing import cast

import pytest

from tests.calibration.pedagogical.offline_calibration_v5 import (
    EXPECTED_V4_CORPUS_SHA256,
    V5PairwiseFixtureClass,
    V5SyntheticClass,
    audit_v5_canonical_anchor_compatibility,
    build_v5_synthetic_pairwise_fixtures,
    build_v5_synthetic_score_fixtures,
    compute_v5_offline_metrics,
    v5_contract_sha256,
)
from tests.calibration.pedagogical.protocol import V4_CALIBRATION_CRITERION_ITEMS
from tests.calibration.pedagogical.scorer_contract_v5 import (
    LIVE_PROVIDER_RECALIBRATION_AUTHORIZED,
    V5_CRITERION_RUBRICS,
    V5_PAIRWISE_CONTRACT_VERSION,
    V5_SCORE_SCALE_VERSION,
    V5_SCORER_CONTRACT_VERSION,
    V5Confidence,
    V5ContractError,
    V5ContractErrorCode,
    V5DefectItem,
    V5DefectSeverity,
    V5DifferenceSignificance,
    V5EvidenceItem,
    V5EvidenceProfile,
    V5FavoredCandidate,
    V5PairwiseDifference,
    V5PairwiseObservation,
    V5ScoreLevel,
    V5ScoreStatus,
    assert_v5_live_execution_forbidden,
    build_v5_anchor_observation,
    evaluate_v5_evidence,
    evaluate_v5_pairwise,
    parse_v5_pairwise_output,
    parse_v5_score_output,
    v5_pairwise_output_schema,
    v5_score_output_schema,
)

EXPECTED_V5_CONTRACT_SHA256 = (
    "a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344"
)


def _score_json(fixture_index: int) -> str:
    fixture = build_v5_synthetic_score_fixtures()[fixture_index]
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
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _pairwise_json(fixture_index: int) -> str:
    outcome = build_v5_synthetic_pairwise_fixtures()[fixture_index].outcome
    payload = {
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
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def test_v5_contract_versions_rubrics_and_hash_are_closed() -> None:
    assert V5_SCORER_CONTRACT_VERSION == "12.16-g2-v5-scorer-contract-v1"
    assert V5_SCORE_SCALE_VERSION == "12.16-g2-v5-ordinal-scale-0-4-v1"
    assert V5_PAIRWISE_CONTRACT_VERSION == "12.16-g2-v5-pairwise-v1"
    assert len(V5_CRITERION_RUBRICS) == 16
    assert len({item.criterion_ref for item in V5_CRITERION_RUBRICS}) == 16
    assert all(len(item.checks) == 4 for item in V5_CRITERION_RUBRICS)
    assert all(len(item.level_descriptors) == 5 for item in V5_CRITERION_RUBRICS)
    assert v5_contract_sha256() == EXPECTED_V5_CONTRACT_SHA256


def test_v5_score_schema_is_evidence_first_and_strict() -> None:
    schema = v5_score_output_schema()
    assert schema["additionalProperties"] is False
    properties = cast(dict[str, object], schema["properties"])
    assert list(properties) == [
        "status",
        "evidence",
        "defects",
        "score_level",
        "confidence",
        "rationale",
    ]
    assert properties["score_level"]["anyOf"][0] == {  # type: ignore[index]
        "type": "integer",
        "minimum": 0,
        "maximum": 4,
    }
    assert properties["evidence"]["items"]["additionalProperties"] is False  # type: ignore[index]
    assert properties["defects"]["items"]["additionalProperties"] is False  # type: ignore[index]


def test_v5_scale_reaches_every_level_with_exact_normalization() -> None:
    fixtures = build_v5_synthetic_score_fixtures()
    first_criterion = fixtures[:6]
    assert tuple(item.fixture_class for item in first_criterion) == tuple(V5SyntheticClass)
    assert tuple(item.outcome.score_level for item in first_criterion) == (
        V5ScoreLevel.ABSENT_OR_CONTRADICTORY,
        V5ScoreLevel.ABSENT_OR_CONTRADICTORY,
        V5ScoreLevel.VERY_INSUFFICIENT,
        V5ScoreLevel.PARTIALLY_SATISFACTORY,
        V5ScoreLevel.SATISFACTORY,
        V5ScoreLevel.VERY_SATISFACTORY,
    )
    assert tuple(item.outcome.normalized_score for item in first_criterion) == (
        Fraction(0, 1),
        Fraction(0, 1),
        Fraction(1, 4),
        Fraction(1, 2),
        Fraction(3, 4),
        Fraction(1, 1),
    )


def test_v5_score_parser_round_trips_all_synthetic_fixtures() -> None:
    fixtures = build_v5_synthetic_score_fixtures()
    for index, fixture in enumerate(fixtures):
        parsed = parse_v5_score_output(_score_json(index), fixture.criterion_ref)
        assert parsed == fixture.outcome
        assert parsed.status is V5ScoreStatus.SCORED


def test_v5_score_parser_rejects_score_not_supported_by_evidence() -> None:
    fixture = next(
        item
        for item in build_v5_synthetic_score_fixtures()
        if item.fixture_class is V5SyntheticClass.WEAK
    )
    payload = json.loads(
        _score_json(build_v5_synthetic_score_fixtures().index(fixture))
    )
    payload["score_level"] = 4
    with pytest.raises(V5ContractError) as mismatch:
        parse_v5_score_output(json.dumps(payload), fixture.criterion_ref)
    assert mismatch.value.code is V5ContractErrorCode.SCORE_EVIDENCE_MISMATCH


def test_v5_score_parser_rejects_contradiction_above_zero() -> None:
    fixtures = build_v5_synthetic_score_fixtures()
    index = next(
        index
        for index, item in enumerate(fixtures)
        if item.fixture_class is V5SyntheticClass.CONTRADICTION
    )
    payload = json.loads(_score_json(index))
    payload["score_level"] = 1
    with pytest.raises(V5ContractError) as mismatch:
        parse_v5_score_output(json.dumps(payload), fixtures[index].criterion_ref)
    assert mismatch.value.code is V5ContractErrorCode.CONTRADICTION_SCORE_MISMATCH


def test_v5_evidence_validation_rejects_unknown_checks_and_missing_defects() -> None:
    rubric = V5_CRITERION_RUBRICS[0]
    unknown = V5EvidenceProfile(
        "fixture.unknown.check",
        rubric.criterion_ref,
        (V5EvidenceItem("unknown.check", "candidate", "Observation locale."),),
        tuple(
            V5DefectItem(
                item.check_id,
                "candidate",
                "Contrôle absent.",
                V5DefectSeverity.MAJOR,
            )
            for item in rubric.checks
        ),
    )
    with pytest.raises(V5ContractError) as unknown_error:
        evaluate_v5_evidence(unknown)
    assert unknown_error.value.code is V5ContractErrorCode.EVIDENCE_CHECK_UNKNOWN

    incomplete = V5EvidenceProfile(
        "fixture.missing.defect",
        rubric.criterion_ref,
        (V5EvidenceItem(rubric.checks[0].check_id, "candidate", "Observation locale."),),
        (),
    )
    with pytest.raises(V5ContractError) as coverage_error:
        evaluate_v5_evidence(incomplete)
    assert coverage_error.value.code is V5ContractErrorCode.DEFECT_COVERAGE_INVALID


def test_v5_synthetic_metrics_are_discriminant_and_non_binary() -> None:
    metrics = compute_v5_offline_metrics()
    assert metrics.score_fixture_count == 96
    assert metrics.strict_monotonicity_count == metrics.criterion_count == 16
    assert metrics.inversion_count == 0
    assert metrics.tie_count == 0
    assert metrics.histogram == ((0, 32), (1, 16), (2, 16), (3, 16), (4, 16))
    assert metrics.extreme_score_count == 48
    assert metrics.extreme_score_rate == 1 / 2
    assert metrics.intermediate_score_count == 48
    assert metrics.intermediate_score_rate == 1 / 2


def test_v5_pairwise_contract_is_independent_and_accurate() -> None:
    schema = v5_pairwise_output_schema()
    assert schema["additionalProperties"] is False
    assert "score" not in json.dumps(schema).casefold()
    fixtures = build_v5_synthetic_pairwise_fixtures()
    assert len(fixtures) == 64
    assert {item.fixture_class for item in fixtures} == set(V5PairwiseFixtureClass)
    for index, fixture in enumerate(fixtures):
        parsed = parse_v5_pairwise_output(_pairwise_json(index))
        assert parsed == fixture.outcome
        assert parsed.decision is fixture.expected_decision
    metrics = compute_v5_offline_metrics()
    assert metrics.pairwise_correct_count == metrics.pairwise_fixture_count == 64
    assert metrics.pairwise_accuracy == 1
    assert metrics.pairwise_tie_count == 32
    assert metrics.pairwise_false_tie_count == 0


def test_v5_pairwise_tie_rejects_any_material_difference() -> None:
    material = V5PairwiseDifference(
        "candidate-a",
        "candidate-b",
        "A satisfait un contrôle que B ne satisfait pas.",
        V5DifferenceSignificance.MATERIAL,
        V5FavoredCandidate.A,
    )
    with pytest.raises(V5ContractError) as tie_error:
        parse_v5_pairwise_output(
            json.dumps(
                {
                    "differences": [
                        {
                            "locator_a": material.locator_a,
                            "locator_b": material.locator_b,
                            "observation": material.observation,
                            "significance": material.significance.value,
                            "favored_candidate": material.favored_candidate.value,
                        }
                    ],
                    "decision": "TIE",
                    "confidence": "HIGH",
                    "rationale": "Tie non étayé.",
                }
            )
        )
    assert tie_error.value.code is V5ContractErrorCode.PAIRWISE_TIE_MATERIAL_DIFFERENCE


def test_v5_pairwise_rejects_conflicting_material_winners() -> None:
    differences = (
        V5PairwiseDifference(
            "a-1",
            "b-1",
            "Avantage matériel A.",
            V5DifferenceSignificance.MATERIAL,
            V5FavoredCandidate.A,
        ),
        V5PairwiseDifference(
            "a-2",
            "b-2",
            "Avantage matériel B.",
            V5DifferenceSignificance.MATERIAL,
            V5FavoredCandidate.B,
        ),
    )
    with pytest.raises(V5ContractError) as conflict:
        evaluate_v5_pairwise(differences, confidence=V5Confidence.LOW)
    assert conflict.value.code is V5ContractErrorCode.PAIRWISE_MATERIAL_CONFLICT


def test_v5_canonical_anchor_observations_remain_blind_and_immutable() -> None:
    audit = audit_v5_canonical_anchor_compatibility()
    assert audit.corpus_sha256 == EXPECTED_V4_CORPUS_SHA256
    assert audit.corpus_hash_preserved is True
    assert audit.anchor_count == 24
    assert audit.observation_count == 48
    assert audit.criterion_count == 16
    assert audit.distinct_triplet_count == 16
    assert audit.blinding_violation_count == 0
    assert audit.semantic_scoring_status == "NOT_EXECUTED_OFFLINE_WITHOUT_A_SEMANTIC_JUDGE"

    observations = tuple(
        build_v5_anchor_observation(item) for item in V4_CALIBRATION_CRITERION_ITEMS
    )
    assert all("tier" not in item.as_payload() for item in observations)
    assert all("expected_score" not in item.as_payload() for item in observations)


def test_v5_pairwise_input_uses_opaque_candidates_without_producer_identity() -> None:
    score_observation = build_v5_anchor_observation(V4_CALIBRATION_CRITERION_ITEMS[0])
    pairwise = V5PairwiseObservation(
        comparison_id="pairwise.fixture.opaque",
        scenario=score_observation.scenario,
        rubric=score_observation.rubric,
        candidate_a_id="candidate.opaque.a",
        candidate_a_projection="[section] Contenu synthétique A.",
        candidate_b_id="candidate.opaque.b",
        candidate_b_projection="[section] Contenu synthétique B.",
    )
    payload = json.dumps(pairwise.as_payload(), ensure_ascii=False, sort_keys=True).casefold()
    assert all(marker not in payload for marker in ("provider", "producer", "model", "openai", "anthropic"))


def test_v5_live_execution_is_fail_closed() -> None:
    assert LIVE_PROVIDER_RECALIBRATION_AUTHORIZED is False
    with pytest.raises(V5ContractError) as blocked:
        assert_v5_live_execution_forbidden()
    assert blocked.value.code is V5ContractErrorCode.LIVE_EXECUTION_FORBIDDEN
