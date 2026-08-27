from __future__ import annotations

from fractions import Fraction

from evaluation_harness.contracts.scoring import (
    EvaluationRubric,
    NormalizedScore,
    RubricScoreResult,
    ScoreReasonCode,
    ScoreResult,
    ScoreStatus,
)


class RubricAggregator:
    """Exact rubric aggregation; no threshold or verdict semantics."""

    def aggregate(
        self,
        rubric: EvaluationRubric,
        criterion_results: tuple[ScoreResult, ...],
    ) -> RubricScoreResult:
        if type(rubric) is not EvaluationRubric:
            raise TypeError("rubric must be an EvaluationRubric")
        if type(criterion_results) is not tuple:
            raise TypeError("criterion_results must be a tuple")
        if any(type(result) is not ScoreResult for result in criterion_results):
            raise TypeError("criterion_results must contain ScoreResult values")

        expected_refs = tuple(item.criterion_ref for item in rubric.criteria)
        actual_refs = tuple(item.criterion_ref for item in criterion_results)
        if len(actual_refs) != len(set(actual_refs)):
            return _unavailable(
                rubric,
                ScoreReasonCode.INVALID_SCORING_CONFIGURATION,
            )
        if any(reference not in actual_refs for reference in expected_refs):
            return _unavailable(rubric, ScoreReasonCode.RUBRIC_CRITERION_MISSING)
        if len(actual_refs) != len(expected_refs) or any(
            reference not in expected_refs for reference in actual_refs
        ):
            return _unavailable(
                rubric,
                ScoreReasonCode.INVALID_SCORING_CONFIGURATION,
            )

        ordered_results = tuple(
            next(
                result
                for result in criterion_results
                if result.criterion_ref == criterion.criterion_ref
            )
            for criterion in rubric.criteria
        )
        if any(
            result.schema_version != rubric.schema_version
            or result.scorer_ref != criterion.scorer_ref
            for criterion, result in zip(
                rubric.criteria,
                ordered_results,
                strict=True,
            )
        ):
            return _unavailable(
                rubric,
                ScoreReasonCode.INVALID_SCORING_CONFIGURATION,
            )
        if any(result.status is ScoreStatus.ERROR for result in ordered_results):
            return RubricScoreResult(
                rubric.schema_version,
                rubric.rubric_ref,
                ScoreStatus.ERROR,
                ordered_results,
                reason_code=ScoreReasonCode.RUBRIC_CRITERION_ERROR,
            )
        if any(
            result.status is ScoreStatus.INCONCLUSIVE for result in ordered_results
        ):
            return RubricScoreResult(
                rubric.schema_version,
                rubric.rubric_ref,
                ScoreStatus.INCONCLUSIVE,
                ordered_results,
                reason_code=ScoreReasonCode.RUBRIC_CRITERION_INCONCLUSIVE,
            )

        aggregate = sum(
            (
                criterion.weight.as_fraction() * _required_score(result).as_fraction()
                for criterion, result in zip(
                    rubric.criteria,
                    ordered_results,
                    strict=True,
                )
            ),
            start=Fraction(0, 1),
        )
        try:
            normalized = NormalizedScore.from_fraction(aggregate)
        except ValueError:
            return _unavailable(
                rubric,
                ScoreReasonCode.RUBRIC_AGGREGATION_UNAVAILABLE,
            )
        return RubricScoreResult(
            rubric.schema_version,
            rubric.rubric_ref,
            ScoreStatus.SCORED,
            ordered_results,
            score=normalized,
        )


def _required_score(result: ScoreResult) -> NormalizedScore:
    if result.score is None:
        raise ValueError("a SCORED criterion requires a normalized score")
    return result.score


def _unavailable(
    rubric: EvaluationRubric,
    reason_code: ScoreReasonCode,
) -> RubricScoreResult:
    return RubricScoreResult(
        rubric.schema_version,
        rubric.rubric_ref,
        ScoreStatus.ERROR,
        (),
        reason_code=reason_code,
    )
