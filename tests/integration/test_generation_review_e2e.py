from collections.abc import Mapping
from dataclasses import replace

from backend.agent_runtime.agents.generation import GenerationGuardDisposition
from backend.agent_runtime.contracts import (
    GateDecisionValue,
    OverallAssessment,
    ProductionValidationState,
)
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
from tests.e2e.core.catalog import CANONICAL_PEDAGOGICAL_SUITE, scenario_for
from tests.e2e.core.expectations import PEDAGOGICAL_ASSERTION_CATALOG
from tests.e2e.core.generation_adapters import (
    DFixtureFactory,
    DInputFactory,
    DInvariantEvaluator,
    FixedEvaluationClock,
    build_d_executor,
    run_human_gate_sequence,
)


def test_scn_03_and_scn_05_run_real_agent_owners_through_full_harness() -> None:
    scenarios = tuple(
        scenario
        for code in ("SCN-03", "SCN-05")
        if (scenario := scenario_for(EvaluationCaseCode(code))) is not None
    )
    assert len(scenarios) == 2
    suite = replace(
        CANONICAL_PEDAGOGICAL_SUITE,
        cases=tuple(scenario.case for scenario in scenarios),
    )
    executor = build_d_executor(None)
    result = EvaluationRunner(
        input_factory=DInputFactory(),
        target_executor=executor,
        clock=FixedEvaluationClock(1_777_001_000),
        fixture_factory=DFixtureFactory(),
        invariant_evaluator=DInvariantEvaluator(),
    ).run_suite(
        suite,
        tuple(
            EvaluationCaseRunConfiguration(
                scenario.case.case_id, PEDAGOGICAL_ASSERTION_CATALOG
            )
            for scenario in scenarios
        ),
    )
    report = EvaluationReportProjector().project(suite, result)
    artifacts = EvaluationArtifactFactory()
    json_artifact = artifacts.create(
        report,
        EvaluationArtifactName("scn-03-05.json"),
        EvaluationArtifactFormat.JSON,
    )
    markdown_artifact = artifacts.create(
        report,
        EvaluationArtifactName("scn-03-05.md"),
        EvaluationArtifactFormat.MARKDOWN,
    )

    assert result.verdict is EvaluationVerdict.PASS
    assert tuple(
        len(case.repetition_results[0].assertion_results)
        for case in result.case_results
    ) == (4, 4)
    for case in result.case_results:
        repetition = case.repetition_results[0]
        assert all(
            assertion.verdict is EvaluationVerdict.PASS
            for assertion in repetition.assertion_results
        )
        assert repetition.score_results == ()
        assert repetition.rubric_results == ()

    scn03 = executor.witnesses["SCN-03"]
    assert scn03.generation.port_call_count == 1
    assert scn03.generation.candidate.validation_state is ProductionValidationState.CANDIDATE
    assert scn03.generation.candidate.lineage["capability_id"] == "CAP-G01"
    assert scn03.generation.candidate.lineage["generation_operation"] == "GENERATE"
    assert scn03.generation.guard.disposition in {
        GenerationGuardDisposition.ALLOW,
        GenerationGuardDisposition.ALLOW_WITH_WARNINGS,
    }
    sections = scn03.generation.candidate.structured_payload["sections"]
    assert isinstance(sections, Mapping)
    assert tuple(sections) == (
        "objective",
        "concept",
        "example",
        "summary",
    )
    assert tuple(step.executor.kind.value for step in scn03.plan.steps) == ("AG-03",)

    scn05 = executor.witnesses["SCN-05"]
    assert scn05.review is not None
    assert scn05.review_port_call_count == 1
    assert scn05.review.target_production_ref.object_ref.entity_id.value == (
        scn05.generation.candidate.production_id
    )
    assert scn05.review.target_production_ref.version_ref.value == "candidate-v1"
    assert scn05.review.overall_assessment is OverallAssessment.ACCEPTABLE
    assert scn05.gate is not None
    assert scn05.gate.disposition is GateResolutionDisposition.APPROVED
    assert scn05.gate.decision_value is GateDecisionValue.APPROVED
    assert scn05.gate.to_policy_facts().matrix_gate_satisfied is True
    assert scn05.continuation_count == 1
    assert scn05.events[-4:] == (
        "review-complete",
        "gate-request",
        "external-APPROVED",
        "continuation",
    )

    for raw_text in executor.raw_texts:
        assert raw_text
        assert raw_text.encode("utf-8") not in json_artifact.content
        assert raw_text.encode("utf-8") not in markdown_artifact.content
    assert b"PASS" in json_artifact.content
    assert b"PASS" in markdown_artifact.content


def test_scn_05_rejected_gate_has_no_downstream_continuation() -> None:
    witness = run_human_gate_sequence(GateDecisionValue.REJECTED)

    assert witness.resolution.disposition is GateResolutionDisposition.REJECTED
    assert witness.continuation_count == 0
