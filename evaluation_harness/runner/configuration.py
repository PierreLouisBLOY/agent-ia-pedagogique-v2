from __future__ import annotations

from dataclasses import dataclass, field

from evaluation_harness.assertions.catalog import EvaluationAssertionCatalog
from evaluation_harness.contracts.identity import EvaluationCaseId
from evaluation_harness.contracts.scoring import (
    MAX_RUBRIC_RESULTS_PER_CASE,
    MAX_SCORE_RESULTS_PER_CASE,
    EvaluationRubric,
    EvaluationScoringCriterionSpec,
)


@dataclass(frozen=True, slots=True)
class EvaluationCaseScoringPlan:
    criteria: tuple[EvaluationScoringCriterionSpec, ...] = ()
    rubrics: tuple[EvaluationRubric, ...] = ()

    def __post_init__(self) -> None:
        if type(self.criteria) is not tuple:
            raise TypeError("scoring plan criteria must be a tuple")
        if len(self.criteria) > MAX_SCORE_RESULTS_PER_CASE:
            raise ValueError("scoring plan has too many criteria")
        if any(
            type(criterion) is not EvaluationScoringCriterionSpec
            for criterion in self.criteria
        ):
            raise TypeError("scoring plan criteria contain an unsupported value")
        criterion_refs = tuple(item.criterion_ref for item in self.criteria)
        if len(criterion_refs) != len(set(criterion_refs)):
            raise ValueError("scoring plan criterion refs must be unique")
        if type(self.rubrics) is not tuple:
            raise TypeError("scoring plan rubrics must be a tuple")
        if len(self.rubrics) > MAX_RUBRIC_RESULTS_PER_CASE:
            raise ValueError("scoring plan has too many rubrics")
        if any(type(rubric) is not EvaluationRubric for rubric in self.rubrics):
            raise TypeError("scoring plan rubrics contain an unsupported value")
        rubric_refs = tuple(item.rubric_ref for item in self.rubrics)
        if len(rubric_refs) != len(set(rubric_refs)):
            raise ValueError("scoring plan rubric refs must be unique")
        criteria_by_ref = {item.criterion_ref: item for item in self.criteria}
        for rubric in self.rubrics:
            for criterion in rubric.criteria:
                if criteria_by_ref.get(criterion.criterion_ref) != criterion:
                    raise ValueError(
                        "rubric criteria must match the explicit scoring plan"
                    )


@dataclass(frozen=True, slots=True)
class EvaluationCaseRunConfiguration:
    case_id: EvaluationCaseId
    assertion_catalog: EvaluationAssertionCatalog
    scoring_plan: EvaluationCaseScoringPlan = field(
        default_factory=EvaluationCaseScoringPlan
    )
    explicit_skip: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, EvaluationCaseId):
            raise TypeError("case_id must be an EvaluationCaseId")
        if type(self.assertion_catalog) is not EvaluationAssertionCatalog:
            raise TypeError("assertion_catalog must be an EvaluationAssertionCatalog")
        if type(self.scoring_plan) is not EvaluationCaseScoringPlan:
            raise TypeError("scoring_plan must be an EvaluationCaseScoringPlan")
        if type(self.explicit_skip) is not bool:
            raise TypeError("explicit_skip must be a boolean")
