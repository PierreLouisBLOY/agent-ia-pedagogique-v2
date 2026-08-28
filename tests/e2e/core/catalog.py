from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.orchestration.workflows import (
    BASELINE_WORKFLOW_CATALOG,
    WorkflowKind,
)
from evaluation_harness import (
    EVALUATION_SCHEMA_V1_0,
    EvaluationCase,
    EvaluationCaseCode,
    EvaluationCaseId,
    EvaluationFixtureRef,
    EvaluationInfrastructureErrorPolicy,
    EvaluationInputFactoryRef,
    EvaluationRubric,
    EvaluationSuite,
    EvaluationSuiteCode,
    EvaluationSuiteId,
    EvaluationTagCode,
    EvaluationTargetCode,
    EvaluationTargetKind,
    EvaluationTargetRef,
)
from tests.e2e.core.expectations import SCENARIO_EXPECTATIONS, expectations_for
from tests.e2e.core.fixtures import (
    SYNTHETIC_PEDAGOGICAL_FIXTURES,
    PedagogicalLevelCode,
    PedagogicalSectionCode,
    SyntheticPedagogicalFixture,
)

PEDAGOGICAL_INPUT_FACTORY_REF = EvaluationInputFactoryRef(
    "pedagogical-corpus-input"
)


class PedagogicalIntentCode(StrEnum):
    """Test-only reporting vocabulary; values are not runtime capabilities."""

    RESOURCE_ORGANIZATION = "resource-organization"
    RESOURCE_SEARCH = "resource-search"
    COURSE_CREATION = "course-creation"
    RESOURCE_TRANSFORMATION = "resource-transformation"
    EXERCISE_CREATION = "exercise-creation"
    ASSESSMENT_CREATION = "assessment-creation"
    CORRECTION_REMEDIATION = "correction-remediation"
    QCM_QUIZ_CREATION = "qcm-quiz-creation"


@dataclass(frozen=True, slots=True)
class CanonicalPedagogicalScenario:
    """Test-only composition of one real 12.14 EvaluationCase."""

    case: EvaluationCase
    level: PedagogicalLevelCode
    intent: PedagogicalIntentCode
    workflow_kinds: tuple[WorkflowKind, ...]
    fixture: SyntheticPedagogicalFixture
    section_codes: tuple[PedagogicalSectionCode, ...]
    rubric: EvaluationRubric

    def __post_init__(self) -> None:
        if not isinstance(self.case, EvaluationCase):
            raise TypeError("case must be an EvaluationCase")
        if not isinstance(self.level, PedagogicalLevelCode):
            raise TypeError("level must be a PedagogicalLevelCode")
        if not isinstance(self.intent, PedagogicalIntentCode):
            raise TypeError("intent must be a PedagogicalIntentCode")
        if type(self.workflow_kinds) is not tuple or not self.workflow_kinds:
            raise ValueError("workflow_kinds must be a non-empty tuple")
        if any(type(kind) is not WorkflowKind for kind in self.workflow_kinds):
            raise TypeError("workflow_kinds must contain WorkflowKind values")
        if len(self.workflow_kinds) != len(set(self.workflow_kinds)):
            raise ValueError("workflow_kinds must be unique within a scenario")
        if not isinstance(self.fixture, SyntheticPedagogicalFixture):
            raise TypeError("fixture must be a SyntheticPedagogicalFixture")
        if self.fixture.level is not self.level:
            raise ValueError("scenario level must match its fixture")
        if self.case.fixture_ref != self.fixture.fixture_ref:
            raise ValueError("EvaluationCase fixture ref must resolve to the fixture")
        if type(self.section_codes) is not tuple or not self.section_codes:
            raise ValueError("section_codes must be a non-empty tuple")
        if any(type(code) is not PedagogicalSectionCode for code in self.section_codes):
            raise TypeError("section_codes must contain PedagogicalSectionCode values")
        if len(self.section_codes) != len(set(self.section_codes)):
            raise ValueError("section_codes must be unique")
        if not isinstance(self.rubric, EvaluationRubric):
            raise TypeError("rubric must be an EvaluationRubric")
        if self.rubric.schema_version != self.case.schema_version:
            raise ValueError("case and rubric schema versions must match")


@dataclass(frozen=True, slots=True)
class _ScenarioDeclaration:
    case_code: str
    title: str
    level: PedagogicalLevelCode
    intent: PedagogicalIntentCode
    workflow_kinds: tuple[WorkflowKind, ...]
    section_codes: tuple[PedagogicalSectionCode, ...]
    transverse_tags: tuple[str, ...] = ()


_DECLARATIONS = (
    _ScenarioDeclaration(
        "SCN-01",
        "Organisation d'une ressource pedagogique synthetique",
        PedagogicalLevelCode.PREMIERE_STMG,
        PedagogicalIntentCode.RESOURCE_ORGANIZATION,
        (WorkflowKind.WF_0,),
        (PedagogicalSectionCode.CONTEXT, PedagogicalSectionCode.SUMMARY),
        ("observability.equivalence",),
    ),
    _ScenarioDeclaration(
        "SCN-02",
        "Recherche de ressources pedagogiques synthetiques",
        PedagogicalLevelCode.TERMINALE_STMG,
        PedagogicalIntentCode.RESOURCE_SEARCH,
        (WorkflowKind.WF_1,),
        (PedagogicalSectionCode.CONCEPT, PedagogicalSectionCode.SUMMARY),
        ("security.evidence-injection",),
    ),
    _ScenarioDeclaration(
        "SCN-03",
        "Creation d'un cours pedagogique synthetique",
        PedagogicalLevelCode.PREMIERE_STMG,
        PedagogicalIntentCode.COURSE_CREATION,
        (WorkflowKind.WF_2,),
        (
            PedagogicalSectionCode.OBJECTIVE,
            PedagogicalSectionCode.CONCEPT,
            PedagogicalSectionCode.EXAMPLE,
            PedagogicalSectionCode.SUMMARY,
        ),
        ("security.authority-smuggling",),
    ),
    _ScenarioDeclaration(
        "SCN-04",
        "Transformation d'une ressource pedagogique synthetique",
        PedagogicalLevelCode.BTS_CG_1,
        PedagogicalIntentCode.RESOURCE_TRANSFORMATION,
        (WorkflowKind.WF_4,),
        (
            PedagogicalSectionCode.CONTEXT,
            PedagogicalSectionCode.CONCEPT,
            PedagogicalSectionCode.EXAMPLE,
            PedagogicalSectionCode.SUMMARY,
        ),
    ),
    _ScenarioDeclaration(
        "SCN-05",
        "Creation et revue d'un exercice sous gate humaine",
        PedagogicalLevelCode.TERMINALE_STMG,
        PedagogicalIntentCode.EXERCISE_CREATION,
        (WorkflowKind.WF_5, WorkflowKind.WF_10),
        (
            PedagogicalSectionCode.CONTEXT,
            PedagogicalSectionCode.QUESTIONS,
            PedagogicalSectionCode.CORRECTION_LINK,
        ),
        ("security.authority-smuggling", "gate.human"),
    ),
    _ScenarioDeclaration(
        "SCN-06",
        "Creation d'une evaluation et d'un bareme synthetiques",
        PedagogicalLevelCode.BTS_CG_1,
        PedagogicalIntentCode.ASSESSMENT_CREATION,
        (WorkflowKind.WF_8, WorkflowKind.WF_6),
        (
            PedagogicalSectionCode.INSTRUCTIONS,
            PedagogicalSectionCode.QUESTIONS,
            PedagogicalSectionCode.MARKING_SCHEME,
        ),
        ("observability.equivalence",),
    ),
    _ScenarioDeclaration(
        "SCN-07",
        "Correction et remediation pedagogiques bornees",
        PedagogicalLevelCode.BTS_CG_2,
        PedagogicalIntentCode.CORRECTION_REMEDIATION,
        (WorkflowKind.WF_1, WorkflowKind.WF_7, WorkflowKind.WF_0),
        (
            PedagogicalSectionCode.CONTEXT,
            PedagogicalSectionCode.CORRECTION_LINK,
            PedagogicalSectionCode.SUMMARY,
        ),
    ),
    _ScenarioDeclaration(
        "SCN-08",
        "Creation de variantes de QCM puis promotion controlee",
        PedagogicalLevelCode.BTS_CG_2,
        PedagogicalIntentCode.QCM_QUIZ_CREATION,
        (WorkflowKind.WF_9, WorkflowKind.WF_3, WorkflowKind.WF_11),
        (
            PedagogicalSectionCode.QUESTION,
            PedagogicalSectionCode.OPTIONS,
            PedagogicalSectionCode.ANSWER_KEY,
            PedagogicalSectionCode.FEEDBACK,
        ),
        (
            "security.exfiltration",
            "recovery.effectful-promotion",
            "observability.equivalence",
        ),
    ),
)


def _case(
    declaration: _ScenarioDeclaration,
    fixture_ref: EvaluationFixtureRef,
) -> EvaluationCase:
    case_code = EvaluationCaseCode(declaration.case_code)
    expectations = expectations_for(case_code)
    if expectations is None:
        raise ValueError("scenario expectations must resolve during declaration")
    return EvaluationCase(
        EvaluationCaseId(f"case.{declaration.case_code.lower()}"),
        EVALUATION_SCHEMA_V1_0,
        case_code,
        declaration.title,
        EvaluationTargetRef(
            EvaluationTargetKind.WORKFLOW,
            EvaluationTargetCode(f"pedagogical.{declaration.case_code.lower()}"),
        ),
        PEDAGOGICAL_INPUT_FACTORY_REF,
        expectations.assertion_refs,
        fixture_ref=fixture_ref,
        tags=(
            EvaluationTagCode("golden"),
            *(EvaluationTagCode(tag) for tag in declaration.transverse_tags),
        ),
        timeout_seconds=30,
    )


CANONICAL_PEDAGOGICAL_SCENARIOS = tuple(
    CanonicalPedagogicalScenario(
        case=_case(declaration, fixture.fixture_ref),
        level=declaration.level,
        intent=declaration.intent,
        workflow_kinds=declaration.workflow_kinds,
        fixture=fixture,
        section_codes=declaration.section_codes,
        rubric=expectations.rubric,
    )
    for declaration, fixture, expectations in zip(
        _DECLARATIONS,
        SYNTHETIC_PEDAGOGICAL_FIXTURES,
        SCENARIO_EXPECTATIONS,
        strict=True,
    )
)


CANONICAL_PEDAGOGICAL_SUITE = EvaluationSuite(
    EvaluationSuiteId("suite.pedagogical-canonical"),
    EVALUATION_SCHEMA_V1_0,
    EvaluationSuiteCode("pedagogical-canonical"),
    "Corpus pedagogique golden canonique",
    tuple(scenario.case for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS),
    EvaluationInfrastructureErrorPolicy.CONTINUE,
    (EvaluationTagCode("golden"),),
)


def scenario_for(case_code: EvaluationCaseCode) -> CanonicalPedagogicalScenario | None:
    if not isinstance(case_code, EvaluationCaseCode):
        raise TypeError("case_code must be an EvaluationCaseCode")
    return next(
        (
            scenario
            for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
            if scenario.case.code == case_code
        ),
        None,
    )


def workflow_coverage() -> tuple[tuple[WorkflowKind, tuple[EvaluationCaseCode, ...]], ...]:
    """Return deterministic traceability without creating a mutable registry."""

    return tuple(
        (
            descriptor.workflow_kind,
            tuple(
                scenario.case.code
                for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
                if descriptor.workflow_kind in scenario.workflow_kinds
            ),
        )
        for descriptor in BASELINE_WORKFLOW_CATALOG.all()
    )
