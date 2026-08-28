from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from evaluation_harness import (
    EVALUATION_SCHEMA_V1_0,
    AssertionReasonCode,
    EvaluationAssertionCatalog,
    EvaluationAssertionRef,
    EvaluationCase,
    EvaluationCaseCode,
    EvaluationCaseId,
    EvaluationCaseRunConfiguration,
    EvaluationCaseScoringPlan,
    EvaluationCriterionRef,
    EvaluationDeadline,
    EvaluationFixtureRef,
    EvaluationInfrastructureErrorPolicy,
    EvaluationInputFactoryRef,
    EvaluationInvariantCode,
    EvaluationObservationRef,
    EvaluationObservationSnapshot,
    EvaluationObservationSnapshotEntry,
    EvaluationRepetitionContext,
    EvaluationRubric,
    EvaluationRubricRef,
    EvaluationRunner,
    EvaluationRunnerReasonCode,
    EvaluationScorerRef,
    EvaluationScoringCriterionSpec,
    EvaluationSuite,
    EvaluationSuiteCode,
    EvaluationSuiteId,
    EvaluationTargetCode,
    EvaluationTargetKind,
    EvaluationTargetRef,
    EvaluationVerdict,
    ExactAssertionSpec,
    InvariantAssertionSpec,
    InvariantCheckResult,
    NormalizedScore,
    ObservationScalar,
    ObservationScalarKind,
    RepetitionEvaluationResult,
    ScoreReasonCode,
    ScorerOutcome,
    ScoreStatus,
    TargetExecutionOutcome,
    TargetExecutionStatus,
)
from tests.support.evaluation_assertion_fakes import RecordingInvariantEvaluator
from tests.support.evaluation_runner_fakes import (
    FreshFixtureHandle,
    FreshPreparedInput,
    RecordingClock,
    RecordingFixtureFactory,
    RecordingInputFactory,
    RecordingTargetExecutor,
)
from tests.support.evaluation_scoring_fakes import RecordingScorer

SUBJECT_REF = EvaluationObservationRef("observation-subject")
EXPECTED_REF = EvaluationObservationRef("observation-expected")
ASSERTION_REF = EvaluationAssertionRef("assertion-exact")


def _scalar(value: str) -> ObservationScalar:
    return ObservationScalar(ObservationScalarKind.STRING, value)


def _snapshot(subject: str = "same", expected: str = "same") -> EvaluationObservationSnapshot:
    return EvaluationObservationSnapshot(
        (
            EvaluationObservationSnapshotEntry(SUBJECT_REF, _scalar(subject)),
            EvaluationObservationSnapshotEntry(EXPECTED_REF, _scalar(expected)),
        )
    )


def _completed(
    subject: str = "same",
    expected: str = "same",
) -> TargetExecutionOutcome:
    return TargetExecutionOutcome(
        TargetExecutionStatus.COMPLETED,
        _snapshot(subject, expected),
        duration_milliseconds=5,
    )


def _case(
    value: str = "case-01",
    *,
    repeat_count: int = 1,
    timeout_seconds: int | None = None,
    fixture: bool = True,
    assertion_ref: EvaluationAssertionRef = ASSERTION_REF,
) -> EvaluationCase:
    return EvaluationCase(
        EvaluationCaseId(value),
        EVALUATION_SCHEMA_V1_0,
        EvaluationCaseCode(value),
        f"Synthetic {value}",
        EvaluationTargetRef(
            EvaluationTargetKind.COMPONENT,
            EvaluationTargetCode(f"target-{value}"),
        ),
        EvaluationInputFactoryRef("input-factory"),
        (assertion_ref,),
        fixture_ref=EvaluationFixtureRef("fixture") if fixture else None,
        repeat_count=repeat_count,
        timeout_seconds=timeout_seconds,
    )


def _exact_catalog() -> EvaluationAssertionCatalog:
    return EvaluationAssertionCatalog(
        (
            ExactAssertionSpec(
                ASSERTION_REF,
                EVALUATION_SCHEMA_V1_0,
                SUBJECT_REF,
                EXPECTED_REF,
            ),
        )
    )


def _configuration(
    case: EvaluationCase,
    *,
    catalog: EvaluationAssertionCatalog | None = None,
    scoring_plan: EvaluationCaseScoringPlan | None = None,
    explicit_skip: bool = False,
) -> EvaluationCaseRunConfiguration:
    return EvaluationCaseRunConfiguration(
        case.case_id,
        catalog or _exact_catalog(),
        scoring_plan or EvaluationCaseScoringPlan(),
        explicit_skip,
    )


def _scoring_plan() -> EvaluationCaseScoringPlan:
    criterion = EvaluationScoringCriterionSpec(
        EVALUATION_SCHEMA_V1_0,
        EvaluationCriterionRef("criterion-quality"),
        EvaluationScorerRef("scorer-quality"),
        (SUBJECT_REF,),
        NormalizedScore.whole(),
    )
    rubric = EvaluationRubric(
        EVALUATION_SCHEMA_V1_0,
        EvaluationRubricRef("rubric-quality"),
        (criterion,),
    )
    return EvaluationCaseScoringPlan((criterion,), (rubric,))


def _runner(
    target: RecordingTargetExecutor,
    *,
    clock: RecordingClock | None = None,
    inputs: RecordingInputFactory | None = None,
    fixtures: RecordingFixtureFactory | None = None,
    invariant: RecordingInvariantEvaluator | None = None,
    scorer: RecordingScorer | None = None,
) -> EvaluationRunner:
    return EvaluationRunner(
        input_factory=inputs or RecordingInputFactory(),
        target_executor=target,
        clock=clock or RecordingClock(),
        fixture_factory=fixtures or RecordingFixtureFactory(),
        invariant_evaluator=invariant,
        scorer=scorer,
    )


def _suite(
    cases: tuple[EvaluationCase, ...],
    policy: EvaluationInfrastructureErrorPolicy,
) -> EvaluationSuite:
    return EvaluationSuite(
        EvaluationSuiteId("suite-runner"),
        EVALUATION_SCHEMA_V1_0,
        EvaluationSuiteCode("suite-runner"),
        "Synthetic runner suite",
        cases,
        infrastructure_error_policy=policy,
    )


def test_runner_contracts_are_bounded_immutable_and_timeout_expires_at_deadline() -> None:
    context = EvaluationRepetitionContext(
        EVALUATION_SCHEMA_V1_0,
        EvaluationCaseId("case-contract"),
        1,
    )
    deadline = EvaluationDeadline(10, 15)
    assert not deadline.is_expired_at(14)
    assert deadline.is_expired_at(15)
    with pytest.raises(FrozenInstanceError):
        context.repetition_index = 2  # type: ignore[misc]
    duplicate = EvaluationObservationSnapshotEntry(SUBJECT_REF, _scalar("x"))
    with pytest.raises(ValueError, match="unique"):
        EvaluationObservationSnapshot((duplicate, duplicate))
    with pytest.raises(ValueError, match="closed reason"):
        TargetExecutionOutcome(TargetExecutionStatus.ERROR)


def test_one_case_one_repetition_passes_with_real_assertion_evaluator() -> None:
    case = _case()
    result = _runner(RecordingTargetExecutor(_completed())).run_case(
        case, _configuration(case)
    )
    assert result.verdict is EvaluationVerdict.PASS
    assert len(result.repetition_results) == 1
    repetition = result.repetition_results[0]
    assert repetition.verdict is EvaluationVerdict.PASS
    assert repetition.assertion_results[0].verdict is EvaluationVerdict.PASS
    assert result.execution_results == (repetition.execution_result,)
    assert result.assertion_results == ()


def test_n_repetitions_use_fresh_fixture_and_input_and_cleanup_each_time() -> None:
    case = _case(repeat_count=3)
    inputs = RecordingInputFactory()
    fixtures = RecordingFixtureFactory()

    def verify_fresh(
        _target: object,
        prepared: object,
        fixture: object,
        _context: object,
        _deadline: object,
    ) -> TargetExecutionOutcome:
        assert isinstance(prepared, FreshPreparedInput)
        assert isinstance(fixture, FreshFixtureHandle)
        assert prepared.state == []
        assert fixture.state == []
        prepared.state.append("mutated")
        fixture.state.append("mutated")
        return _completed()

    target = RecordingTargetExecutor(verify_fresh, verify_fresh, verify_fresh)  # type: ignore[arg-type]
    result = _runner(target, inputs=inputs, fixtures=fixtures).run_case(
        case, _configuration(case)
    )
    assert result.verdict is EvaluationVerdict.PASS
    assert [item.repetition_index for item in result.repetition_results] == [1, 2, 3]
    assert len(inputs.calls) == len(inputs.inputs) == 3
    assert len({id(item) for item in inputs.inputs}) == 3
    assert len(fixtures.create_calls) == len(fixtures.handles) == 3
    assert len({id(item) for item in fixtures.handles}) == 3
    assert len(fixtures.cleanup_calls) == 3
    assert len(target.calls) == 3


def test_target_exception_is_contained_without_silent_retry() -> None:
    case = _case()
    failure_text = "synthetic target secret path failure"
    target = RecordingTargetExecutor(RuntimeError(failure_text))
    result = _runner(target).run_case(case, _configuration(case))
    assert result.verdict is EvaluationVerdict.ERROR
    assert result.repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.TARGET_EXECUTOR_ERROR
    )
    assert len(target.calls) == 1
    assert failure_text not in repr(result)


def test_next_repetition_is_declared_execution_not_retry() -> None:
    case = _case(repeat_count=2)
    target = RecordingTargetExecutor(RuntimeError("first"), _completed())
    result = _runner(target).run_case(case, _configuration(case))
    assert result.verdict is EvaluationVerdict.ERROR
    assert [item.verdict for item in result.repetition_results] == [
        EvaluationVerdict.ERROR,
        EvaluationVerdict.PASS,
    ]
    assert len(target.calls) == 2


@pytest.mark.parametrize(
    ("inputs", "reason"),
    [
        (
            RecordingInputFactory(missing=True),
            EvaluationRunnerReasonCode.INPUT_FACTORY_NOT_FOUND,
        ),
        (
            RecordingInputFactory(error=RuntimeError("synthetic input failure")),
            EvaluationRunnerReasonCode.INPUT_FACTORY_ERROR,
        ),
    ],
)
def test_input_factory_failures_are_contained_and_fixture_is_cleaned(
    inputs: RecordingInputFactory,
    reason: EvaluationRunnerReasonCode,
) -> None:
    case = _case()
    fixtures = RecordingFixtureFactory()
    target = RecordingTargetExecutor()
    result = _runner(target, inputs=inputs, fixtures=fixtures).run_case(
        case, _configuration(case)
    )
    assert result.repetition_results[0].reason_code is reason
    assert len(fixtures.create_calls) == len(fixtures.cleanup_calls) == 1
    assert target.calls == []


@pytest.mark.parametrize(
    ("fixtures", "reason"),
    [
        (
            RecordingFixtureFactory(missing=True),
            EvaluationRunnerReasonCode.FIXTURE_NOT_FOUND,
        ),
        (
            RecordingFixtureFactory(create_error=RuntimeError("setup")),
            EvaluationRunnerReasonCode.FIXTURE_SETUP_ERROR,
        ),
    ],
)
def test_fixture_setup_failures_are_contained_without_cleanup(
    fixtures: RecordingFixtureFactory,
    reason: EvaluationRunnerReasonCode,
) -> None:
    case = _case()
    inputs = RecordingInputFactory()
    result = _runner(
        RecordingTargetExecutor(), inputs=inputs, fixtures=fixtures
    ).run_case(case, _configuration(case))
    assert result.repetition_results[0].reason_code is reason
    assert fixtures.cleanup_calls == []
    assert inputs.calls == []


def test_cleanup_failure_overrides_pass_and_target_failure_without_retry() -> None:
    case = _case()
    fixtures = RecordingFixtureFactory(cleanup_error=RuntimeError("cleanup private"))
    target = RecordingTargetExecutor(_completed())
    passed_target = _runner(target, fixtures=fixtures).run_case(
        case, _configuration(case)
    )
    assert passed_target.verdict is EvaluationVerdict.ERROR
    assert passed_target.repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.FIXTURE_CLEANUP_ERROR
    )
    assert len(target.calls) == len(fixtures.cleanup_calls) == 1

    failing_fixtures = RecordingFixtureFactory(
        cleanup_error=RuntimeError("cleanup private")
    )
    failing_target = RecordingTargetExecutor(RuntimeError("target private"))
    failed = _runner(failing_target, fixtures=failing_fixtures).run_case(
        case, _configuration(case)
    )
    assert failed.repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.FIXTURE_CLEANUP_ERROR
    )
    assert len(failing_target.calls) == len(failing_fixtures.cleanup_calls) == 1


@pytest.mark.parametrize(
    ("finished_at", "expected"),
    [
        (14, EvaluationVerdict.PASS),
        (15, EvaluationVerdict.ERROR),
        (16, EvaluationVerdict.ERROR),
    ],
)
def test_timeout_is_cooperative_deterministic_and_expired_at_exact_deadline(
    finished_at: int,
    expected: EvaluationVerdict,
) -> None:
    case = _case(timeout_seconds=5)
    clock = RecordingClock(10)

    def finish_at(
        _target: object,
        _prepared: object,
        _fixture: object,
        _context: object,
        _deadline: object,
    ) -> TargetExecutionOutcome:
        clock.current_second = finished_at
        return _completed()

    target = RecordingTargetExecutor(finish_at)  # type: ignore[arg-type]
    result = _runner(target, clock=clock).run_case(case, _configuration(case))
    assert result.verdict is expected
    if expected is EvaluationVerdict.ERROR:
        assert result.repetition_results[0].reason_code is (
            EvaluationRunnerReasonCode.EVALUATION_TIMEOUT
        )
    assert len(target.calls) == 1


def test_cooperative_target_timeout_is_not_retried() -> None:
    case = _case(timeout_seconds=5)
    outcome = TargetExecutionOutcome(
        TargetExecutionStatus.TIMEOUT,
        reason_code=EvaluationRunnerReasonCode.EVALUATION_TIMEOUT,
    )
    target = RecordingTargetExecutor(outcome)
    result = _runner(target).run_case(case, _configuration(case))
    assert result.verdict is EvaluationVerdict.ERROR
    assert len(target.calls) == 1


def test_target_reported_error_and_unknown_executor_are_distinct() -> None:
    case = _case()
    reported = TargetExecutionOutcome(
        TargetExecutionStatus.ERROR,
        reason_code=EvaluationRunnerReasonCode.TARGET_EXECUTION_ERROR,
    )
    first = _runner(RecordingTargetExecutor(reported)).run_case(
        case, _configuration(case)
    )
    assert first.repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.TARGET_EXECUTION_ERROR
    )
    second = _runner(RecordingTargetExecutor(missing=True)).run_case(
        case, _configuration(case)
    )
    assert second.repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.TARGET_EXECUTOR_NOT_FOUND
    )


def test_assertion_fail_error_and_inconclusive_are_per_repetition() -> None:
    failed_case = _case()
    failed = _runner(RecordingTargetExecutor(_completed("left", "right"))).run_case(
        failed_case, _configuration(failed_case)
    )
    assert failed.verdict is EvaluationVerdict.FAIL
    assert failed.repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.ASSERTION_FAILED
    )

    errored = _runner(
        RecordingTargetExecutor(
            TargetExecutionOutcome(
                TargetExecutionStatus.COMPLETED,
                EvaluationObservationSnapshot(
                    (EvaluationObservationSnapshotEntry(SUBJECT_REF, _scalar("x")),)
                ),
            )
        )
    ).run_case(failed_case, _configuration(failed_case))
    assert errored.verdict is EvaluationVerdict.ERROR
    assert errored.repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.ASSERTION_EVALUATION_ERROR
    )

    invariant_ref = EvaluationAssertionRef("assertion-invariant")
    invariant_code = EvaluationInvariantCode("invariant-synthetic")
    inconclusive_case = _case(assertion_ref=invariant_ref)
    catalog = EvaluationAssertionCatalog(
        (
            InvariantAssertionSpec(
                invariant_ref,
                EVALUATION_SCHEMA_V1_0,
                SUBJECT_REF,
                invariant_code,
            ),
        )
    )
    checker = RecordingInvariantEvaluator(
        (
            invariant_code,
            InvariantCheckResult(EvaluationVerdict.INCONCLUSIVE),
        )
    )
    inconclusive = _runner(
        RecordingTargetExecutor(_completed()), invariant=checker
    ).run_case(inconclusive_case, _configuration(inconclusive_case, catalog=catalog))
    assert inconclusive.verdict is EvaluationVerdict.INCONCLUSIVE
    assert inconclusive.repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.ASSERTION_INCONCLUSIVE
    )


def test_low_score_keeps_pass_and_high_score_cannot_hide_fail() -> None:
    plan = _scoring_plan()
    scorer_ref = plan.criteria[0].scorer_ref
    pass_case = _case("case-low")
    low = _runner(
        RecordingTargetExecutor(_completed()),
        scorer=RecordingScorer(
            (scorer_ref, ScorerOutcome(ScoreStatus.SCORED, NormalizedScore.zero()))
        ),
    ).run_case(pass_case, _configuration(pass_case, scoring_plan=plan))
    assert low.verdict is EvaluationVerdict.PASS
    assert low.repetition_results[0].rubric_results[0].score == NormalizedScore.zero()

    fail_case = _case("case-high")
    high = _runner(
        RecordingTargetExecutor(_completed("left", "right")),
        scorer=RecordingScorer(
            (scorer_ref, ScorerOutcome(ScoreStatus.SCORED, NormalizedScore.whole()))
        ),
    ).run_case(fail_case, _configuration(fail_case, scoring_plan=plan))
    assert high.verdict is EvaluationVerdict.FAIL
    assert high.repetition_results[0].rubric_results[0].score == NormalizedScore.whole()


def test_scorer_error_is_infrastructure_but_inconclusive_score_does_not_change_pass() -> None:
    plan = _scoring_plan()
    scorer_ref = plan.criteria[0].scorer_ref
    case = _case()
    errored = _runner(
        RecordingTargetExecutor(_completed()),
        scorer=RecordingScorer(
            (scorer_ref, ScorerOutcome(ScoreStatus.ERROR))
        ),
    ).run_case(case, _configuration(case, scoring_plan=plan))
    repetition = errored.repetition_results[0]
    assert repetition.verdict is EvaluationVerdict.ERROR
    assert repetition.infrastructure_error
    assert repetition.score_results[0].reason_code is (
        ScoreReasonCode.SCORER_EVALUATION_ERROR
    )
    assert repetition.rubric_results[0].status is ScoreStatus.ERROR

    inconclusive = _runner(
        RecordingTargetExecutor(_completed()),
        scorer=RecordingScorer(
            (scorer_ref, ScorerOutcome(ScoreStatus.INCONCLUSIVE))
        ),
    ).run_case(case, _configuration(case, scoring_plan=plan))
    assert inconclusive.verdict is EvaluationVerdict.PASS
    assert inconclusive.repetition_results[0].score_results[0].status is (
        ScoreStatus.INCONCLUSIVE
    )
    assert inconclusive.repetition_results[0].rubric_results[0].status is (
        ScoreStatus.INCONCLUSIVE
    )


def test_explicit_skip_calls_no_fixture_input_target_assertion_or_scorer() -> None:
    case = _case()
    inputs = RecordingInputFactory()
    fixtures = RecordingFixtureFactory()
    target = RecordingTargetExecutor()
    scorer = RecordingScorer()
    result = _runner(
        target,
        inputs=inputs,
        fixtures=fixtures,
        scorer=scorer,
    ).run_case(case, _configuration(case, explicit_skip=True))
    assert result.verdict is EvaluationVerdict.SKIPPED
    assert result.repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.CASE_EXPLICITLY_SKIPPED
    )
    assert inputs.calls == fixtures.create_calls == target.calls == scorer.calls == []


def test_suite_continue_runs_cases_after_infrastructure_error_in_order() -> None:
    first = _case("case-first")
    second = _case("case-second")
    target = RecordingTargetExecutor(RuntimeError("first fails"), _completed())
    result = _runner(target).run_suite(
        _suite((first, second), EvaluationInfrastructureErrorPolicy.CONTINUE),
        (_configuration(first), _configuration(second)),
    )
    assert result.verdict is EvaluationVerdict.ERROR
    assert [item.case_id for item in result.case_results] == [
        first.case_id,
        second.case_id,
    ]
    assert [item.verdict for item in result.case_results] == [
        EvaluationVerdict.ERROR,
        EvaluationVerdict.PASS,
    ]
    assert len(target.calls) == 2


def test_suite_abort_skips_remaining_cases_with_zero_calls() -> None:
    first = _case("case-first")
    second = _case("case-second")
    target = RecordingTargetExecutor(RuntimeError("first fails"), _completed())
    result = _runner(target).run_suite(
        _suite((first, second), EvaluationInfrastructureErrorPolicy.ABORT_SUITE),
        (_configuration(first), _configuration(second)),
    )
    assert result.verdict is EvaluationVerdict.ERROR
    assert result.infrastructure_error
    assert result.case_results[1].verdict is EvaluationVerdict.SKIPPED
    assert result.case_results[1].repetition_results[0].reason_code is (
        EvaluationRunnerReasonCode.SUITE_ABORTED
    )
    assert len(target.calls) == 1


def test_hard_fail_does_not_trigger_abort_suite_policy() -> None:
    first = _case("case-first")
    second = _case("case-second")
    target = RecordingTargetExecutor(_completed("left", "right"), _completed())
    result = _runner(target).run_suite(
        _suite((first, second), EvaluationInfrastructureErrorPolicy.ABORT_SUITE),
        (_configuration(first), _configuration(second)),
    )
    assert result.verdict is EvaluationVerdict.FAIL
    assert not result.infrastructure_error
    assert result.case_results[1].verdict is EvaluationVerdict.PASS
    assert len(target.calls) == 2


def test_missing_case_configuration_is_infrastructure_error_and_can_abort() -> None:
    first = _case("case-first", repeat_count=2)
    second = _case("case-second")
    target = RecordingTargetExecutor(_completed())
    result = _runner(target).run_suite(
        _suite((first, second), EvaluationInfrastructureErrorPolicy.ABORT_SUITE),
        (_configuration(second),),
    )
    assert len(result.case_results[0].repetition_results) == 2
    assert all(
        item.reason_code is EvaluationRunnerReasonCode.CASE_CONFIGURATION_MISSING
        for item in result.case_results[0].repetition_results
    )
    assert result.case_results[1].verdict is EvaluationVerdict.SKIPPED
    assert target.calls == []


def test_missing_assertion_spec_and_missing_scorer_fail_before_lifecycle() -> None:
    case = _case(repeat_count=2)
    inputs = RecordingInputFactory()
    fixtures = RecordingFixtureFactory()
    target = RecordingTargetExecutor()
    empty = EvaluationAssertionCatalog(())
    assertion_error = _runner(
        target, inputs=inputs, fixtures=fixtures
    ).run_case(case, _configuration(case, catalog=empty))
    assert len(assertion_error.repetition_results) == 2
    assert all(
        item.reason_code is EvaluationRunnerReasonCode.ASSERTION_CONFIGURATION_ERROR
        for item in assertion_error.repetition_results
    )
    assert inputs.calls == fixtures.create_calls == target.calls == []

    score_error = _runner(
        target, inputs=inputs, fixtures=fixtures
    ).run_case(case, _configuration(case, scoring_plan=_scoring_plan()))
    assert all(
        item.reason_code is EvaluationRunnerReasonCode.SCORING_CONFIGURATION_ERROR
        for item in score_error.repetition_results
    )
    assert inputs.calls == fixtures.create_calls == target.calls == []


def test_repetition_result_cannot_mix_flat_and_per_repetition_models() -> None:
    case = _case()
    result = _runner(RecordingTargetExecutor(_completed())).run_case(
        case, _configuration(case)
    )
    repetition = result.repetition_results[0]
    assert isinstance(repetition, RepetitionEvaluationResult)
    with pytest.raises(ValueError, match="cannot mix"):
        type(result)(
            result.schema_version,
            result.case_id,
            result.verdict,
            result.execution_results,
            assertion_results=repetition.assertion_results,
            repetition_results=result.repetition_results,
        )


def test_runner_reason_taxonomy_is_closed() -> None:
    assert {code.value for code in EvaluationRunnerReasonCode} == {
        "CASE_CONFIGURATION_MISSING",
        "FIXTURE_NOT_FOUND",
        "FIXTURE_SETUP_ERROR",
        "FIXTURE_CLEANUP_ERROR",
        "INPUT_FACTORY_NOT_FOUND",
        "INPUT_FACTORY_ERROR",
        "TARGET_EXECUTOR_NOT_FOUND",
        "TARGET_EXECUTOR_ERROR",
        "TARGET_EXECUTION_ERROR",
        "EVALUATION_TIMEOUT",
        "CLOCK_ERROR",
        "ASSERTION_CONFIGURATION_ERROR",
        "ASSERTION_FAILED",
        "ASSERTION_INCONCLUSIVE",
        "ASSERTION_EVALUATION_ERROR",
        "SCORING_CONFIGURATION_ERROR",
        "SCORING_EVALUATION_ERROR",
        "SUITE_ABORTED",
        "CASE_EXPLICITLY_SKIPPED",
    }


def test_assertion_failure_reason_remains_closed_and_raw_free() -> None:
    case = _case()
    result = _runner(RecordingTargetExecutor(_completed("a", "b"))).run_case(
        case, _configuration(case)
    )
    assertion = result.repetition_results[0].assertion_results[0]
    assert assertion.reason_code is AssertionReasonCode.EXACT_MISMATCH
    assert "observation-subject" not in repr(assertion)
