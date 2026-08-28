from __future__ import annotations

import json
from dataclasses import replace

from evaluation_harness import (
    EVALUATION_SCHEMA_V1_0,
    EvaluationAssertionCatalog,
    EvaluationAssertionRef,
    EvaluationCase,
    EvaluationCaseCode,
    EvaluationCaseId,
    EvaluationCaseRunConfiguration,
    EvaluationCaseScoringPlan,
    EvaluationCriterionRef,
    EvaluationFixtureRef,
    EvaluationInfrastructureErrorPolicy,
    EvaluationInputFactoryRef,
    EvaluationInvariantCode,
    EvaluationJsonReportRenderer,
    EvaluationMarkdownReportRenderer,
    EvaluationObservationRef,
    EvaluationReportComparator,
    EvaluationReportProjector,
    EvaluationRubric,
    EvaluationRubricRef,
    EvaluationRunner,
    EvaluationScorerRef,
    EvaluationScoringCriterionSpec,
    EvaluationSuite,
    EvaluationSuiteCode,
    EvaluationSuiteId,
    EvaluationTargetCode,
    EvaluationTargetKind,
    EvaluationTargetRef,
    EvaluationVerdict,
    InvariantAssertionSpec,
    NormalizedScore,
    RationalScoreDelta,
    ScoreStatus,
)
from tests.support.evaluation_runner_fakes import RecordingClock
from tests.support.evaluation_runtime_adapters import (
    TechnicalFactScorer,
    TechnicalOwnerInvariantEvaluator,
    TechnicalRuntimeFixtureFactory,
    TechnicalRuntimeInputFactory,
    TechnicalRuntimeTargetExecutor,
)

TARGET_CODES = (
    "ag01",
    "ag02",
    "ag03",
    "ag04",
    "authority",
    "security",
    "recovery",
    "observability",
)


def _case(
    code: str,
    *,
    repeat_count: int = 1,
    profile: str = "technical-baseline",
) -> EvaluationCase:
    return EvaluationCase(
        EvaluationCaseId(f"case-{code}"),
        EVALUATION_SCHEMA_V1_0,
        EvaluationCaseCode(f"case-{code}"),
        f"Technical runtime {code}",
        EvaluationTargetRef(
            EvaluationTargetKind.COMPONENT,
            EvaluationTargetCode(code),
        ),
        EvaluationInputFactoryRef(profile),
        (EvaluationAssertionRef(f"assert-{code}"),),
        fixture_ref=EvaluationFixtureRef("runtime-fixture"),
        repeat_count=repeat_count,
        timeout_seconds=30,
    )


def _suite() -> EvaluationSuite:
    cases = tuple(
        _case(code, repeat_count=2 if code == "ag01" else 1)
        for code in TARGET_CODES
    )
    return EvaluationSuite(
        EvaluationSuiteId("suite-runtime-technical"),
        EVALUATION_SCHEMA_V1_0,
        EvaluationSuiteCode("runtime-technical"),
        "Technical runtime owner integration",
        cases,
        EvaluationInfrastructureErrorPolicy.CONTINUE,
    )


def _catalog(*codes: str) -> EvaluationAssertionCatalog:
    return EvaluationAssertionCatalog(
        tuple(
            InvariantAssertionSpec(
                EvaluationAssertionRef(f"assert-{code}"),
                EVALUATION_SCHEMA_V1_0,
                EvaluationObservationRef(f"runtime.{code}.primary"),
                EvaluationInvariantCode("owner.closed-fact-true"),
            )
            for code in codes
        )
    )


def _configuration(
    case: EvaluationCase,
    catalog: EvaluationAssertionCatalog,
) -> EvaluationCaseRunConfiguration:
    code = case.target.code.value
    criterion = EvaluationScoringCriterionSpec(
        EVALUATION_SCHEMA_V1_0,
        EvaluationCriterionRef(f"criterion-{code}"),
        EvaluationScorerRef("technical-fact-ratio"),
        (EvaluationObservationRef(f"runtime.{code}.checks"),),
        NormalizedScore.whole(),
    )
    rubric = EvaluationRubric(
        EVALUATION_SCHEMA_V1_0,
        EvaluationRubricRef(f"rubric-{code}"),
        (criterion,),
    )
    return EvaluationCaseRunConfiguration(
        case.case_id,
        catalog,
        EvaluationCaseScoringPlan((criterion,), (rubric,)),
    )


def _execute(suite: EvaluationSuite):
    inputs = TechnicalRuntimeInputFactory()
    fixtures = TechnicalRuntimeFixtureFactory()
    targets = TechnicalRuntimeTargetExecutor()
    runner = EvaluationRunner(
        input_factory=inputs,
        fixture_factory=fixtures,
        target_executor=targets,
        clock=RecordingClock(),
        invariant_evaluator=TechnicalOwnerInvariantEvaluator(),
        scorer=TechnicalFactScorer(),
    )
    catalog = _catalog(*(case.target.code.value for case in suite.cases))
    result = runner.run_suite(
        suite,
        tuple(_configuration(case, catalog) for case in suite.cases),
    )
    return result, inputs, fixtures, targets


def test_full_b_to_f_path_reuses_real_runtime_owners_and_renders_reports() -> None:
    suite = _suite()
    result, _, _, targets = _execute(suite)

    assert result.verdict is EvaluationVerdict.PASS
    assert tuple(item.case_id for item in result.case_results) == tuple(
        case.case_id for case in suite.cases
    )
    assert all(
        repetition.assertion_results[0].verdict is EvaluationVerdict.PASS
        and repetition.score_results[0].status is ScoreStatus.SCORED
        and repetition.rubric_results[0].status is ScoreStatus.SCORED
        for case in result.case_results
        for repetition in case.repetition_results
    )
    assert tuple(code for code, _ in targets.projected_facts) == (
        "ag01",
        "ag01",
        "ag02",
        "ag03",
        "ag04",
        "authority",
        "security",
        "recovery",
        "observability",
    )

    report = EvaluationReportProjector().project(suite, result)
    machine = EvaluationJsonReportRenderer().render(report)
    human = EvaluationMarkdownReportRenderer().render(report)
    assert json.loads(machine)["verdict"] == "PASS"
    assert b"Technical runtime" not in machine
    assert b"observation" not in machine.lower()
    assert b"# Evaluation suite" in human
    assert b"observation" not in human.lower()


def test_real_owner_fact_projections_cover_all_required_families() -> None:
    _, _, _, targets = _execute(_suite())
    latest = {code: facts for code, facts in targets.projected_facts}

    assert latest["ag01"].status_codes == ("WF-6",)
    assert latest["ag01"].counts == (4,)
    assert latest["ag02"].status_codes == ("FULL", "COMPLETE")
    assert latest["ag02"].counts == (3, 3)
    assert latest["ag03"].counts == (1,)
    assert latest["ag04"].counts == (1, 1)
    assert latest["authority"].status_codes == ("APPROVED",)
    assert latest["authority"].counts == (1, 1)
    assert latest["security"].counts == (1, 0)
    assert latest["recovery"].status_codes == (
        "ELIGIBLE",
        "RECONCILE_FIRST",
        "BLOCKED",
        "BLOCKED",
    )
    assert latest["observability"].technical_checks == (True, True, True)


def test_multi_repetition_uses_fresh_state_exact_calls_and_no_retry() -> None:
    suite = _suite()
    result, inputs, fixtures, targets = _execute(suite)

    assert len(inputs.calls) == len(fixtures.create_calls) == 9
    assert len(fixtures.cleanup_calls) == len(targets.calls) == 9
    assert len({id(item) for item in inputs.inputs}) == 9
    assert len({id(item) for item in fixtures.fixtures}) == 9
    assert all(item.cleaned for item in fixtures.fixtures)
    assert all(len(item.invocation_codes) == 1 for item in fixtures.fixtures)
    ag01 = result.case_results[0]
    assert len(ag01.repetition_results) == 2
    assert (
        ag01.repetition_results[0].assertion_results
        == ag01.repetition_results[1].assertion_results
    )
    assert (
        ag01.repetition_results[0].score_results
        == ag01.repetition_results[1].score_results
    )
    assert (
        ag01.repetition_results[0].execution_result.observation_refs
        == ag01.repetition_results[1].execution_result.observation_refs
    )
    assert [code for code, _ in targets.calls].count("ag01") == 2


def test_security_recovery_and_observability_preserve_runtime_authority() -> None:
    result, _, _, targets = _execute(_suite())
    latest = {code: facts for code, facts in targets.projected_facts}

    assert result.verdict is EvaluationVerdict.PASS
    assert latest["security"].technical_checks == (True, True, True, True)
    assert latest["security"].counts[1] == 0
    assert latest["recovery"].counts == (1,)
    assert latest["observability"].primary_fact is True


def test_controlled_comparison_is_descriptive_with_exact_technical_delta() -> None:
    baseline_suite = EvaluationSuite(
        EvaluationSuiteId("suite-runtime-comparison"),
        EVALUATION_SCHEMA_V1_0,
        EvaluationSuiteCode("runtime-comparison"),
        "Technical comparison baseline",
        (_case("comparison", profile="technical-baseline"),),
    )
    candidate_suite = replace(
        baseline_suite,
        title="Technical comparison candidate",
        cases=(
            replace(
                baseline_suite.cases[0],
                input_factory_ref=EvaluationInputFactoryRef("technical-candidate"),
            ),
        ),
    )
    baseline_result, *_ = _execute(baseline_suite)
    candidate_result, *_ = _execute(candidate_suite)
    projector = EvaluationReportProjector()
    baseline = projector.project(baseline_suite, baseline_result)
    candidate = projector.project(candidate_suite, candidate_result)
    comparison = EvaluationReportComparator().compare(baseline, candidate)

    score = comparison.cases[0].repetitions[0].scores[0]
    assert baseline.verdict is candidate.verdict is EvaluationVerdict.PASS
    assert score.delta == RationalScoreDelta(1, 3)
    assert not hasattr(comparison, "winner")
    assert not hasattr(comparison, "accepted")


def test_runtime_values_and_hostile_markers_never_reach_reports() -> None:
    suite = _suite()
    result, *_ = _execute(suite)
    report = EvaluationReportProjector().project(suite, result)
    rendered = (
        repr(report).encode(),
        EvaluationJsonReportRenderer().render(report),
        EvaluationMarkdownReportRenderer().render(report),
    )
    forbidden = (
        b"Exact secure target",
        b"Bounded generated lesson",
        b"gateDecision",
        b"APPROVED\"}",
        b"lesson_plan",
    )
    assert all(marker not in value for marker in forbidden for value in rendered)
