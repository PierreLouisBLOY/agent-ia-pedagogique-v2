from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from evaluation_harness.contracts.assertion import AssertionKind
from evaluation_harness.contracts.identity import (
    EvaluationAssertionRef,
    EvaluationCaseId,
    EvaluationCriterionRef,
    EvaluationRubricRef,
    EvaluationSuiteId,
)
from evaluation_harness.contracts.scoring import NormalizedScore, ScoreStatus
from evaluation_harness.contracts.verdict import EvaluationVerdict
from evaluation_harness.reporting.model import (
    EvaluationAssertionReport,
    EvaluationCaseReport,
    EvaluationRepetitionReport,
    EvaluationRubricReport,
    EvaluationScoreReport,
    EvaluationSuiteReport,
)


class EvaluationChangeKind(Enum):
    UNCHANGED = "UNCHANGED"
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    CHANGED = "CHANGED"


@dataclass(frozen=True, slots=True)
class EvaluationVerdictTransition:
    from_verdict: EvaluationVerdict
    to_verdict: EvaluationVerdict


@dataclass(frozen=True, slots=True)
class RationalScoreDelta:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise TypeError("score delta components must be integers")
        if self.denominator <= 0:
            raise ValueError("score delta denominator must be positive")
        value = Fraction(self.numerator, self.denominator)
        if not Fraction(-1, 1) <= value <= Fraction(1, 1):
            raise ValueError("score delta must be in [-1,1]")
        if value.numerator != self.numerator or value.denominator != self.denominator:
            raise ValueError("score delta must be normalized")

    @classmethod
    def between(
        cls, baseline: NormalizedScore, candidate: NormalizedScore
    ) -> RationalScoreDelta:
        value = candidate.as_fraction() - baseline.as_fraction()
        return cls(value.numerator, value.denominator)


@dataclass(frozen=True, slots=True)
class EvaluationAssertionComparison:
    assertion_ref: EvaluationAssertionRef
    change_kind: EvaluationChangeKind
    baseline_kind: AssertionKind | None
    candidate_kind: AssertionKind | None
    baseline_verdict: EvaluationVerdict | None
    candidate_verdict: EvaluationVerdict | None


@dataclass(frozen=True, slots=True)
class EvaluationScoreComparison:
    criterion_ref: EvaluationCriterionRef
    change_kind: EvaluationChangeKind
    baseline_status: ScoreStatus | None
    candidate_status: ScoreStatus | None
    delta: RationalScoreDelta | None


@dataclass(frozen=True, slots=True)
class EvaluationRubricComparison:
    rubric_ref: EvaluationRubricRef
    change_kind: EvaluationChangeKind
    baseline_status: ScoreStatus | None
    candidate_status: ScoreStatus | None
    baseline_criterion_refs: tuple[EvaluationCriterionRef, ...]
    candidate_criterion_refs: tuple[EvaluationCriterionRef, ...]
    delta: RationalScoreDelta | None


@dataclass(frozen=True, slots=True)
class EvaluationRepetitionComparison:
    repetition_index: int
    change_kind: EvaluationChangeKind
    verdict_transition: EvaluationVerdictTransition | None
    assertions: tuple[EvaluationAssertionComparison, ...]
    scores: tuple[EvaluationScoreComparison, ...]
    rubrics: tuple[EvaluationRubricComparison, ...]


@dataclass(frozen=True, slots=True)
class EvaluationCaseComparison:
    case_id: EvaluationCaseId
    change_kind: EvaluationChangeKind
    verdict_transition: EvaluationVerdictTransition | None
    assertions: tuple[EvaluationAssertionComparison, ...]
    scores: tuple[EvaluationScoreComparison, ...]
    rubrics: tuple[EvaluationRubricComparison, ...]
    repetitions: tuple[EvaluationRepetitionComparison, ...]


@dataclass(frozen=True, slots=True)
class EvaluationComparisonSummary:
    unchanged_count: int
    added_count: int
    removed_count: int
    changed_count: int


@dataclass(frozen=True, slots=True)
class EvaluationSuiteComparison:
    suite_id: EvaluationSuiteId
    change_kind: EvaluationChangeKind
    verdict_transition: EvaluationVerdictTransition
    cases: tuple[EvaluationCaseComparison, ...]
    summary: EvaluationComparisonSummary


class EvaluationReportComparator:
    """Identity-aligned descriptive comparison without acceptance semantics."""

    def compare(
        self,
        baseline: EvaluationSuiteReport,
        candidate: EvaluationSuiteReport,
    ) -> EvaluationSuiteComparison:
        if type(baseline) is not EvaluationSuiteReport or type(candidate) is not EvaluationSuiteReport:
            raise TypeError("comparison inputs must be EvaluationSuiteReport values")
        if baseline.suite_id != candidate.suite_id:
            raise ValueError("comparison suite IDs must match")
        cases = tuple(
            _compare_case(left, right)
            for left, right in _align(
                baseline.cases, candidate.cases, lambda item: item.case_id
            )
        )
        counts = {kind: 0 for kind in EvaluationChangeKind}
        for case in cases:
            counts[case.change_kind] += 1
        kind = EvaluationChangeKind.UNCHANGED if baseline == candidate else EvaluationChangeKind.CHANGED
        return EvaluationSuiteComparison(
            baseline.suite_id,
            kind,
            EvaluationVerdictTransition(baseline.verdict, candidate.verdict),
            cases,
            EvaluationComparisonSummary(
                counts[EvaluationChangeKind.UNCHANGED],
                counts[EvaluationChangeKind.ADDED],
                counts[EvaluationChangeKind.REMOVED],
                counts[EvaluationChangeKind.CHANGED],
            ),
        )


def _compare_case(
    baseline: EvaluationCaseReport | None,
    candidate: EvaluationCaseReport | None,
) -> EvaluationCaseComparison:
    source = baseline if baseline is not None else candidate
    if source is None:
        raise AssertionError("aligned case requires one side")
    repetitions = tuple(
        _compare_repetition(left, right)
        for left, right in _align(
            baseline.repetitions if baseline else (),
            candidate.repetitions if candidate else (),
            lambda item: item.repetition_index,
        )
    )
    transition = (
        EvaluationVerdictTransition(baseline.verdict, candidate.verdict)
        if baseline is not None and candidate is not None
        else None
    )
    return EvaluationCaseComparison(
        source.case_id,
        _kind(baseline, candidate),
        transition,
        tuple(
            _compare_assertion(left, right)
            for left, right in _align(
                baseline.assertions if baseline else (),
                candidate.assertions if candidate else (),
                lambda item: item.assertion_ref,
            )
        ),
        tuple(
            _compare_score(left, right)
            for left, right in _align(
                baseline.scores if baseline else (),
                candidate.scores if candidate else (),
                lambda item: item.criterion_ref,
            )
        ),
        tuple(
            _compare_rubric(left, right)
            for left, right in _align(
                baseline.rubrics if baseline else (),
                candidate.rubrics if candidate else (),
                lambda item: item.rubric_ref,
            )
        ),
        repetitions,
    )


def _compare_repetition(
    baseline: EvaluationRepetitionReport | None,
    candidate: EvaluationRepetitionReport | None,
) -> EvaluationRepetitionComparison:
    source = baseline if baseline is not None else candidate
    if source is None:
        raise AssertionError("aligned repetition requires one side")
    transition = (
        EvaluationVerdictTransition(baseline.verdict, candidate.verdict)
        if baseline is not None
        and candidate is not None
        and baseline.verdict is not None
        and candidate.verdict is not None
        else None
    )
    return EvaluationRepetitionComparison(
        source.repetition_index,
        _kind(baseline, candidate),
        transition,
        tuple(
            _compare_assertion(left, right)
            for left, right in _align(
                baseline.assertions if baseline else (),
                candidate.assertions if candidate else (),
                lambda item: item.assertion_ref,
            )
        ),
        tuple(
            _compare_score(left, right)
            for left, right in _align(
                baseline.scores if baseline else (),
                candidate.scores if candidate else (),
                lambda item: item.criterion_ref,
            )
        ),
        tuple(
            _compare_rubric(left, right)
            for left, right in _align(
                baseline.rubrics if baseline else (),
                candidate.rubrics if candidate else (),
                lambda item: item.rubric_ref,
            )
        ),
    )


def _compare_assertion(
    baseline: EvaluationAssertionReport | None,
    candidate: EvaluationAssertionReport | None,
) -> EvaluationAssertionComparison:
    source = baseline if baseline is not None else candidate
    if source is None:
        raise AssertionError("aligned assertion requires one side")
    return EvaluationAssertionComparison(
        source.assertion_ref,
        _kind(baseline, candidate),
        baseline.kind if baseline else None,
        candidate.kind if candidate else None,
        baseline.verdict if baseline else None,
        candidate.verdict if candidate else None,
    )


def _compare_score(
    baseline: EvaluationScoreReport | None,
    candidate: EvaluationScoreReport | None,
) -> EvaluationScoreComparison:
    source = baseline if baseline is not None else candidate
    if source is None:
        raise AssertionError("aligned score requires one side")
    return EvaluationScoreComparison(
        source.criterion_ref,
        _kind(baseline, candidate),
        baseline.status if baseline else None,
        candidate.status if candidate else None,
        _delta(baseline, candidate),
    )


def _compare_rubric(
    baseline: EvaluationRubricReport | None,
    candidate: EvaluationRubricReport | None,
) -> EvaluationRubricComparison:
    source = baseline if baseline is not None else candidate
    if source is None:
        raise AssertionError("aligned rubric requires one side")
    return EvaluationRubricComparison(
        source.rubric_ref,
        _kind(baseline, candidate),
        baseline.status if baseline else None,
        candidate.status if candidate else None,
        baseline.criterion_refs if baseline else (),
        candidate.criterion_refs if candidate else (),
        _delta(baseline, candidate),
    )


def _delta(
    baseline: EvaluationScoreReport | EvaluationRubricReport | None,
    candidate: EvaluationScoreReport | EvaluationRubricReport | None,
) -> RationalScoreDelta | None:
    if (
        baseline is None
        or candidate is None
        or baseline.status is not ScoreStatus.SCORED
        or candidate.status is not ScoreStatus.SCORED
        or baseline.score is None
        or candidate.score is None
    ):
        return None
    return RationalScoreDelta.between(baseline.score, candidate.score)


def _kind(baseline: object | None, candidate: object | None) -> EvaluationChangeKind:
    if baseline is None:
        return EvaluationChangeKind.ADDED
    if candidate is None:
        return EvaluationChangeKind.REMOVED
    return EvaluationChangeKind.UNCHANGED if baseline == candidate else EvaluationChangeKind.CHANGED


def _align[T, K](
    baseline: tuple[T, ...],
    candidate: tuple[T, ...],
    identity: Callable[[T], K],
) -> tuple[tuple[T | None, T | None], ...]:
    candidate_by_id = {identity(item): item for item in candidate}
    pairs: list[tuple[T | None, T | None]] = []
    baseline_ids: set[K] = set()
    for item in baseline:
        item_id = identity(item)
        baseline_ids.add(item_id)
        pairs.append((item, candidate_by_id.get(item_id)))
    pairs.extend(
        (None, item) for item in candidate if identity(item) not in baseline_ids
    )
    return tuple(pairs)
