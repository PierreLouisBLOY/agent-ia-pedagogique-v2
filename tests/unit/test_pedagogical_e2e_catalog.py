from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
from importlib import import_module

import pytest

from backend.agent_runtime.orchestration.workflows import WorkflowKind
from evaluation_harness import (
    EvaluationCase,
    EvaluationCaseCode,
    EvaluationRubric,
    EvaluationTargetKind,
    NormalizedScore,
)
from tests.e2e.core.catalog import (
    CANONICAL_PEDAGOGICAL_SCENARIOS,
    CANONICAL_PEDAGOGICAL_SUITE,
    PEDAGOGICAL_INPUT_FACTORY_REF,
    CanonicalPedagogicalScenario,
    PedagogicalIntentCode,
    scenario_for,
    workflow_coverage,
)
from tests.e2e.core.expectations import (
    PEDAGOGICAL_ASSERTION_CATALOG,
    PEDAGOGICAL_QUALITY_SCORER_REF,
    SCENARIO_EXPECTATIONS,
    expectations_for,
)
from tests.e2e.core.fixtures import (
    MAX_SYNTHETIC_SOURCE_TEXT_LENGTH,
    SYNTHETIC_PEDAGOGICAL_FIXTURES,
    PedagogicalLevelCode,
    PedagogicalSectionCode,
    SyntheticPedagogicalFixture,
    SyntheticSourceEntry,
    SyntheticSourceRef,
    fixture_for,
)

EXPECTED_WORKFLOWS = (
    (WorkflowKind.WF_0,),
    (WorkflowKind.WF_1,),
    (WorkflowKind.WF_2,),
    (WorkflowKind.WF_4,),
    (WorkflowKind.WF_5, WorkflowKind.WF_10),
    (WorkflowKind.WF_8, WorkflowKind.WF_6),
    (WorkflowKind.WF_1, WorkflowKind.WF_7, WorkflowKind.WF_0),
    (WorkflowKind.WF_9, WorkflowKind.WF_3, WorkflowKind.WF_11),
)


def test_catalog_contains_exactly_the_eight_ordered_canonical_scenarios() -> None:
    assert tuple(
        scenario.case.code.value for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
    ) == tuple(f"SCN-{index:02d}" for index in range(1, 9))
    assert tuple(
        scenario.workflow_kinds for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
    ) == EXPECTED_WORKFLOWS
    assert CANONICAL_PEDAGOGICAL_SUITE.cases == tuple(
        scenario.case for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
    )


def test_each_scenario_composes_a_real_workflow_evaluation_case() -> None:
    for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS:
        assert type(scenario.case) is EvaluationCase
        assert scenario.case.target.kind is EvaluationTargetKind.WORKFLOW
        assert scenario.case.input_factory_ref == PEDAGOGICAL_INPUT_FACTORY_REF
        assert scenario.case.repeat_count == 1
        assert scenario.case.timeout_seconds == 30
        assert scenario_for(scenario.case.code) == scenario


def test_fixture_and_assertion_references_all_resolve() -> None:
    for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS:
        assert scenario.case.fixture_ref is not None
        assert fixture_for(scenario.case.fixture_ref) == scenario.fixture
        declaration = expectations_for(scenario.case.code)
        assert declaration is not None
        assert declaration.assertion_refs == scenario.case.assertion_refs
        assert declaration.rubric == scenario.rubric
        assert all(
            PEDAGOGICAL_ASSERTION_CATALOG.resolve(assertion_ref) is not None
            for assertion_ref in scenario.case.assertion_refs
        )


def test_workflow_coverage_is_complete_canonical_and_stably_traceable() -> None:
    coverage = workflow_coverage()
    assert tuple(kind for kind, _ in coverage) == tuple(WorkflowKind)
    assert all(case_codes for _, case_codes in coverage)
    assert {
        kind for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS for kind in scenario.workflow_kinds
    } == set(WorkflowKind)
    assert {kind for kind, _ in coverage} == set(WorkflowKind)
    assert dict(coverage)[WorkflowKind.WF_0] == (
        EvaluationCaseCode("SCN-01"),
        EvaluationCaseCode("SCN-07"),
    )
    assert dict(coverage)[WorkflowKind.WF_11] == (EvaluationCaseCode("SCN-08"),)


def test_all_four_test_only_levels_are_covered() -> None:
    assert {scenario.level for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS} == set(
        PedagogicalLevelCode
    )
    assert tuple(scenario.level for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS) == (
        PedagogicalLevelCode.PREMIERE_STMG,
        PedagogicalLevelCode.TERMINALE_STMG,
        PedagogicalLevelCode.PREMIERE_STMG,
        PedagogicalLevelCode.BTS_CG_1,
        PedagogicalLevelCode.TERMINALE_STMG,
        PedagogicalLevelCode.BTS_CG_1,
        PedagogicalLevelCode.BTS_CG_2,
        PedagogicalLevelCode.BTS_CG_2,
    )


def test_each_test_only_intent_is_used_exactly_once() -> None:
    intents = tuple(scenario.intent for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS)
    assert set(intents) == set(PedagogicalIntentCode)
    assert len(intents) == len(set(intents)) == 8
    assert all(not intent.value.startswith("CAP-") for intent in intents)


def test_fixture_catalog_is_short_offline_synthetic_and_unique() -> None:
    fixture_refs = tuple(
        fixture.fixture_ref for fixture in SYNTHETIC_PEDAGOGICAL_FIXTURES
    )
    source_refs = tuple(
        source.source_ref
        for fixture in SYNTHETIC_PEDAGOGICAL_FIXTURES
        for source in fixture.sources
    )
    assert len(fixture_refs) == len(set(fixture_refs)) == 8
    assert len(source_refs) == len(set(source_refs))
    for fixture in SYNTHETIC_PEDAGOGICAL_FIXTURES:
        assert fixture.level in PedagogicalLevelCode
        assert "synthetic" in fixture.scope_code
        for source in fixture.sources:
            assert len(source.text) <= MAX_SYNTHETIC_SOURCE_TEXT_LENGTH
            assert "://" not in source.text
            assert "@" not in source.text
            assert "C:\\" not in source.text
            assert "/home/" not in source.text


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "https://example.invalid/source",
        "C:\\private\\fixture.txt",
        "/home/person/fixture.txt",
        "person@example.invalid",
        "api_key=synthetic-but-forbidden",
        "x" * (MAX_SYNTHETIC_SOURCE_TEXT_LENGTH + 1),
    ],
)
def test_fixture_model_rejects_live_refs_private_paths_and_secret_like_text(
    unsafe_text: str,
) -> None:
    with pytest.raises(ValueError):
        SyntheticSourceEntry(SyntheticSourceRef("synthetic:unsafe"), "v1", unsafe_text)


def test_fixture_model_requires_adversarial_marker_to_resolve_locally() -> None:
    source = SyntheticSourceEntry(
        SyntheticSourceRef("synthetic:safe"),
        "v1",
        "Court texte synthetique sans donnee personnelle.",
    )
    with pytest.raises(ValueError, match="resolve"):
        SyntheticPedagogicalFixture(
            SYNTHETIC_PEDAGOGICAL_FIXTURES[0].fixture_ref,
            PedagogicalLevelCode.PREMIERE_STMG,
            "safe-synthetic",
            (source,),
            SyntheticSourceRef("synthetic:missing"),
        )


def test_all_identity_namespaces_are_unique() -> None:
    cases = tuple(scenario.case for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS)
    assertion_refs = tuple(
        assertion_ref for case in cases for assertion_ref in case.assertion_refs
    )
    rubric_refs = tuple(scenario.rubric.rubric_ref for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS)
    criterion_refs = tuple(
        criterion.criterion_ref
        for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
        for criterion in scenario.rubric.criteria
    )
    for values in (
        tuple(case.case_id for case in cases),
        tuple(case.code for case in cases),
        assertion_refs,
        rubric_refs,
        criterion_refs,
    ):
        assert len(values) == len(set(values))


def test_soft_rubrics_are_exact_declarations_without_thresholds() -> None:
    for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS:
        assert type(scenario.rubric) is EvaluationRubric
        assert sum(
            (criterion.weight.as_fraction() for criterion in scenario.rubric.criteria),
            Fraction(0, 1),
        ) == Fraction(1, 1)
        assert all(
            criterion.weight == NormalizedScore(1, 2)
            and criterion.scorer_ref == PEDAGOGICAL_QUALITY_SCORER_REF
            for criterion in scenario.rubric.criteria
        )
        assert not hasattr(scenario.rubric, "threshold")
        assert not hasattr(scenario.rubric, "verdict")


def test_pedagogical_marking_scheme_is_not_an_evaluation_rubric() -> None:
    assessment = scenario_for(EvaluationCaseCode("SCN-06"))
    assert assessment is not None
    assert PedagogicalSectionCode.MARKING_SCHEME in assessment.section_codes
    assert not hasattr(PedagogicalSectionCode.MARKING_SCHEME, "criteria")
    assert not hasattr(assessment.rubric, "value")
    assert PedagogicalSectionCode.MARKING_SCHEME.value != assessment.rubric.rubric_ref.value


def test_adversarial_markers_and_transverse_tags_are_minimized() -> None:
    marked = {
        scenario.case.code.value
        for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
        if scenario.fixture.adversarial_marker_ref is not None
    }
    assert marked == {"SCN-02", "SCN-03", "SCN-08"}
    tags = {
        scenario.case.code.value: {tag.value for tag in scenario.case.tags}
        for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
    }
    assert "security.evidence-injection" in tags["SCN-02"]
    assert "recovery.effectful-promotion" in tags["SCN-08"]
    assert "observability.equivalence" in tags["SCN-06"]


def test_scenario_wrapper_is_frozen_slotted_and_has_no_authority_channel() -> None:
    forbidden = {
        "allow",
        "approve",
        "authority",
        "capability",
        "config",
        "metadata",
        "model_name",
        "payload",
        "permission",
        "provider",
        "threshold",
    }
    assert {field.name for field in fields(CanonicalPedagogicalScenario)}.isdisjoint(
        forbidden
    )
    with pytest.raises(FrozenInstanceError):
        CANONICAL_PEDAGOGICAL_SCENARIOS[0].level = (  # type: ignore[misc]
            PedagogicalLevelCode.BTS_CG_2
        )
    assert not hasattr(CANONICAL_PEDAGOGICAL_SCENARIOS[0], "__dict__")


def test_repeated_import_and_reconstruction_are_deterministic() -> None:
    imported = import_module("tests.e2e.core.catalog")
    assert imported.CANONICAL_PEDAGOGICAL_SCENARIOS == CANONICAL_PEDAGOGICAL_SCENARIOS
    assert tuple(
        replace(scenario) for scenario in CANONICAL_PEDAGOGICAL_SCENARIOS
    ) == CANONICAL_PEDAGOGICAL_SCENARIOS
    assert tuple(replace(item) for item in SCENARIO_EXPECTATIONS) == SCENARIO_EXPECTATIONS
