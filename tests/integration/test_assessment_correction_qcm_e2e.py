from dataclasses import replace

from backend.agent_runtime.contracts import OverallAssessment, ProductionValidationState
from backend.agent_runtime.gates import GateResolutionDisposition
from evaluation_harness import (
    EvaluationArtifactFactory,
    EvaluationArtifactFormat,
    EvaluationArtifactName,
    EvaluationCaseCode,
    EvaluationCaseRunConfiguration,
    EvaluationReportProjector,
    EvaluationRunner,
    EvaluationVerdict,
)
from tests.e2e.core.assessment_adapters import (
    EAssessmentTargetExecutor,
    EFixtureFactory,
    EInputFactory,
    EInvariantEvaluator,
    FixedEvaluationClock,
)
from tests.e2e.core.assessment_bindings import Scn06Witness, Scn07Witness, Scn08Witness
from tests.e2e.core.catalog import CANONICAL_PEDAGOGICAL_SUITE, scenario_for
from tests.e2e.core.expectations import PEDAGOGICAL_ASSERTION_CATALOG


def test_scn06_scn07_scn08_run_full_harness_with_17_hard_assertions() -> None:
    scenarios = tuple(
        scenario
        for code in ("SCN-06", "SCN-07", "SCN-08")
        if (scenario := scenario_for(EvaluationCaseCode(code))) is not None
    )
    assert len(scenarios) == 3
    suite = replace(
        CANONICAL_PEDAGOGICAL_SUITE,
        cases=tuple(scenario.case for scenario in scenarios),
    )
    executor = EAssessmentTargetExecutor()
    result = EvaluationRunner(
        input_factory=EInputFactory(),
        target_executor=executor,
        clock=FixedEvaluationClock(1_777_002_000),
        fixture_factory=EFixtureFactory(),
        invariant_evaluator=EInvariantEvaluator(),
    ).run_suite(
        suite,
        tuple(
            EvaluationCaseRunConfiguration(
                scenario.case.case_id,
                PEDAGOGICAL_ASSERTION_CATALOG,
            )
            for scenario in scenarios
        ),
    )
    report = EvaluationReportProjector().project(suite, result)
    factory = EvaluationArtifactFactory()
    json_artifact = factory.create(
        report,
        EvaluationArtifactName("scn-06-08.json"),
        EvaluationArtifactFormat.JSON,
    )
    markdown_artifact = factory.create(
        report,
        EvaluationArtifactName("scn-06-08.md"),
        EvaluationArtifactFormat.MARKDOWN,
    )

    assert result.verdict is EvaluationVerdict.PASS
    assert tuple(
        len(case.repetition_results[0].assertion_results)
        for case in result.case_results
    ) == (5, 6, 6)
    assert sum(
        len(case.repetition_results[0].assertion_results)
        for case in result.case_results
    ) == 17
    for case in result.case_results:
        repetition = case.repetition_results[0]
        assert all(
            assertion.verdict is EvaluationVerdict.PASS
            for assertion in repetition.assertion_results
        )
        assert repetition.score_results == ()
        assert repetition.rubric_results == ()

    scn06 = executor.witnesses["SCN-06"]
    assert isinstance(scn06, Scn06Witness)
    assert scn06.generation.port_call_count == 1
    assert scn06.generation.candidate.validation_state is ProductionValidationState.CANDIDATE
    assert scn06.events[-3:] == ("GENERATION", "VALIDATION", "REVIEW")
    assert scn06.review.result.overall_assessment is OverallAssessment.ACCEPTABLE

    scn07 = executor.witnesses["SCN-07"]
    assert isinstance(scn07, Scn07Witness)
    assert scn07.correction_result.new_production_ref.version_ref.value == "v2"
    assert scn07.rereview.result.overall_assessment is OverallAssessment.ACCEPTABLE
    assert scn07.final_read.success is True

    scn08 = executor.witnesses["SCN-08"]
    assert isinstance(scn08, Scn08Witness)
    assert scn08.review.result.target_production_ref.object_ref.entity_id.value == (
        scn08.variants[scn08.selected_index].candidate.production_id
    )
    assert scn08.gate_promotion.resolution.disposition is (
        GateResolutionDisposition.APPROVED
    )
    assert scn08.gate_promotion.resolution.to_policy_facts().matrix_gate_satisfied
    assert scn08.gate_promotion.promotion is not None
    assert scn08.gate_promotion.promotion.call_count == 1

    for raw_text in executor.raw_texts:
        assert raw_text
        assert raw_text.encode("utf-8") not in json_artifact.content
        assert raw_text.encode("utf-8") not in markdown_artifact.content
    assert b"PASS" in json_artifact.content
    assert b"PASS" in markdown_artifact.content
