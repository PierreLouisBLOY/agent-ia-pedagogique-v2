from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from evaluation_harness import (
    EVALUATION_SCHEMA_V1_0,
    AssertionKind,
    AssertionReasonCode,
    AssertionResult,
    CaseEvaluationResult,
    CaseExecutionResult,
    CaseExecutionStatus,
    EvaluationAssertionCatalog,
    EvaluationAssertionRef,
    EvaluationCase,
    EvaluationCaseCode,
    EvaluationCaseId,
    EvaluationCaseRunConfiguration,
    EvaluationInputFactoryRef,
    EvaluationObservationRef,
    EvaluationObservationSnapshot,
    EvaluationObservationSnapshotEntry,
    EvaluationReasonCode,
    EvaluationRepetitionContext,
    EvaluationRunner,
    EvaluationScorerRef,
    EvaluationSuite,
    EvaluationSuiteCode,
    EvaluationSuiteId,
    EvaluationTargetCode,
    EvaluationTargetKind,
    EvaluationTargetRef,
    EvaluationVerdict,
    ExactAssertionSpec,
    NormalizedScore,
    ObservationScalar,
    ObservationScalarKind,
    RepetitionEvaluationResult,
    RubricScoreResult,
    ScoreReasonCode,
    ScoreResult,
    ScoreStatus,
    SuiteEvaluationResult,
    TargetExecutionOutcome,
    TargetExecutionStatus,
)
from evaluation_harness.contracts.identity import (
    EvaluationCriterionRef,
    EvaluationRubricRef,
)
from evaluation_harness.reporting import (
    ArtifactDeliveryReasonCode,
    ArtifactDeliveryStatus,
    EvaluationArtifactDelivery,
    EvaluationArtifactFactory,
    EvaluationArtifactFormat,
    EvaluationArtifactName,
    EvaluationChangeKind,
    EvaluationJsonReportRenderer,
    EvaluationMarkdownReportRenderer,
    EvaluationReportComparator,
    EvaluationReportProjector,
    RationalScoreDelta,
    ReportSizeLimitError,
)
from tests.support.evaluation_reporting_fakes import RecordingArtifactSink
from tests.support.evaluation_runner_fakes import (
    RecordingClock,
    RecordingInputFactory,
    RecordingTargetExecutor,
)

DEFAULT_SCORE = NormalizedScore(1, 3)


def _case(value: str = "case_01") -> EvaluationCase:
    return EvaluationCase(
        EvaluationCaseId(value),
        EVALUATION_SCHEMA_V1_0,
        EvaluationCaseCode(value),
        "Synthetic case",
        EvaluationTargetRef(
            EvaluationTargetKind.COMPONENT, EvaluationTargetCode("target")
        ),
        EvaluationInputFactoryRef("input"),
        (EvaluationAssertionRef("assertion"),),
    )


def _suite(*cases: EvaluationCase) -> EvaluationSuite:
    selected = cases or (_case(),)
    return EvaluationSuite(
        EvaluationSuiteId("suite-01"),
        EVALUATION_SCHEMA_V1_0,
        EvaluationSuiteCode("suite_01"),
        "Synthetic suite",
        selected,
    )


def _assertion(verdict: EvaluationVerdict = EvaluationVerdict.PASS) -> AssertionResult:
    return AssertionResult(
        EVALUATION_SCHEMA_V1_0,
        EvaluationAssertionRef("assertion"),
        AssertionKind.EXACT,
        verdict,
        None if verdict is EvaluationVerdict.PASS else _assertion_reason(verdict),
    )


def _assertion_reason(verdict: EvaluationVerdict):
    return {
        EvaluationVerdict.FAIL: AssertionReasonCode.EXACT_MISMATCH,
        EvaluationVerdict.ERROR: AssertionReasonCode.OBSERVATION_SOURCE_ERROR,
        EvaluationVerdict.INCONCLUSIVE: AssertionReasonCode.OBSERVATION_NOT_FOUND,
    }[verdict]


def _score(value: NormalizedScore = DEFAULT_SCORE) -> ScoreResult:
    return ScoreResult(
        EVALUATION_SCHEMA_V1_0,
        EvaluationCriterionRef("criterion"),
        EvaluationScorerRef("scorer"),
        ScoreStatus.SCORED,
        value,
    )


def _rubric(value: NormalizedScore = DEFAULT_SCORE) -> RubricScoreResult:
    score = _score(value)
    return RubricScoreResult(
        EVALUATION_SCHEMA_V1_0,
        EvaluationRubricRef("rubric"),
        ScoreStatus.SCORED,
        (score,),
        value,
    )


def _result(
    suite: EvaluationSuite,
    *,
    score: NormalizedScore = DEFAULT_SCORE,
) -> SuiteEvaluationResult:
    cases = []
    for case in suite.cases:
        execution = CaseExecutionResult(
            EVALUATION_SCHEMA_V1_0,
            case.case_id,
            1,
            CaseExecutionStatus.COMPLETED,
            duration_milliseconds=7,
        )
        repetition = RepetitionEvaluationResult(
            EVALUATION_SCHEMA_V1_0,
            execution,
            EvaluationVerdict.PASS,
            assertion_results=(_assertion(),),
            score_results=(_score(score),),
            rubric_results=(_rubric(score),),
        )
        cases.append(
            CaseEvaluationResult(
                EVALUATION_SCHEMA_V1_0,
                case.case_id,
                EvaluationVerdict.PASS,
                (execution,),
                repetition_results=(repetition,),
            )
        )
    return SuiteEvaluationResult(
        EVALUATION_SCHEMA_V1_0,
        suite.suite_id,
        EvaluationVerdict.PASS,
        tuple(cases),
    )


def _report(score: NormalizedScore = DEFAULT_SCORE):
    suite = _suite()
    return EvaluationReportProjector().project(suite, _result(suite, score=score))


def test_projector_projects_minimized_suite_case_and_repetition() -> None:
    report = _report()
    repetition = report.cases[0].repetitions[0]
    assert report.suite_code.value == "suite_01"
    assert report.summary.case_count == 1
    assert report.summary.repetition_count == 1
    assert repetition.execution_status is CaseExecutionStatus.COMPLETED
    assert repetition.assertions[0].kind is AssertionKind.EXACT
    assert repetition.scores[0].score == NormalizedScore(1, 3)
    assert not hasattr(repetition, "observation_refs")


def test_projector_rejects_suite_and_case_order_mismatch() -> None:
    suite = _suite(_case("case-01"), _case("case-02"))
    result = _result(suite)
    reversed_result = SuiteEvaluationResult(
        result.schema_version,
        result.suite_id,
        result.verdict,
        tuple(reversed(result.case_results)),
    )
    with pytest.raises(ValueError, match="case order"):
        EvaluationReportProjector().project(suite, reversed_result)
    with pytest.raises(ValueError, match="suite definition"):
        EvaluationReportProjector().project(
            _suite(), replace(_result(_suite()), suite_id=EvaluationSuiteId("other"))
        )


def test_projector_rejects_case_repetition_count_mismatch() -> None:
    suite = _suite()
    case = replace(suite.cases[0], repeat_count=2)
    mismatched_suite = replace(suite, cases=(case,))
    with pytest.raises(ValueError, match="repetition counts"):
        EvaluationReportProjector().project(mismatched_suite, _result(suite))


def test_legacy_flat_results_remain_case_level_and_are_not_misattributed() -> None:
    suite = _suite()
    execution = CaseExecutionResult(
        EVALUATION_SCHEMA_V1_0,
        suite.cases[0].case_id,
        1,
        CaseExecutionStatus.COMPLETED,
    )
    case_result = CaseEvaluationResult(
        EVALUATION_SCHEMA_V1_0,
        suite.cases[0].case_id,
        EvaluationVerdict.PASS,
        (execution,),
        assertion_results=(_assertion(),),
        score_results=(_score(),),
        rubric_results=(_rubric(),),
    )
    result = SuiteEvaluationResult(
        EVALUATION_SCHEMA_V1_0,
        suite.suite_id,
        EvaluationVerdict.PASS,
        (case_result,),
    )
    report = EvaluationReportProjector().project(suite, result)
    assert report.cases[0].assertions
    assert report.cases[0].repetitions[0].verdict is None
    assert not report.cases[0].repetitions[0].assertions


def test_report_is_frozen_and_source_result_is_not_mutated() -> None:
    suite = _suite()
    result = _result(suite)
    before = repr(result)
    report = EvaluationReportProjector().project(suite, result)
    assert repr(result) == before
    with pytest.raises(FrozenInstanceError):
        report.verdict = EvaluationVerdict.FAIL  # type: ignore[misc]


def test_json_is_canonical_deterministic_utf8_and_exact() -> None:
    renderer = EvaluationJsonReportRenderer()
    first = renderer.render(_report())
    second = renderer.render(_report())
    assert first == second
    payload = json.loads(first)
    score = payload["cases"][0]["repetitions"][0]["scores"][0]["score"]
    assert score == {"denominator": 3, "numerator": 1}
    assert b"0.333" not in first
    assert b"observation" not in first


def test_renderers_refuse_output_over_configured_size_without_truncation() -> None:
    with pytest.raises(ReportSizeLimitError):
        EvaluationJsonReportRenderer(32).render(_report())
    with pytest.raises(ReportSizeLimitError):
        EvaluationMarkdownReportRenderer(32).render(_report())


def test_realistic_multi_case_report_stays_within_canonical_limit() -> None:
    suite = _suite(*(_case(f"case-{index:02d}") for index in range(32)))
    report = EvaluationReportProjector().project(suite, _result(suite))
    assert len(EvaluationJsonReportRenderer().render(report)) < 2_000_000
    assert len(EvaluationMarkdownReportRenderer().render(report)) < 2_000_000


def test_markdown_is_deterministic_minimized_and_escapes_codes() -> None:
    rendered = EvaluationMarkdownReportRenderer().render(_report())
    assert rendered == EvaluationMarkdownReportRenderer().render(_report())
    assert b"suite\\_01" in rendered
    assert b"case\\_01" in rendered
    assert b"observation" not in rendered
    assert b"<" not in rendered and b">" not in rendered


def test_identical_reports_compare_unchanged_without_acceptance_field() -> None:
    comparison = EvaluationReportComparator().compare(_report(), _report())
    assert comparison.change_kind is EvaluationChangeKind.UNCHANGED
    assert comparison.cases[0].change_kind is EvaluationChangeKind.UNCHANGED
    assert comparison.cases[0].repetitions[0].scores[0].delta == RationalScoreDelta(0, 1)
    assert not hasattr(comparison, "accepted")
    assert not hasattr(comparison, "release_gate")


@pytest.mark.parametrize(
    ("baseline", "candidate", "expected"),
    [
        (NormalizedScore(1, 3), NormalizedScore(2, 3), RationalScoreDelta(1, 3)),
        (NormalizedScore(2, 3), NormalizedScore(1, 3), RationalScoreDelta(-1, 3)),
        (NormalizedScore(1, 3), NormalizedScore(1, 3), RationalScoreDelta(0, 1)),
    ],
)
def test_score_delta_is_signed_exact_and_descriptive(baseline, candidate, expected) -> None:
    comparison = EvaluationReportComparator().compare(
        _report(baseline), _report(candidate)
    )
    assert comparison.cases[0].repetitions[0].scores[0].delta == expected


def test_non_scored_status_has_no_delta() -> None:
    baseline = _report()
    score = baseline.cases[0].repetitions[0].scores[0]
    inconclusive = replace(
        score,
        status=ScoreStatus.INCONCLUSIVE,
        score=None,
        reason_code=ScoreReasonCode.SCORER_INCONCLUSIVE,
    )
    repetition = baseline.cases[0].repetitions[0]
    candidate = replace(
        baseline,
        cases=(
            replace(
                baseline.cases[0],
                repetitions=(replace(repetition, scores=(inconclusive,)),),
            ),
        ),
    )
    comparison = EvaluationReportComparator().compare(baseline, candidate)
    assert comparison.cases[0].repetitions[0].scores[0].delta is None


def test_case_repetition_assertion_and_score_added_removed_changed_alignment() -> None:
    baseline = _report()
    case = baseline.cases[0]
    repetition = case.repetitions[0]
    added_assertion = replace(
        repetition.assertions[0], assertion_ref=EvaluationAssertionRef("assertion-2")
    )
    added_score = replace(
        repetition.scores[0], criterion_ref=EvaluationCriterionRef("criterion-2")
    )
    second_repetition = replace(
        repetition,
        repetition_index=2,
        assertions=(added_assertion,),
        scores=(added_score,),
    )
    candidate = replace(
        baseline,
        cases=(replace(case, repetitions=(repetition, second_repetition)),),
        summary=replace(baseline.summary, repetition_count=2),
    )
    comparison = EvaluationReportComparator().compare(baseline, candidate)
    assert comparison.change_kind is EvaluationChangeKind.CHANGED
    assert comparison.cases[0].repetitions[1].change_kind is EvaluationChangeKind.ADDED
    reverse = EvaluationReportComparator().compare(candidate, baseline)
    assert reverse.cases[0].repetitions[1].change_kind is EvaluationChangeKind.REMOVED


def test_case_added_and_removed_are_aligned_by_case_id() -> None:
    baseline = _report()
    added_case = replace(
        baseline.cases[0],
        case_id=EvaluationCaseId("case-02"),
        case_code=EvaluationCaseCode("case-02"),
    )
    candidate = replace(
        baseline,
        cases=(*baseline.cases, added_case),
        summary=replace(
            baseline.summary, case_count=2, repetition_count=2, pass_count=2
        ),
    )
    comparison = EvaluationReportComparator().compare(baseline, candidate)
    assert comparison.cases[1].change_kind is EvaluationChangeKind.ADDED
    reverse = EvaluationReportComparator().compare(candidate, baseline)
    assert reverse.cases[1].change_kind is EvaluationChangeKind.REMOVED


def test_assertions_are_added_removed_and_changed_by_ref() -> None:
    baseline = _report()
    repetition = baseline.cases[0].repetitions[0]
    changed = replace(
        repetition.assertions[0],
        verdict=EvaluationVerdict.FAIL,
        reason_code=AssertionReasonCode.EXACT_MISMATCH,
    )
    added = replace(
        repetition.assertions[0],
        assertion_ref=EvaluationAssertionRef("assertion-added"),
    )
    candidate_repetition = replace(repetition, assertions=(changed, added))
    candidate = replace(
        baseline,
        cases=(
            replace(
                baseline.cases[0], repetitions=(candidate_repetition,)
            ),
        ),
    )
    comparison = EvaluationReportComparator().compare(baseline, candidate)
    assertions = comparison.cases[0].repetitions[0].assertions
    assert assertions[0].change_kind is EvaluationChangeKind.CHANGED
    assert assertions[1].change_kind is EvaluationChangeKind.ADDED
    reverse = EvaluationReportComparator().compare(candidate, baseline)
    assert reverse.cases[0].repetitions[0].assertions[1].change_kind is EvaluationChangeKind.REMOVED


def test_verdict_transition_is_descriptive_only() -> None:
    baseline = _report()
    candidate_case = replace(
        baseline.cases[0],
        verdict=EvaluationVerdict.FAIL,
        reason_codes=(EvaluationReasonCode("ASSERTION_FAILED"),),
    )
    candidate = replace(
        baseline,
        verdict=EvaluationVerdict.FAIL,
        reason_codes=(EvaluationReasonCode("ASSERTION_FAILED"),),
        cases=(candidate_case,),
        summary=replace(
            baseline.summary, pass_count=0, fail_count=1
        ),
    )
    comparison = EvaluationReportComparator().compare(baseline, candidate)
    assert comparison.verdict_transition.from_verdict is EvaluationVerdict.PASS
    assert comparison.verdict_transition.to_verdict is EvaluationVerdict.FAIL


def test_rubric_comparison_preserves_status_criteria_and_exact_delta() -> None:
    comparison = EvaluationReportComparator().compare(
        _report(NormalizedScore(1, 4)), _report(NormalizedScore(3, 4))
    )
    rubric = comparison.cases[0].repetitions[0].rubrics[0]
    assert rubric.delta == RationalScoreDelta(1, 2)
    assert rubric.baseline_criterion_refs == (EvaluationCriterionRef("criterion"),)


@pytest.mark.parametrize(
    "invalid",
    ["../report", "folder/report", "folder\\report", "C:report", "https://x"],
)
def test_artifact_name_is_path_safe(invalid: str) -> None:
    with pytest.raises(ValueError, match="path-safe"):
        EvaluationArtifactName(invalid)


def test_artifact_formats_have_deterministic_media_types() -> None:
    factory = EvaluationArtifactFactory()
    json_artifact = factory.create(
        _report(), EvaluationArtifactName("suite-report.json"), EvaluationArtifactFormat.JSON
    )
    markdown_artifact = factory.create(
        _report(), EvaluationArtifactName("suite-report.md"), EvaluationArtifactFormat.MARKDOWN
    )
    assert json_artifact.media_type == "application/json; charset=utf-8"
    assert markdown_artifact.media_type == "text/markdown; charset=utf-8"


def test_sink_success_and_failure_are_single_attempt_and_isolated() -> None:
    artifact = EvaluationArtifactFactory().create(
        _report(), EvaluationArtifactName("report.json"), EvaluationArtifactFormat.JSON
    )
    delivery = EvaluationArtifactDelivery()
    success = RecordingArtifactSink()
    failure_text = "fake credential sk-" + "x" * 40 + " C:\\private\\file"
    failure = RecordingArtifactSink(RuntimeError(failure_text))
    assert delivery.deliver(artifact, success).status is ArtifactDeliveryStatus.DELIVERED
    failed = delivery.deliver(artifact, failure)
    assert failed.status is ArtifactDeliveryStatus.ERROR
    assert failed.reason_code is ArtifactDeliveryReasonCode.ARTIFACT_SINK_ERROR
    assert len(failure.calls) == 1
    assert failure_text not in repr(failed)


def test_privacy_adversarial_values_never_reach_report_renderers_or_artifact() -> None:
    fake_values = (
        "fake-secret-sk-" + "z" * 40,
        "C:\\private\\synthetic.txt",
        "<script>inject()</script>",
    )
    suite = _suite()
    subject_ref = EvaluationObservationRef("subject")
    expected_ref = EvaluationObservationRef("expected")
    hostile_value = " | ".join(fake_values)
    outcome = TargetExecutionOutcome(
        TargetExecutionStatus.COMPLETED,
        EvaluationObservationSnapshot(
            (
                EvaluationObservationSnapshotEntry(
                    subject_ref,
                    ObservationScalar(ObservationScalarKind.STRING, hostile_value),
                ),
                EvaluationObservationSnapshotEntry(
                    expected_ref,
                    ObservationScalar(ObservationScalarKind.STRING, hostile_value),
                ),
            )
        ),
    )
    runner = EvaluationRunner(
        input_factory=RecordingInputFactory(),
        target_executor=RecordingTargetExecutor(outcome),
        clock=RecordingClock(),
    )
    catalog = EvaluationAssertionCatalog(
        (
            ExactAssertionSpec(
                EvaluationAssertionRef("assertion"),
                EVALUATION_SCHEMA_V1_0,
                subject_ref,
                expected_ref,
            ),
        )
    )
    hostile_result = runner.run_suite(
        suite,
        (EvaluationCaseRunConfiguration(suite.cases[0].case_id, catalog),),
    )
    report = EvaluationReportProjector().project(suite, hostile_result)
    outputs = (
        repr(report).encode(),
        EvaluationJsonReportRenderer().render(report),
        EvaluationMarkdownReportRenderer().render(report),
        repr(EvaluationReportComparator().compare(report, report)).encode(),
        EvaluationArtifactFactory()
        .create(report, EvaluationArtifactName("safe.json"), EvaluationArtifactFormat.JSON)
        .content,
    )
    for value in fake_values:
        assert all(value.encode() not in output for output in outputs)


def test_report_has_no_implicit_environment_identity() -> None:
    rendered = EvaluationJsonReportRenderer().render(_report()).lower()
    for forbidden in (b"timestamp", b"hostname", b"username", b"uuid", b"path"):
        assert forbidden not in rendered


def test_context_is_not_reported_as_runtime_identity() -> None:
    context = EvaluationRepetitionContext(
        EVALUATION_SCHEMA_V1_0, EvaluationCaseId("case_01"), 1
    )
    assert context.case_id.value in EvaluationJsonReportRenderer().render(_report()).decode()
