from __future__ import annotations

from evaluation_harness.assertions.ports import (
    EvaluationObservationSourcePort,
    ObservationNotFoundError,
)
from evaluation_harness.contracts.identity import EvaluationObservationRef
from evaluation_harness.contracts.observation import (
    EvaluationObservationValue,
    validate_observation_value,
)
from evaluation_harness.contracts.scoring import (
    EvaluationScoringCriterionSpec,
    ScoreReasonCode,
    ScoreResult,
    ScorerOutcome,
    ScoreStatus,
)
from evaluation_harness.scoring.ports import (
    EvaluationScorerPort,
    ScorerNotFoundError,
)


class _ObservationResolutionFailure(Exception):
    def __init__(self, reason_code: ScoreReasonCode) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code.value)


class ScoreEvaluator:
    """Pure single-criterion evaluator with injected source and scorer."""

    def __init__(
        self,
        observation_source: EvaluationObservationSourcePort,
        scorer: EvaluationScorerPort,
    ) -> None:
        self._observation_source = observation_source
        self._scorer = scorer

    def evaluate(self, spec: EvaluationScoringCriterionSpec) -> ScoreResult:
        cache: dict[EvaluationObservationRef, EvaluationObservationValue] = {}

        def resolve(reference: EvaluationObservationRef) -> EvaluationObservationValue:
            if reference in cache:
                return cache[reference]
            try:
                value = self._observation_source.resolve(reference)
            except ObservationNotFoundError:
                raise _ObservationResolutionFailure(
                    ScoreReasonCode.OBSERVATION_NOT_FOUND
                ) from None
            except Exception:
                raise _ObservationResolutionFailure(
                    ScoreReasonCode.OBSERVATION_RESOLUTION_ERROR
                ) from None
            try:
                validate_observation_value(value)
            except (TypeError, ValueError):
                raise _ObservationResolutionFailure(
                    ScoreReasonCode.OBSERVATION_TYPE_UNSUPPORTED
                ) from None
            cache[reference] = value
            return value

        try:
            observations = tuple(resolve(reference) for reference in spec.observation_refs)
        except _ObservationResolutionFailure as failure:
            return _error_result(spec, failure.reason_code)
        try:
            outcome = self._scorer.score(spec.scorer_ref, observations)
        except ScorerNotFoundError:
            return _error_result(spec, ScoreReasonCode.SCORER_NOT_FOUND)
        except Exception:
            return _error_result(spec, ScoreReasonCode.SCORER_EVALUATION_ERROR)
        if type(outcome) is not ScorerOutcome:
            return _error_result(spec, ScoreReasonCode.INVALID_SCORE_VALUE)
        if outcome.status is ScoreStatus.SCORED:
            return ScoreResult(
                spec.schema_version,
                spec.criterion_ref,
                spec.scorer_ref,
                ScoreStatus.SCORED,
                score=outcome.score,
            )
        if outcome.status is ScoreStatus.INCONCLUSIVE:
            return ScoreResult(
                spec.schema_version,
                spec.criterion_ref,
                spec.scorer_ref,
                ScoreStatus.INCONCLUSIVE,
                reason_code=ScoreReasonCode.SCORER_INCONCLUSIVE,
            )
        return _error_result(spec, ScoreReasonCode.SCORER_EVALUATION_ERROR)


def _error_result(
    spec: EvaluationScoringCriterionSpec,
    reason_code: ScoreReasonCode,
) -> ScoreResult:
    return ScoreResult(
        spec.schema_version,
        spec.criterion_ref,
        spec.scorer_ref,
        ScoreStatus.ERROR,
        reason_code=reason_code,
    )
