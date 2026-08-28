from __future__ import annotations

from collections.abc import Iterable

from evaluation_harness.assertions.catalog import EvaluationAssertionCatalog
from evaluation_harness.assertions.evaluator import AssertionEvaluator
from evaluation_harness.assertions.ports import (
    InvariantEvaluatorPort,
    ObservationNotFoundError,
)
from evaluation_harness.contracts.assertion import AssertionResult, AssertionSpec
from evaluation_harness.contracts.case import EvaluationCase
from evaluation_harness.contracts.identity import (
    EvaluationObservationRef,
    EvaluationReasonCode,
)
from evaluation_harness.contracts.observation import EvaluationObservationValue
from evaluation_harness.contracts.result import (
    CaseEvaluationResult,
    CaseExecutionResult,
    CaseExecutionStatus,
    RepetitionEvaluationResult,
    SuiteEvaluationResult,
)
from evaluation_harness.contracts.runner import (
    EvaluationDeadline,
    EvaluationObservationSnapshot,
    EvaluationRepetitionContext,
    EvaluationRunnerReasonCode,
    TargetExecutionOutcome,
    TargetExecutionStatus,
)
from evaluation_harness.contracts.scoring import (
    RubricScoreResult,
    ScoreResult,
    ScoreStatus,
)
from evaluation_harness.contracts.suite import (
    EvaluationInfrastructureErrorPolicy,
    EvaluationSuite,
)
from evaluation_harness.contracts.verdict import EvaluationVerdict
from evaluation_harness.runner.configuration import (
    EvaluationCaseRunConfiguration,
    EvaluationCaseScoringPlan,
)
from evaluation_harness.runner.ports import (
    EvaluationClockPort,
    EvaluationFixtureFactoryPort,
    EvaluationFixtureHandle,
    EvaluationInputFactoryPort,
    EvaluationTargetExecutorPort,
    FixtureNotFoundError,
    InputFactoryNotFoundError,
    PreparedEvaluationInput,
    TargetExecutorNotFoundError,
)
from evaluation_harness.scoring.aggregation import RubricAggregator
from evaluation_harness.scoring.evaluator import ScoreEvaluator
from evaluation_harness.scoring.ports import EvaluationScorerPort


class _SnapshotObservationSource:
    def __init__(self, snapshot: EvaluationObservationSnapshot) -> None:
        self._snapshot = snapshot

    def resolve(
        self, observation_ref: EvaluationObservationRef
    ) -> EvaluationObservationValue:
        for entry in self._snapshot.entries:
            if entry.observation_ref == observation_ref:
                return entry.value
        raise ObservationNotFoundError


class EvaluationRunner:
    """Sequential offline orchestration over the existing C/D owners."""

    def __init__(
        self,
        *,
        input_factory: EvaluationInputFactoryPort,
        target_executor: EvaluationTargetExecutorPort,
        clock: EvaluationClockPort,
        fixture_factory: EvaluationFixtureFactoryPort | None = None,
        invariant_evaluator: InvariantEvaluatorPort | None = None,
        scorer: EvaluationScorerPort | None = None,
    ) -> None:
        self._input_factory = input_factory
        self._target_executor = target_executor
        self._clock = clock
        self._fixture_factory = fixture_factory
        self._invariant_evaluator = invariant_evaluator
        self._scorer = scorer

    def run_case(
        self,
        case: EvaluationCase,
        configuration: EvaluationCaseRunConfiguration,
    ) -> CaseEvaluationResult:
        if type(case) is not EvaluationCase:
            raise TypeError("case must be an EvaluationCase")
        if type(configuration) is not EvaluationCaseRunConfiguration:
            raise TypeError("configuration must be an EvaluationCaseRunConfiguration")
        if configuration.case_id != case.case_id:
            raise ValueError("case configuration ID must match the case")
        if configuration.explicit_skip:
            return _skipped_case(
                case,
                EvaluationRunnerReasonCode.CASE_EXPLICITLY_SKIPPED,
            )

        assertion_specs = _resolve_assertion_specs(
            case,
            configuration.assertion_catalog,
        )
        configuration_error = _configuration_error(
            case,
            assertion_specs,
            configuration.scoring_plan,
            self._scorer,
        )
        if configuration_error is not None:
            repetitions = tuple(
                _error_repetition(case, index, configuration_error)
                for index in range(1, case.repeat_count + 1)
            )
            return _case_result(case, repetitions)
        if assertion_specs is None:
            raise AssertionError("validated assertion specs must be available")

        repetitions = tuple(
            self._run_repetition(
                case,
                index,
                assertion_specs,
                configuration.scoring_plan,
            )
            for index in range(1, case.repeat_count + 1)
        )
        return _case_result(case, repetitions)

    def run_suite(
        self,
        suite: EvaluationSuite,
        configurations: tuple[EvaluationCaseRunConfiguration, ...],
    ) -> SuiteEvaluationResult:
        if type(suite) is not EvaluationSuite:
            raise TypeError("suite must be an EvaluationSuite")
        if type(configurations) is not tuple:
            raise TypeError("configurations must be a tuple")
        if any(
            type(configuration) is not EvaluationCaseRunConfiguration
            for configuration in configurations
        ):
            raise TypeError("configurations contain an unsupported value")
        configuration_ids = tuple(item.case_id for item in configurations)
        if len(configuration_ids) != len(set(configuration_ids)):
            raise ValueError("suite case configuration IDs must be unique")
        suite_case_ids = tuple(case.case_id for case in suite.cases)
        if any(case_id not in suite_case_ids for case_id in configuration_ids):
            raise ValueError("suite configuration contains an unknown case ID")

        case_results: list[CaseEvaluationResult] = []
        aborted = False
        for case in suite.cases:
            if aborted:
                case_results.append(
                    _skipped_case(case, EvaluationRunnerReasonCode.SUITE_ABORTED)
                )
                continue
            configuration = next(
                (item for item in configurations if item.case_id == case.case_id),
                None,
            )
            if configuration is None:
                repetitions = tuple(
                    _error_repetition(
                        case,
                        index,
                        EvaluationRunnerReasonCode.CASE_CONFIGURATION_MISSING,
                    )
                    for index in range(1, case.repeat_count + 1)
                )
                result = _case_result(case, repetitions)
            else:
                result = self.run_case(case, configuration)
            case_results.append(result)
            if (
                suite.infrastructure_error_policy
                is EvaluationInfrastructureErrorPolicy.ABORT_SUITE
                and _case_has_infrastructure_error(result)
            ):
                aborted = True

        results = tuple(case_results)
        verdict = _suite_verdict(results)
        infrastructure_error = any(
            _case_has_infrastructure_error(result) for result in results
        )
        reasons = _unique_reason_codes(
            code
            for result in results
            for code in result.reason_codes
        )
        return SuiteEvaluationResult(
            suite.schema_version,
            suite.suite_id,
            verdict,
            results,
            infrastructure_error=infrastructure_error,
            reason_codes=reasons,
        )

    def _run_repetition(
        self,
        case: EvaluationCase,
        repetition_index: int,
        assertion_specs: tuple[AssertionSpec, ...],
        scoring_plan: EvaluationCaseScoringPlan,
    ) -> RepetitionEvaluationResult:
        context = EvaluationRepetitionContext(
            case.schema_version,
            case.case_id,
            repetition_index,
        )
        fixture: EvaluationFixtureHandle | None = None
        if case.fixture_ref is not None:
            if self._fixture_factory is None:
                return _error_repetition(
                    case,
                    repetition_index,
                    EvaluationRunnerReasonCode.FIXTURE_NOT_FOUND,
                )
            try:
                fixture = self._fixture_factory.create(case.fixture_ref, context)
                if not isinstance(fixture, EvaluationFixtureHandle):
                    raise TypeError("fixture factory returned an invalid handle")
            except FixtureNotFoundError:
                return _error_repetition(
                    case,
                    repetition_index,
                    EvaluationRunnerReasonCode.FIXTURE_NOT_FOUND,
                )
            except Exception:
                return _error_repetition(
                    case,
                    repetition_index,
                    EvaluationRunnerReasonCode.FIXTURE_SETUP_ERROR,
                )

        failure_reason: EvaluationRunnerReasonCode | None = None
        outcome: TargetExecutionOutcome | None = None
        try:
            prepared_input = self._build_input(case, context)
            deadline = self._deadline(case)
            outcome = self._execute_target(
                case,
                prepared_input,
                fixture,
                context,
                deadline,
            )
            if (
                outcome.status is TargetExecutionStatus.COMPLETED
                and deadline.expires_at_second is not None
            ):
                try:
                    if deadline.is_expired_at(self._now_seconds()):
                        failure_reason = EvaluationRunnerReasonCode.EVALUATION_TIMEOUT
                except Exception:
                    failure_reason = EvaluationRunnerReasonCode.CLOCK_ERROR
        except _RunnerFailure as failure:
            failure_reason = failure.reason_code
        finally:
            if fixture is not None and self._fixture_factory is not None:
                try:
                    self._fixture_factory.cleanup(fixture, context)
                except Exception:
                    failure_reason = EvaluationRunnerReasonCode.FIXTURE_CLEANUP_ERROR

        if failure_reason is not None:
            return _error_repetition(
                case,
                repetition_index,
                failure_reason,
                outcome.duration_milliseconds if outcome is not None else None,
            )
        if outcome is None:
            raise AssertionError("target outcome must be available")
        if outcome.status is not TargetExecutionStatus.COMPLETED:
            if outcome.reason_code is None:
                raise AssertionError("failed target outcome must have a reason")
            return _error_repetition(
                case,
                repetition_index,
                outcome.reason_code,
                outcome.duration_milliseconds,
            )
        return self._evaluate_completed_repetition(
            case,
            repetition_index,
            outcome,
            assertion_specs,
            scoring_plan,
        )

    def _build_input(
        self,
        case: EvaluationCase,
        context: EvaluationRepetitionContext,
    ) -> PreparedEvaluationInput:
        try:
            prepared = self._input_factory.build(case.input_factory_ref, context)
            if not isinstance(prepared, PreparedEvaluationInput):
                raise TypeError("input factory returned an invalid input")
            return prepared
        except InputFactoryNotFoundError:
            raise _RunnerFailure(
                EvaluationRunnerReasonCode.INPUT_FACTORY_NOT_FOUND
            ) from None
        except Exception:
            raise _RunnerFailure(EvaluationRunnerReasonCode.INPUT_FACTORY_ERROR) from None

    def _deadline(self, case: EvaluationCase) -> EvaluationDeadline:
        try:
            started = self._now_seconds()
            expires = (
                started + case.timeout_seconds
                if case.timeout_seconds is not None
                else None
            )
            return EvaluationDeadline(started, expires)
        except Exception:
            raise _RunnerFailure(EvaluationRunnerReasonCode.CLOCK_ERROR) from None

    def _execute_target(
        self,
        case: EvaluationCase,
        prepared_input: PreparedEvaluationInput,
        fixture: EvaluationFixtureHandle | None,
        context: EvaluationRepetitionContext,
        deadline: EvaluationDeadline,
    ) -> TargetExecutionOutcome:
        try:
            outcome = self._target_executor.execute(
                case.target,
                prepared_input,
                fixture,
                context,
                deadline,
            )
        except TargetExecutorNotFoundError:
            raise _RunnerFailure(
                EvaluationRunnerReasonCode.TARGET_EXECUTOR_NOT_FOUND
            ) from None
        except Exception:
            raise _RunnerFailure(
                EvaluationRunnerReasonCode.TARGET_EXECUTOR_ERROR
            ) from None
        if type(outcome) is not TargetExecutionOutcome:
            raise _RunnerFailure(EvaluationRunnerReasonCode.TARGET_EXECUTOR_ERROR)
        return outcome

    def _now_seconds(self) -> int:
        value = self._clock.now_seconds()
        if type(value) is not int or value < 0:
            raise ValueError("clock must return a non-negative integer")
        return value

    def _evaluate_completed_repetition(
        self,
        case: EvaluationCase,
        repetition_index: int,
        outcome: TargetExecutionOutcome,
        assertion_specs: tuple[AssertionSpec, ...],
        scoring_plan: EvaluationCaseScoringPlan,
    ) -> RepetitionEvaluationResult:
        source = _SnapshotObservationSource(outcome.observations)
        assertion_evaluator = AssertionEvaluator(source, self._invariant_evaluator)
        assertion_results = tuple(
            assertion_evaluator.evaluate(spec) for spec in assertion_specs
        )
        score_results: tuple[ScoreResult, ...] = ()
        rubric_results: tuple[RubricScoreResult, ...] = ()
        if scoring_plan.criteria:
            if self._scorer is None:
                raise AssertionError("validated scoring requires an injected scorer")
            score_evaluator = ScoreEvaluator(source, self._scorer)
            score_results = tuple(
                score_evaluator.evaluate(criterion)
                for criterion in scoring_plan.criteria
            )
            aggregator = RubricAggregator()
            rubric_results = tuple(
                aggregator.aggregate(
                    rubric,
                    tuple(
                        result
                        for result in score_results
                        if result.criterion_ref
                        in {item.criterion_ref for item in rubric.criteria}
                    ),
                )
                for rubric in scoring_plan.rubrics
            )

        verdict, reason, infrastructure_error = _repetition_verdict(
            assertion_results,
            score_results,
            rubric_results,
        )
        execution = CaseExecutionResult(
            case.schema_version,
            case.case_id,
            repetition_index,
            CaseExecutionStatus.COMPLETED,
            observation_refs=tuple(
                entry.observation_ref for entry in outcome.observations.entries
            ),
            duration_milliseconds=outcome.duration_milliseconds,
        )
        return RepetitionEvaluationResult(
            case.schema_version,
            execution,
            verdict,
            assertion_results=assertion_results,
            score_results=score_results,
            rubric_results=rubric_results,
            reason_code=reason,
            infrastructure_error=infrastructure_error,
        )


class _RunnerFailure(Exception):
    def __init__(self, reason_code: EvaluationRunnerReasonCode) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code.value)


def _resolve_assertion_specs(
    case: EvaluationCase,
    catalog: EvaluationAssertionCatalog,
) -> tuple[AssertionSpec, ...] | None:
    resolved: list[AssertionSpec] = []
    for reference in case.assertion_refs:
        spec = catalog.resolve(reference)
        if spec is None:
            return None
        resolved.append(spec)
    return tuple(resolved)


def _configuration_error(
    case: EvaluationCase,
    assertion_specs: tuple[AssertionSpec, ...] | None,
    scoring_plan: EvaluationCaseScoringPlan,
    scorer: EvaluationScorerPort | None,
) -> EvaluationRunnerReasonCode | None:
    if assertion_specs is None or any(
        spec.schema_version != case.schema_version for spec in assertion_specs
    ):
        return EvaluationRunnerReasonCode.ASSERTION_CONFIGURATION_ERROR
    if any(
        criterion.schema_version != case.schema_version
        for criterion in scoring_plan.criteria
    ) or any(
        rubric.schema_version != case.schema_version for rubric in scoring_plan.rubrics
    ):
        return EvaluationRunnerReasonCode.SCORING_CONFIGURATION_ERROR
    if scoring_plan.criteria and scorer is None:
        return EvaluationRunnerReasonCode.SCORING_CONFIGURATION_ERROR
    return None


def _repetition_verdict(
    assertion_results: tuple[AssertionResult, ...],
    score_results: tuple[ScoreResult, ...],
    rubric_results: tuple[RubricScoreResult, ...],
) -> tuple[EvaluationVerdict, EvaluationRunnerReasonCode | None, bool]:
    if any(
        result.verdict is EvaluationVerdict.ERROR for result in assertion_results
    ):
        return (
            EvaluationVerdict.ERROR,
            EvaluationRunnerReasonCode.ASSERTION_EVALUATION_ERROR,
            True,
        )
    if any(
        result.status is ScoreStatus.ERROR for result in score_results
    ) or any(result.status is ScoreStatus.ERROR for result in rubric_results):
        return (
            EvaluationVerdict.ERROR,
            EvaluationRunnerReasonCode.SCORING_EVALUATION_ERROR,
            True,
        )
    if any(
        result.verdict is EvaluationVerdict.FAIL for result in assertion_results
    ):
        return (
            EvaluationVerdict.FAIL,
            EvaluationRunnerReasonCode.ASSERTION_FAILED,
            False,
        )
    if any(
        result.verdict is EvaluationVerdict.INCONCLUSIVE
        for result in assertion_results
    ):
        return (
            EvaluationVerdict.INCONCLUSIVE,
            EvaluationRunnerReasonCode.ASSERTION_INCONCLUSIVE,
            False,
        )
    return EvaluationVerdict.PASS, None, False


def _error_repetition(
    case: EvaluationCase,
    repetition_index: int,
    reason: EvaluationRunnerReasonCode,
    duration_milliseconds: int | None = None,
) -> RepetitionEvaluationResult:
    execution = CaseExecutionResult(
        case.schema_version,
        case.case_id,
        repetition_index,
        CaseExecutionStatus.ERROR,
        duration_milliseconds=duration_milliseconds,
        error_code=EvaluationReasonCode(reason.value),
    )
    return RepetitionEvaluationResult(
        case.schema_version,
        execution,
        EvaluationVerdict.ERROR,
        reason_code=reason,
        infrastructure_error=True,
    )


def _skipped_case(
    case: EvaluationCase,
    reason: EvaluationRunnerReasonCode,
) -> CaseEvaluationResult:
    execution = CaseExecutionResult(
        case.schema_version,
        case.case_id,
        1,
        CaseExecutionStatus.SKIPPED,
    )
    repetition = RepetitionEvaluationResult(
        case.schema_version,
        execution,
        EvaluationVerdict.SKIPPED,
        reason_code=reason,
    )
    return _case_result(case, (repetition,))


def _case_result(
    case: EvaluationCase,
    repetitions: tuple[RepetitionEvaluationResult, ...],
) -> CaseEvaluationResult:
    verdict = _case_verdict(repetitions)
    reasons = _unique_reason_codes(
        EvaluationReasonCode(result.reason_code.value)
        for result in repetitions
        if result.reason_code is not None
    )
    return CaseEvaluationResult(
        case.schema_version,
        case.case_id,
        verdict,
        tuple(result.execution_result for result in repetitions),
        reason_codes=reasons,
        repetition_results=repetitions,
    )


def _case_verdict(
    repetitions: tuple[RepetitionEvaluationResult, ...],
) -> EvaluationVerdict:
    verdicts = tuple(result.verdict for result in repetitions)
    if EvaluationVerdict.ERROR in verdicts:
        return EvaluationVerdict.ERROR
    if EvaluationVerdict.FAIL in verdicts:
        return EvaluationVerdict.FAIL
    if EvaluationVerdict.INCONCLUSIVE in verdicts:
        return EvaluationVerdict.INCONCLUSIVE
    if all(verdict is EvaluationVerdict.SKIPPED for verdict in verdicts):
        return EvaluationVerdict.SKIPPED
    if EvaluationVerdict.SKIPPED in verdicts:
        return EvaluationVerdict.INCONCLUSIVE
    return EvaluationVerdict.PASS


def _suite_verdict(results: tuple[CaseEvaluationResult, ...]) -> EvaluationVerdict:
    verdicts = tuple(result.verdict for result in results)
    if EvaluationVerdict.ERROR in verdicts:
        return EvaluationVerdict.ERROR
    if EvaluationVerdict.FAIL in verdicts:
        return EvaluationVerdict.FAIL
    if EvaluationVerdict.INCONCLUSIVE in verdicts:
        return EvaluationVerdict.INCONCLUSIVE
    if all(verdict is EvaluationVerdict.SKIPPED for verdict in verdicts):
        return EvaluationVerdict.SKIPPED
    if EvaluationVerdict.SKIPPED in verdicts:
        return EvaluationVerdict.INCONCLUSIVE
    return EvaluationVerdict.PASS


def _case_has_infrastructure_error(result: CaseEvaluationResult) -> bool:
    return any(item.infrastructure_error for item in result.repetition_results)


def _unique_reason_codes(
    codes: Iterable[EvaluationReasonCode],
) -> tuple[EvaluationReasonCode, ...]:
    unique: list[EvaluationReasonCode] = []
    for code in codes:
        if code not in unique:
            unique.append(code)
    return tuple(unique)
