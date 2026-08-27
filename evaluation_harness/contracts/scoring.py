from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from functools import total_ordering
from math import gcd
from typing import Final

from evaluation_harness.contracts.identity import (
    EvaluationCriterionRef,
    EvaluationObservationRef,
    EvaluationRubricRef,
    EvaluationSchemaVersion,
    EvaluationScorerRef,
    require_supported_schema_version,
)

MAX_SCORE_COMPONENT: Final = 10**128 - 1
MAX_SCORING_OBSERVATIONS_PER_CRITERION: Final = 16
MAX_RUBRIC_CRITERIA: Final = 32
MAX_SCORE_RESULTS_PER_CASE: Final = 64
MAX_RUBRIC_RESULTS_PER_CASE: Final = 16


@total_ordering
@dataclass(frozen=True, slots=True)
class NormalizedScore:
    """Canonical exact rational in [0, 1], independent from Decimal context."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise TypeError("score components must be integers")
        if self.denominator <= 0:
            raise ValueError("score denominator must be positive")
        if self.numerator < 0 or self.numerator > self.denominator:
            raise ValueError("normalized score must be between zero and one")
        if (
            self.numerator > MAX_SCORE_COMPONENT
            or self.denominator > MAX_SCORE_COMPONENT
        ):
            raise ValueError("score components exceed the offline limit")
        divisor = gcd(self.numerator, self.denominator)
        object.__setattr__(self, "numerator", self.numerator // divisor)
        object.__setattr__(self, "denominator", self.denominator // divisor)

    def __lt__(self, other: NormalizedScore) -> bool:
        if not isinstance(other, NormalizedScore):
            raise TypeError("normalized scores compare only with normalized scores")
        return self.numerator * other.denominator < other.numerator * self.denominator

    def as_fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    @classmethod
    def from_fraction(cls, value: Fraction) -> NormalizedScore:
        if type(value) is not Fraction:
            raise TypeError("value must be a Fraction")
        return cls(value.numerator, value.denominator)

    @classmethod
    def zero(cls) -> NormalizedScore:
        return cls(0, 1)

    @classmethod
    def whole(cls) -> NormalizedScore:
        return cls(1, 1)


class ScoreStatus(Enum):
    SCORED = "SCORED"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"


class ScoreReasonCode(Enum):
    SCORER_NOT_FOUND = "SCORER_NOT_FOUND"
    SCORER_INCONCLUSIVE = "SCORER_INCONCLUSIVE"
    SCORER_EVALUATION_ERROR = "SCORER_EVALUATION_ERROR"
    INVALID_SCORE_VALUE = "INVALID_SCORE_VALUE"
    OBSERVATION_NOT_FOUND = "OBSERVATION_NOT_FOUND"
    OBSERVATION_TYPE_UNSUPPORTED = "OBSERVATION_TYPE_UNSUPPORTED"
    OBSERVATION_RESOLUTION_ERROR = "OBSERVATION_RESOLUTION_ERROR"
    INVALID_SCORING_CONFIGURATION = "INVALID_SCORING_CONFIGURATION"
    RUBRIC_CRITERION_MISSING = "RUBRIC_CRITERION_MISSING"
    RUBRIC_CRITERION_ERROR = "RUBRIC_CRITERION_ERROR"
    RUBRIC_CRITERION_INCONCLUSIVE = "RUBRIC_CRITERION_INCONCLUSIVE"
    RUBRIC_WEIGHT_INVALID = "RUBRIC_WEIGHT_INVALID"
    RUBRIC_AGGREGATION_UNAVAILABLE = "RUBRIC_AGGREGATION_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ScorerOutcome:
    status: ScoreStatus
    score: NormalizedScore | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ScoreStatus):
            raise TypeError("status must be a ScoreStatus")
        if self.status is ScoreStatus.SCORED:
            if type(self.score) is not NormalizedScore:
                raise ValueError("a SCORED outcome requires a normalized score")
        elif self.score is not None:
            raise ValueError("a non-SCORED outcome cannot carry a score")


@dataclass(frozen=True, slots=True)
class EvaluationScoringCriterionSpec:
    schema_version: EvaluationSchemaVersion
    criterion_ref: EvaluationCriterionRef
    scorer_ref: EvaluationScorerRef
    observation_refs: tuple[EvaluationObservationRef, ...]
    weight: NormalizedScore

    def __post_init__(self) -> None:
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.criterion_ref, EvaluationCriterionRef):
            raise TypeError("criterion_ref must be an EvaluationCriterionRef")
        if not isinstance(self.scorer_ref, EvaluationScorerRef):
            raise TypeError("scorer_ref must be an EvaluationScorerRef")
        if type(self.observation_refs) is not tuple:
            raise TypeError("observation_refs must be a tuple")
        if not self.observation_refs:
            raise ValueError("a scoring criterion requires observations")
        if len(self.observation_refs) > MAX_SCORING_OBSERVATIONS_PER_CRITERION:
            raise ValueError("too many observations for one scoring criterion")
        if any(
            type(reference) is not EvaluationObservationRef
            for reference in self.observation_refs
        ):
            raise TypeError("observation_refs must contain EvaluationObservationRef")
        if len(self.observation_refs) != len(set(self.observation_refs)):
            raise ValueError("scoring observation refs must be unique")
        if type(self.weight) is not NormalizedScore:
            raise TypeError("weight must be a NormalizedScore")
        if self.weight.numerator == 0:
            raise ValueError("criterion weight must be strictly positive")


@dataclass(frozen=True, slots=True)
class EvaluationRubric:
    schema_version: EvaluationSchemaVersion
    rubric_ref: EvaluationRubricRef
    criteria: tuple[EvaluationScoringCriterionSpec, ...]

    def __post_init__(self) -> None:
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.rubric_ref, EvaluationRubricRef):
            raise TypeError("rubric_ref must be an EvaluationRubricRef")
        if type(self.criteria) is not tuple:
            raise TypeError("rubric criteria must be a tuple")
        if not self.criteria:
            raise ValueError("a rubric requires at least one criterion")
        if len(self.criteria) > MAX_RUBRIC_CRITERIA:
            raise ValueError("rubric exceeds the offline criterion limit")
        if any(
            type(criterion) is not EvaluationScoringCriterionSpec
            for criterion in self.criteria
        ):
            raise TypeError("rubric criteria contain an unsupported value")
        if any(
            criterion.schema_version != self.schema_version
            for criterion in self.criteria
        ):
            raise ValueError("rubric criterion schema versions must match")
        refs = tuple(criterion.criterion_ref for criterion in self.criteria)
        if len(refs) != len(set(refs)):
            raise ValueError("rubric criterion refs must be unique")
        total_weight = sum(
            (criterion.weight.as_fraction() for criterion in self.criteria),
            start=Fraction(0, 1),
        )
        if total_weight != Fraction(1, 1):
            raise ValueError("rubric weights must sum exactly to one")


@dataclass(frozen=True, slots=True)
class ScoreResult:
    schema_version: EvaluationSchemaVersion
    criterion_ref: EvaluationCriterionRef
    scorer_ref: EvaluationScorerRef
    status: ScoreStatus
    score: NormalizedScore | None = None
    reason_code: ScoreReasonCode | None = None

    def __post_init__(self) -> None:
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.criterion_ref, EvaluationCriterionRef):
            raise TypeError("criterion_ref must be an EvaluationCriterionRef")
        if not isinstance(self.scorer_ref, EvaluationScorerRef):
            raise TypeError("scorer_ref must be an EvaluationScorerRef")
        _validate_score_state(self.status, self.score, self.reason_code)
        if self.status is ScoreStatus.INCONCLUSIVE and (
            self.reason_code is not ScoreReasonCode.SCORER_INCONCLUSIVE
        ):
            raise ValueError("an inconclusive score requires its closed reason")
        if self.status is ScoreStatus.ERROR and (
            self.reason_code is ScoreReasonCode.SCORER_INCONCLUSIVE
        ):
            raise ValueError("an error score cannot use an inconclusive reason")


@dataclass(frozen=True, slots=True)
class RubricScoreResult:
    schema_version: EvaluationSchemaVersion
    rubric_ref: EvaluationRubricRef
    status: ScoreStatus
    criterion_results: tuple[ScoreResult, ...]
    score: NormalizedScore | None = None
    reason_code: ScoreReasonCode | None = None

    def __post_init__(self) -> None:
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.rubric_ref, EvaluationRubricRef):
            raise TypeError("rubric_ref must be an EvaluationRubricRef")
        if type(self.criterion_results) is not tuple:
            raise TypeError("criterion_results must be a tuple")
        if len(self.criterion_results) > MAX_RUBRIC_CRITERIA:
            raise ValueError("too many criterion results for one rubric")
        if any(type(result) is not ScoreResult for result in self.criterion_results):
            raise TypeError("criterion_results must contain ScoreResult values")
        refs = tuple(result.criterion_ref for result in self.criterion_results)
        if len(refs) != len(set(refs)):
            raise ValueError("rubric criterion result refs must be unique")
        if any(
            result.schema_version != self.schema_version
            for result in self.criterion_results
        ):
            raise ValueError("rubric criterion result schema versions must match")
        _validate_score_state(self.status, self.score, self.reason_code)
        if self.status is ScoreStatus.INCONCLUSIVE and (
            self.reason_code is not ScoreReasonCode.RUBRIC_CRITERION_INCONCLUSIVE
        ):
            raise ValueError("an inconclusive rubric requires its closed reason")
        if self.status is ScoreStatus.SCORED and (
            not self.criterion_results
            or any(
                result.status is not ScoreStatus.SCORED
                for result in self.criterion_results
            )
        ):
            raise ValueError("a scored rubric requires only scored criteria")
        if self.status is ScoreStatus.INCONCLUSIVE and (
            not any(
                result.status is ScoreStatus.INCONCLUSIVE
                for result in self.criterion_results
            )
            or any(
                result.status is ScoreStatus.ERROR
                for result in self.criterion_results
            )
        ):
            raise ValueError("an inconclusive rubric requires inconclusive criteria")
        if self.status is ScoreStatus.ERROR and (
            self.reason_code is ScoreReasonCode.RUBRIC_CRITERION_INCONCLUSIVE
        ):
            raise ValueError("an error rubric cannot use an inconclusive reason")


def _validate_score_state(
    status: ScoreStatus,
    score: NormalizedScore | None,
    reason_code: ScoreReasonCode | None,
) -> None:
    if not isinstance(status, ScoreStatus):
        raise TypeError("status must be a ScoreStatus")
    if score is not None and type(score) is not NormalizedScore:
        raise TypeError("score must be a NormalizedScore or None")
    if reason_code is not None and not isinstance(reason_code, ScoreReasonCode):
        raise TypeError("reason_code must be a ScoreReasonCode or None")
    if status is ScoreStatus.SCORED:
        if score is None or reason_code is not None:
            raise ValueError("a SCORED result requires only a normalized score")
    elif score is not None or reason_code is None:
        raise ValueError("a non-SCORED result requires only a closed reason code")
