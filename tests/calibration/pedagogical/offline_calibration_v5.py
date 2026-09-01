"""Deterministic synthetic calibration and canonical-anchor audit for V5."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from tests.calibration.pedagogical.anchor_corpus_v4 import (
    V4_CALIBRATION_ANCHORS,
    V4_CRITERION_ORDERINGS,
    v4_calibration_corpus_sha256,
)
from tests.calibration.pedagogical.protocol import V4_CALIBRATION_CRITERION_ITEMS
from tests.calibration.pedagogical.scorer_contract_v5 import (
    V5_CRITERION_RUBRICS,
    V5Confidence,
    V5DefectItem,
    V5DefectSeverity,
    V5DifferenceSignificance,
    V5EvidenceItem,
    V5EvidenceProfile,
    V5FavoredCandidate,
    V5PairwiseDecision,
    V5PairwiseDifference,
    V5PairwiseOutcome,
    V5ScoreLevel,
    V5ScorerOutcome,
    build_v5_anchor_observation,
    evaluate_v5_evidence,
    evaluate_v5_pairwise,
    v5_pairwise_output_schema,
    v5_pairwise_system_instructions,
    v5_score_output_schema,
    v5_scorer_system_instructions,
)

EXPECTED_V4_CORPUS_SHA256 = (
    "9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034"
)


class V5SyntheticClass(StrEnum):
    ABSENT = "ABSENT"
    CONTRADICTION = "CONTRADICTION"
    WEAK = "WEAK"
    MIXED = "MIXED"
    SATISFACTORY = "SATISFACTORY"
    STRONG = "STRONG"


class V5PairwiseFixtureClass(StrEnum):
    A_CLEARLY_BETTER = "A_CLEARLY_BETTER"
    B_CLEARLY_BETTER = "B_CLEARLY_BETTER"
    NEAR_IDENTICAL = "NEAR_IDENTICAL"
    OUT_OF_SCOPE_DIFFERENCE = "OUT_OF_SCOPE_DIFFERENCE"


@dataclass(frozen=True, slots=True)
class V5SyntheticScoreFixture:
    fixture_id: str
    criterion_ref: str
    fixture_class: V5SyntheticClass
    expected_level: V5ScoreLevel
    profile: V5EvidenceProfile
    outcome: V5ScorerOutcome


@dataclass(frozen=True, slots=True)
class V5SyntheticPairwiseFixture:
    fixture_id: str
    criterion_ref: str
    fixture_class: V5PairwiseFixtureClass
    expected_decision: V5PairwiseDecision
    outcome: V5PairwiseOutcome


@dataclass(frozen=True, slots=True)
class V5OfflineMetrics:
    score_fixture_count: int
    strict_monotonicity_count: int
    criterion_count: int
    inversion_count: int
    tie_count: int
    histogram: tuple[tuple[int, int], ...]
    extreme_score_count: int
    extreme_score_rate: Fraction
    intermediate_score_count: int
    intermediate_score_rate: Fraction
    pairwise_fixture_count: int
    pairwise_correct_count: int
    pairwise_accuracy: Fraction
    pairwise_tie_count: int
    pairwise_false_tie_count: int


@dataclass(frozen=True, slots=True)
class V5CanonicalAnchorAudit:
    corpus_sha256: str
    corpus_hash_preserved: bool
    anchor_count: int
    observation_count: int
    criterion_count: int
    distinct_triplet_count: int
    blinding_violation_count: int
    semantic_scoring_status: str


_CLASS_LEVELS = {
    V5SyntheticClass.ABSENT: V5ScoreLevel.ABSENT_OR_CONTRADICTORY,
    V5SyntheticClass.CONTRADICTION: V5ScoreLevel.ABSENT_OR_CONTRADICTORY,
    V5SyntheticClass.WEAK: V5ScoreLevel.VERY_INSUFFICIENT,
    V5SyntheticClass.MIXED: V5ScoreLevel.PARTIALLY_SATISFACTORY,
    V5SyntheticClass.SATISFACTORY: V5ScoreLevel.SATISFACTORY,
    V5SyntheticClass.STRONG: V5ScoreLevel.VERY_SATISFACTORY,
}


def build_v5_synthetic_score_fixtures() -> tuple[V5SyntheticScoreFixture, ...]:
    fixtures: list[V5SyntheticScoreFixture] = []
    for rubric in V5_CRITERION_RUBRICS:
        slug = rubric.criterion_ref.replace(".", "-")
        for fixture_class, expected_level in _CLASS_LEVELS.items():
            observed_count = int(expected_level)
            contradiction = fixture_class is V5SyntheticClass.CONTRADICTION
            if contradiction:
                observed_count = 1
            evidence = tuple(
                V5EvidenceItem(
                    check.check_id,
                    f"section-{index}",
                    f"Contrôle observé: {check.description}",
                )
                for index, check in enumerate(rubric.checks[:observed_count], start=1)
            )
            missing = rubric.checks[observed_count:]
            severity = (
                V5DefectSeverity.MINOR
                if expected_level is V5ScoreLevel.SATISFACTORY
                else V5DefectSeverity.MAJOR
            )
            defects = tuple(
                V5DefectItem(
                    check.check_id,
                    "candidate",
                    f"Contrôle non observé: {check.description}",
                    severity,
                )
                for check in missing
            )
            if contradiction:
                defects += (
                    V5DefectItem(
                        "criterion.contradiction",
                        "candidate",
                        "Une affirmation contredit matériellement le critère évalué.",
                        V5DefectSeverity.CONTRADICTION,
                    ),
                )
            profile = V5EvidenceProfile(
                observation_id=f"fixture.{slug}.{fixture_class.value.casefold()}",
                criterion_ref=rubric.criterion_ref,
                evidence=evidence,
                defects=defects,
            )
            outcome = evaluate_v5_evidence(profile)
            fixtures.append(
                V5SyntheticScoreFixture(
                    fixture_id=profile.observation_id,
                    criterion_ref=rubric.criterion_ref,
                    fixture_class=fixture_class,
                    expected_level=expected_level,
                    profile=profile,
                    outcome=outcome,
                )
            )
    return tuple(fixtures)


def build_v5_synthetic_pairwise_fixtures() -> tuple[V5SyntheticPairwiseFixture, ...]:
    fixtures: list[V5SyntheticPairwiseFixture] = []
    specifications = (
        (
            V5PairwiseFixtureClass.A_CLEARLY_BETTER,
            V5DifferenceSignificance.MATERIAL,
            V5FavoredCandidate.A,
            V5PairwiseDecision.A_BETTER,
        ),
        (
            V5PairwiseFixtureClass.B_CLEARLY_BETTER,
            V5DifferenceSignificance.MATERIAL,
            V5FavoredCandidate.B,
            V5PairwiseDecision.B_BETTER,
        ),
        (
            V5PairwiseFixtureClass.NEAR_IDENTICAL,
            V5DifferenceSignificance.NON_MATERIAL,
            V5FavoredCandidate.NEITHER,
            V5PairwiseDecision.TIE,
        ),
        (
            V5PairwiseFixtureClass.OUT_OF_SCOPE_DIFFERENCE,
            V5DifferenceSignificance.OUT_OF_SCOPE,
            V5FavoredCandidate.A,
            V5PairwiseDecision.TIE,
        ),
    )
    for rubric in V5_CRITERION_RUBRICS:
        slug = rubric.criterion_ref.replace(".", "-")
        for fixture_class, significance, favored, expected in specifications:
            difference = V5PairwiseDifference(
                locator_a="candidate-a",
                locator_b="candidate-b",
                observation=f"Différence contrôlée pour {rubric.criterion_ref}.",
                significance=significance,
                favored_candidate=favored,
            )
            outcome = evaluate_v5_pairwise((difference,), confidence=V5Confidence.HIGH)
            fixtures.append(
                V5SyntheticPairwiseFixture(
                    fixture_id=f"pairwise.{slug}.{fixture_class.value.casefold()}",
                    criterion_ref=rubric.criterion_ref,
                    fixture_class=fixture_class,
                    expected_decision=expected,
                    outcome=outcome,
                )
            )
    return tuple(fixtures)


def compute_v5_offline_metrics() -> V5OfflineMetrics:
    score_fixtures = build_v5_synthetic_score_fixtures()
    pairwise_fixtures = build_v5_synthetic_pairwise_fixtures()
    by_key = {
        (item.criterion_ref, item.fixture_class): item.outcome.score_level
        for item in score_fixtures
    }
    strict = 0
    inversions = 0
    ties = 0
    for rubric in V5_CRITERION_RUBRICS:
        values = tuple(
            by_key[(rubric.criterion_ref, fixture_class)]
            for fixture_class in (
                V5SyntheticClass.STRONG,
                V5SyntheticClass.MIXED,
                V5SyntheticClass.WEAK,
            )
        )
        levels = tuple(int(value) for value in values if value is not None)
        pairs = tuple(zip(levels, levels[1:], strict=False))
        strict += int(len(levels) == 3 and all(left > right for left, right in pairs))
        inversions += sum(left < right for left, right in pairs)
        ties += sum(left == right for left, right in pairs)
    scores = tuple(
        int(item.outcome.score_level)
        for item in score_fixtures
        if item.outcome.score_level is not None
    )
    histogram = Counter(scores)
    extremes = sum(score in {0, 4} for score in scores)
    intermediates = sum(score in {1, 2, 3} for score in scores)
    correct = sum(
        item.outcome.decision is item.expected_decision for item in pairwise_fixtures
    )
    pairwise_ties = sum(
        item.outcome.decision is V5PairwiseDecision.TIE for item in pairwise_fixtures
    )
    false_ties = sum(
        item.outcome.decision is V5PairwiseDecision.TIE
        and item.expected_decision is not V5PairwiseDecision.TIE
        for item in pairwise_fixtures
    )
    return V5OfflineMetrics(
        score_fixture_count=len(score_fixtures),
        strict_monotonicity_count=strict,
        criterion_count=len(V5_CRITERION_RUBRICS),
        inversion_count=inversions,
        tie_count=ties,
        histogram=tuple(sorted(histogram.items())),
        extreme_score_count=extremes,
        extreme_score_rate=Fraction(extremes, len(scores)),
        intermediate_score_count=intermediates,
        intermediate_score_rate=Fraction(intermediates, len(scores)),
        pairwise_fixture_count=len(pairwise_fixtures),
        pairwise_correct_count=correct,
        pairwise_accuracy=Fraction(correct, len(pairwise_fixtures)),
        pairwise_tie_count=pairwise_ties,
        pairwise_false_tie_count=false_ties,
    )


def audit_v5_canonical_anchor_compatibility() -> V5CanonicalAnchorAudit:
    observations = tuple(
        build_v5_anchor_observation(item) for item in V4_CALIBRATION_CRITERION_ITEMS
    )
    forbidden = (
        '"tier"',
        "strong",
        "mixed",
        "weak_but_structurally_valid",
        "openai",
        "anthropic",
        '"provider"',
        '"producer"',
        '"expected_score"',
    )
    violations = 0
    for observation in observations:
        payload = json.dumps(
            observation.as_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).casefold()
        violations += int(any(marker in payload for marker in forbidden))
    anchor_projection_by_id = {
        anchor.anchor_id: anchor.candidate_projection() for anchor in V4_CALIBRATION_ANCHORS
    }
    distinct_triplets = sum(
        len(
            {
                anchor_projection_by_id[anchor_id]
                for anchor_id in ordering.ordered_anchor_ids
            }
        )
        == 3
        for ordering in V4_CRITERION_ORDERINGS
    )
    corpus_sha256 = v4_calibration_corpus_sha256()
    return V5CanonicalAnchorAudit(
        corpus_sha256=corpus_sha256,
        corpus_hash_preserved=corpus_sha256 == EXPECTED_V4_CORPUS_SHA256,
        anchor_count=len(V4_CALIBRATION_ANCHORS),
        observation_count=len(observations),
        criterion_count=len(V5_CRITERION_RUBRICS),
        distinct_triplet_count=distinct_triplets,
        blinding_violation_count=violations,
        semantic_scoring_status="NOT_EXECUTED_OFFLINE_WITHOUT_A_SEMANTIC_JUDGE",
    )


def v5_contract_sha256() -> str:
    payload = {
        "scorer_instructions": v5_scorer_system_instructions(),
        "scorer_schema": v5_score_output_schema(),
        "pairwise_instructions": v5_pairwise_system_instructions(),
        "pairwise_schema": v5_pairwise_output_schema(),
        "rubrics": [rubric.as_payload() for rubric in V5_CRITERION_RUBRICS],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
