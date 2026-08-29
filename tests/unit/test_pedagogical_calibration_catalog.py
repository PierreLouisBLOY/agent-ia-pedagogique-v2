from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, fields

import pytest

from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
    ProviderCredentialRef,
)
from evaluation_harness import (
    EVALUATION_SCHEMA_V1_0,
    EvaluationObservationRef,
    EvaluationScoringCriterionSpec,
    NormalizedScore,
    ScoreEvaluator,
    ScoreStatus,
)
from tests.calibration.pedagogical.catalog import (
    ANCHOR_EXPECTATIONS,
    CALIBRATION_ANCHORS,
    CALIBRATION_SCENARIOS,
    CRITERION_ORDERINGS,
    PEDAGOGICAL_CALIBRATION_CORPUS_VERSION,
    AnchorExpectation,
    AnchorTier,
    CalibrationAnchor,
    calibration_corpus_sha256,
)
from tests.calibration.pedagogical.protocol import (
    ANCHOR_ADMISSIBILITY_RULE_IDS,
    CALIBRATION_CRITERION_ITEMS,
    SCORER_OBSERVATION_FIELD_CODES,
    AnchorAdmissibilityStatus,
    assess_anchor_admissibility,
    build_all_blind_scorer_observations,
)
from tests.e2e.core.catalog import CANONICAL_PEDAGOGICAL_SCENARIOS
from tests.e2e.core.expectations import SCENARIO_EXPECTATIONS
from tests.providers.anthropic import (
    AnthropicEvaluationScorer,
    AnthropicScoringResponse,
)
from tests.support.anthropic_scoring_fakes import (
    RecordingAnthropicScoringTransport,
    RecordingAnthropicScoringTransportFactory,
)
from tests.support.evaluation_assertion_fakes import RecordingObservationSource

_EXPECTED_CRITERIA = (
    ("scn-01.quality.clarity", "scn-01.quality.organization-utility"),
    ("scn-02.quality.relevance", "scn-02.quality.coverage"),
    ("scn-03.quality.clarity", "scn-03.quality.level-adaptation"),
    ("scn-04.quality.fidelity", "scn-04.quality.level-adaptation"),
    (
        "scn-05.quality.difficulty-appropriateness",
        "scn-05.quality.instruction-clarity",
    ),
    ("scn-06.quality.assessment-clarity", "scn-06.quality.marking-scheme-coherence"),
    ("scn-07.quality.correction-quality", "scn-07.quality.remediation-clarity"),
    ("scn-08.quality.distractor-quality", "scn-08.quality.feedback-quality"),
)


def test_catalog_is_exact_immutable_and_derived_from_1215_owners() -> None:
    assert PEDAGOGICAL_CALIBRATION_CORPUS_VERSION == "12.16-g1-v1"
    assert len(CALIBRATION_SCENARIOS) == len(CANONICAL_PEDAGOGICAL_SCENARIOS) == 8
    assert len(SCENARIO_EXPECTATIONS) == 8
    assert tuple(item.criterion_refs for item in CALIBRATION_SCENARIOS) == _EXPECTED_CRITERIA
    assert tuple(item.scenario_code for item in CALIBRATION_SCENARIOS) == tuple(
        item.case.code.value for item in CANONICAL_PEDAGOGICAL_SCENARIOS
    )
    assert tuple(item.level_code for item in CALIBRATION_SCENARIOS) == tuple(
        item.level.value for item in CANONICAL_PEDAGOGICAL_SCENARIOS
    )
    assert tuple(item.task_kind for item in CALIBRATION_SCENARIOS) == tuple(
        item.intent.value for item in CANONICAL_PEDAGOGICAL_SCENARIOS
    )
    assert tuple(item.required_sections for item in CALIBRATION_SCENARIOS) == tuple(
        tuple(section.value for section in item.section_codes)
        for item in CANONICAL_PEDAGOGICAL_SCENARIOS
    )
    assert tuple(item.rubric_ref for item in CALIBRATION_SCENARIOS) == tuple(
        item.rubric.rubric_ref.value for item in CANONICAL_PEDAGOGICAL_SCENARIOS
    )
    with pytest.raises(FrozenInstanceError):
        CALIBRATION_ANCHORS[0].anchor_id = "changed"  # type: ignore[misc]
    assert not hasattr(CALIBRATION_ANCHORS[0], "__dict__")


def test_twenty_four_anchors_and_forty_eight_items_are_safe_and_structurally_valid() -> None:
    assert len(CALIBRATION_ANCHORS) == 24
    assert len({anchor.anchor_id for anchor in CALIBRATION_ANCHORS}) == 24
    assert len(CALIBRATION_CRITERION_ITEMS) == 48
    assert len(CRITERION_ORDERINGS) == 16
    assert len(ANCHOR_ADMISSIBILITY_RULE_IDS) == 5
    results = tuple(assess_anchor_admissibility(anchor) for anchor in CALIBRATION_ANCHORS)
    assert {result.status for result in results} == {
        AnchorAdmissibilityStatus.ADMISSIBLE
    }
    assert all(result.violated_rule_ids == () for result in results)
    assert all(len(anchor.candidate_projection()) <= 2_500 for anchor in CALIBRATION_ANCHORS)


def test_analysis_ordering_is_closed_ordinal_and_contains_no_expected_scores() -> None:
    assert tuple(item.tier for item in ANCHOR_EXPECTATIONS[:3]) == tuple(AnchorTier)
    assert len(ANCHOR_EXPECTATIONS) == 24
    assert {
        tier: sum(item.tier is tier for item in ANCHOR_EXPECTATIONS)
        for tier in AnchorTier
    } == {tier: 8 for tier in AnchorTier}
    assert tuple(field.name for field in fields(AnchorExpectation)) == (
        "anchor_id",
        "tier",
    )
    assert tuple(field.name for field in fields(CalibrationAnchor)) == (
        "anchor_id",
        "scenario_code",
        "sections",
    )
    assert all(
        ordering.ordered_anchor_ids[0].endswith(".a")
        and ordering.ordered_anchor_ids[1].endswith(".b")
        and ordering.ordered_anchor_ids[2].endswith(".c")
        for ordering in CRITERION_ORDERINGS
    )


def test_corpus_checksum_is_deterministic_and_frozen() -> None:
    assert (
        calibration_corpus_sha256()
        == "abeec0b4e5e1f60f2974ec1c19de34a5307e1b7d92e11c7b811e338d3b2e626d"
    )
    assert calibration_corpus_sha256() == calibration_corpus_sha256()


def test_all_scorer_observations_have_only_the_blind_bounded_projection() -> None:
    observations = build_all_blind_scorer_observations()
    assert len(observations) == 48
    assert observations == build_all_blind_scorer_observations()
    for observation in observations:
        assert tuple(field.code.value for field in observation.fields) == (
            SCORER_OBSERVATION_FIELD_CODES
        )
        serialized = json.dumps(observation, default=repr).casefold()
        assert "cal.scn-" not in serialized
        assert "strong" not in serialized
        assert "mixed" not in serialized
        assert "weak_but_structurally_valid" not in serialized
        assert "openai" not in serialized
        assert "anthropic" not in serialized
        assert "expected-score" not in serialized
        assert "gate" not in serialized
        assert "credential" not in serialized
        assert ":\\" not in serialized
        assert "://" not in serialized


def test_existing_anthropic_mapper_serializes_all_48_items_through_fake_transport() -> None:
    provider_id = ProviderProfileId("anthropic-calibration-provider")
    credential_ref = ProviderCredentialRef("SYNTHETIC_TEST_CREDENTIAL")
    transport = RecordingAnthropicScoringTransport(
        response=AnthropicScoringResponse(
            '{"status":"SCORED","score_numerator":1,"score_denominator":2}'
        )
    )
    scorer = AnthropicEvaluationScorer(
        provider_profile=ProviderProfileConfig(
            provider_id,
            ProviderCode("anthropic"),
            credential_ref,
        ),
        model_profile=ModelProfileConfig(
            ModelProfileId("anthropic.claude-sonnet-5.scorer"),
            provider_id,
            ModelCode("claude-sonnet-5"),
            ModelContextLimits(1_000_000, 872_000, 128_000),
            ProviderInvocationLimits(1, 30_000, max_output_tokens=512),
            (ProviderWorkloadKind.EVALUATION_SCORING,),
            structured_output_required=True,
        ),
        secret_resolver=EnvironmentProviderSecretResolver(
            {credential_ref.value: "synthetic-test-value"}
        ),
        transport_factory=RecordingAnthropicScoringTransportFactory(transport),
    )
    observations = build_all_blind_scorer_observations()
    refs = tuple(
        EvaluationObservationRef(f"calibration.observation.{index:02d}")
        for index in range(len(observations))
    )
    source = RecordingObservationSource(*tuple(zip(refs, observations, strict=True)))
    results = tuple(
        ScoreEvaluator(source, scorer).evaluate(
            EvaluationScoringCriterionSpec(
                EVALUATION_SCHEMA_V1_0,
                next(
                    criterion.criterion_ref
                    for expectation in SCENARIO_EXPECTATIONS
                    for criterion in expectation.rubric.criteria
                    if criterion.criterion_ref.value == item.criterion_ref
                ),
                next(iter(SCENARIO_EXPECTATIONS)).rubric.criteria[0].scorer_ref,
                (observation_ref,),
                NormalizedScore.whole(),
            )
        )
        for item, observation_ref in zip(
            CALIBRATION_CRITERION_ITEMS,
            refs,
            strict=True,
        )
    )
    assert len(results) == 48
    assert {result.status for result in results} == {ScoreStatus.SCORED}
    assert len(transport.calls) == 48
    for request in transport.calls:
        serialized = request.input_json.casefold()
        assert "cal.scn-" not in serialized
        assert all(tier.value.casefold() not in serialized for tier in AnchorTier)
        assert "provider" not in serialized
        assert "model_id" not in serialized
        assert request.model == "claude-sonnet-5"
