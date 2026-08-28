from __future__ import annotations

from dataclasses import dataclass

from evaluation_harness import (
    EVALUATION_SCHEMA_V1_0,
    CountAssertionSpec,
    EvaluationAssertionCatalog,
    EvaluationAssertionRef,
    EvaluationCaseCode,
    EvaluationCriterionRef,
    EvaluationInvariantCode,
    EvaluationObservationRef,
    EvaluationRubric,
    EvaluationRubricRef,
    EvaluationScorerRef,
    EvaluationScoringCriterionSpec,
    ExactAssertionSpec,
    ForbiddenContentAssertionSpec,
    InvariantAssertionSpec,
    NormalizedScore,
    RangeAssertionSpec,
    SequenceAssertionSpec,
    StructuralAssertionSpec,
)

PEDAGOGICAL_QUALITY_SCORER_REF = EvaluationScorerRef(
    "pedagogical-quality-fixture-scorer"
)


@dataclass(frozen=True, slots=True)
class ScenarioExpectationDeclaration:
    """Declarative hard expectations and soft rubric for one future execution."""

    case_code: EvaluationCaseCode
    assertion_refs: tuple[EvaluationAssertionRef, ...]
    rubric: EvaluationRubric

    def __post_init__(self) -> None:
        if not isinstance(self.case_code, EvaluationCaseCode):
            raise TypeError("case_code must be an EvaluationCaseCode")
        if type(self.assertion_refs) is not tuple or not self.assertion_refs:
            raise ValueError("assertion_refs must be a non-empty tuple")
        if any(
            type(assertion_ref) is not EvaluationAssertionRef
            for assertion_ref in self.assertion_refs
        ):
            raise TypeError("assertion_refs must contain EvaluationAssertionRef values")
        if len(self.assertion_refs) != len(set(self.assertion_refs)):
            raise ValueError("assertion_refs must be unique")
        if not isinstance(self.rubric, EvaluationRubric):
            raise TypeError("rubric must be an EvaluationRubric")


def _assertion_ref(scenario: str, code: str) -> EvaluationAssertionRef:
    return EvaluationAssertionRef(f"{scenario}.hard.{code}")


def _observation(scenario: str, code: str) -> EvaluationObservationRef:
    return EvaluationObservationRef(f"{scenario}.{code}")


def _expected(scenario: str, code: str) -> EvaluationObservationRef:
    return EvaluationObservationRef(f"{scenario}.expected.{code}")


def _exact(scenario: str, code: str) -> ExactAssertionSpec:
    return ExactAssertionSpec(
        _assertion_ref(scenario, code),
        EVALUATION_SCHEMA_V1_0,
        _observation(scenario, code),
        _expected(scenario, code),
    )


def _structural(scenario: str, code: str) -> StructuralAssertionSpec:
    return StructuralAssertionSpec(
        _assertion_ref(scenario, code),
        EVALUATION_SCHEMA_V1_0,
        _observation(scenario, code),
        _expected(scenario, code),
    )


def _sequence(scenario: str, code: str) -> SequenceAssertionSpec:
    return SequenceAssertionSpec(
        _assertion_ref(scenario, code),
        EVALUATION_SCHEMA_V1_0,
        _observation(scenario, code),
        _expected(scenario, code),
    )


def _count(scenario: str, code: str, expected_count: int) -> CountAssertionSpec:
    return CountAssertionSpec(
        _assertion_ref(scenario, code),
        EVALUATION_SCHEMA_V1_0,
        _observation(scenario, code),
        expected_count,
    )


def _range(
    scenario: str,
    code: str,
    *,
    minimum: bool = False,
    maximum: bool = False,
) -> RangeAssertionSpec:
    return RangeAssertionSpec(
        _assertion_ref(scenario, code),
        EVALUATION_SCHEMA_V1_0,
        _observation(scenario, code),
        _expected(scenario, f"{code}.minimum") if minimum else None,
        _expected(scenario, f"{code}.maximum") if maximum else None,
    )


def _invariant(scenario: str, code: str) -> InvariantAssertionSpec:
    return InvariantAssertionSpec(
        _assertion_ref(scenario, code),
        EVALUATION_SCHEMA_V1_0,
        _observation(scenario, code),
        EvaluationInvariantCode(f"pedagogical.{scenario}.{code}"),
    )


def _forbidden(
    scenario: str,
    code: str,
    *forbidden_codes: str,
) -> ForbiddenContentAssertionSpec:
    return ForbiddenContentAssertionSpec(
        _assertion_ref(scenario, code),
        EVALUATION_SCHEMA_V1_0,
        _observation(scenario, code),
        tuple(_expected(scenario, item) for item in forbidden_codes),
    )


_SPECS_BY_SCENARIO = (
    (
        "scn-01",
        (
            _exact("scn-01", "workflow"),
            _exact("scn-01", "application-path"),
            _count("scn-01", "route-count", 1),
            _exact("scn-01", "resource-ref"),
        ),
    ),
    (
        "scn-02",
        (
            _exact("scn-02", "workflow"),
            _exact("scn-02", "evidence-path"),
            _invariant("scn-02", "provenance-valid"),
            _range("scn-02", "source-count", minimum=True, maximum=True),
            _invariant("scn-02", "document-instruction-non-authoritative"),
        ),
    ),
    (
        "scn-03",
        (
            _exact("scn-03", "workflow"),
            _exact("scn-03", "generation-path"),
            _structural("scn-03", "required-sections"),
            _forbidden(
                "scn-03",
                "authority-smuggling",
                "authority-marker",
                "gate-marker",
            ),
        ),
    ),
    (
        "scn-04",
        (
            _exact("scn-04", "workflow"),
            _sequence("scn-04", "evidence-generation-order"),
            _invariant("scn-04", "transformation-lineage"),
        ),
    ),
    (
        "scn-05",
        (
            _exact("scn-05", "workflow"),
            _sequence("scn-05", "generation-review-order"),
            _invariant("scn-05", "gate-before-downstream"),
            _invariant("scn-05", "review-performed"),
        ),
    ),
    (
        "scn-06",
        (
            _exact("scn-06", "workflow"),
            _range("scn-06", "evidence-fanout-count", minimum=True),
            _sequence("scn-06", "join-before-generation"),
            _sequence("scn-06", "validation-review-order"),
            _structural("scn-06", "assessment-marking-scheme"),
        ),
    ),
    (
        "scn-07",
        (
            _exact("scn-07", "workflow"),
            _invariant("scn-07", "evidence-available"),
            _invariant("scn-07", "correction-version-increases"),
            _sequence("scn-07", "review-correction-order"),
            _invariant("scn-07", "bounded-stop"),
            _exact("scn-07", "final-application-path"),
        ),
    ),
    (
        "scn-08",
        (
            _exact("scn-08", "workflow"),
            _range("scn-08", "variant-count", minimum=True),
            _sequence("scn-08", "join-selection-order"),
            _invariant("scn-08", "independent-review"),
            _sequence("scn-08", "validation-gate-promotion-order"),
            _range("scn-08", "render-effect-count", maximum=True),
        ),
    ),
)


PEDAGOGICAL_ASSERTION_CATALOG = EvaluationAssertionCatalog(
    tuple(spec for _, specs in _SPECS_BY_SCENARIO for spec in specs)
)


_RUBRIC_CRITERIA = (
    ("scn-01", ("clarity", "organization-utility")),
    ("scn-02", ("relevance", "coverage")),
    ("scn-03", ("clarity", "level-adaptation")),
    ("scn-04", ("fidelity", "level-adaptation")),
    ("scn-05", ("difficulty-appropriateness", "instruction-clarity")),
    ("scn-06", ("assessment-clarity", "marking-scheme-coherence")),
    ("scn-07", ("correction-quality", "remediation-clarity")),
    ("scn-08", ("distractor-quality", "feedback-quality")),
)


def _rubric(scenario: str, criteria: tuple[str, str]) -> EvaluationRubric:
    return EvaluationRubric(
        EVALUATION_SCHEMA_V1_0,
        EvaluationRubricRef(f"rubric.{scenario}"),
        tuple(
            EvaluationScoringCriterionSpec(
                EVALUATION_SCHEMA_V1_0,
                EvaluationCriterionRef(f"{scenario}.quality.{criterion}"),
                PEDAGOGICAL_QUALITY_SCORER_REF,
                (_observation(scenario, f"quality.{criterion}"),),
                NormalizedScore(1, 2),
            )
            for criterion in criteria
        ),
    )


SCENARIO_EXPECTATIONS = tuple(
    ScenarioExpectationDeclaration(
        EvaluationCaseCode(scenario.upper()),
        tuple(spec.assertion_ref for spec in specs),
        _rubric(
            scenario,
            next(criteria for code, criteria in _RUBRIC_CRITERIA if code == scenario),
        ),
    )
    for scenario, specs in _SPECS_BY_SCENARIO
)


def expectations_for(case_code: EvaluationCaseCode) -> ScenarioExpectationDeclaration | None:
    if not isinstance(case_code, EvaluationCaseCode):
        raise TypeError("case_code must be an EvaluationCaseCode")
    return next(
        (
            declaration
            for declaration in SCENARIO_EXPECTATIONS
            if declaration.case_code == case_code
        ),
        None,
    )
