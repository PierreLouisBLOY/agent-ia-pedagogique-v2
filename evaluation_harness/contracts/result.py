from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from evaluation_harness.contracts.assertion import AssertionResult
from evaluation_harness.contracts.identity import (
    MAX_ASSERTION_REFS_PER_CASE,
    MAX_CASES_PER_SUITE,
    MAX_DURATION_MILLISECONDS,
    MAX_OBSERVATION_REFS_PER_EXECUTION,
    MAX_REASON_CODES_PER_RESULT,
    MAX_REPEAT_COUNT,
    EvaluationCaseId,
    EvaluationObservationRef,
    EvaluationReasonCode,
    EvaluationSchemaVersion,
    EvaluationSuiteId,
    require_supported_schema_version,
)
from evaluation_harness.contracts.scoring import (
    MAX_RUBRIC_RESULTS_PER_CASE,
    MAX_SCORE_RESULTS_PER_CASE,
    RubricScoreResult,
    ScoreResult,
)
from evaluation_harness.contracts.verdict import EvaluationVerdict


class CaseExecutionStatus(Enum):
    """Offline execution state, distinct from runtime and evaluation verdicts."""

    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class CaseExecutionResult:
    """Caller-supplied facts about one offline case execution."""

    schema_version: EvaluationSchemaVersion
    case_id: EvaluationCaseId
    repetition_index: int
    status: CaseExecutionStatus
    observation_refs: tuple[EvaluationObservationRef, ...] = ()
    duration_milliseconds: int | None = None
    error_code: EvaluationReasonCode | None = None

    def __post_init__(self) -> None:
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.case_id, EvaluationCaseId):
            raise TypeError("case_id must be an EvaluationCaseId")
        if type(self.repetition_index) is not int:
            raise TypeError("repetition_index must be an integer")
        if not 1 <= self.repetition_index <= MAX_REPEAT_COUNT:
            raise ValueError("repetition_index exceeds the offline evaluation limit")
        if not isinstance(self.status, CaseExecutionStatus):
            raise TypeError("status must be a CaseExecutionStatus")
        self._validate_observation_refs()
        if self.duration_milliseconds is not None:
            if type(self.duration_milliseconds) is not int:
                raise TypeError("duration_milliseconds must be an integer or None")
            if not 0 <= self.duration_milliseconds <= MAX_DURATION_MILLISECONDS:
                raise ValueError("duration_milliseconds exceeds the offline limit")
        if self.error_code is not None and not isinstance(
            self.error_code, EvaluationReasonCode
        ):
            raise TypeError("error_code must be an EvaluationReasonCode or None")
        if self.status is CaseExecutionStatus.ERROR and self.error_code is None:
            raise ValueError("an execution error requires a bounded error code")
        if self.status is not CaseExecutionStatus.ERROR and self.error_code is not None:
            raise ValueError("only an execution error may carry an error code")
        if self.status is CaseExecutionStatus.SKIPPED and (
            self.observation_refs or self.duration_milliseconds is not None
        ):
            raise ValueError("a skipped execution has no observations or duration")

    def _validate_observation_refs(self) -> None:
        if type(self.observation_refs) is not tuple:
            raise TypeError("observation_refs must be a tuple")
        if len(self.observation_refs) > MAX_OBSERVATION_REFS_PER_EXECUTION:
            raise ValueError("too many observation refs for one execution")
        if any(
            type(reference) is not EvaluationObservationRef
            for reference in self.observation_refs
        ):
            raise TypeError(
                "observation_refs must contain EvaluationObservationRef values"
            )
        if len(self.observation_refs) != len(set(self.observation_refs)):
            raise ValueError("observation refs must be unique")


@dataclass(frozen=True, slots=True)
class CaseEvaluationResult:
    """Non-authoritative verdict over ordered offline execution facts."""

    schema_version: EvaluationSchemaVersion
    case_id: EvaluationCaseId
    verdict: EvaluationVerdict
    execution_results: tuple[CaseExecutionResult, ...]
    reason_codes: tuple[EvaluationReasonCode, ...] = ()
    assertion_results: tuple[AssertionResult, ...] = ()
    score_results: tuple[ScoreResult, ...] = ()
    rubric_results: tuple[RubricScoreResult, ...] = ()

    def __post_init__(self) -> None:
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.case_id, EvaluationCaseId):
            raise TypeError("case_id must be an EvaluationCaseId")
        if not isinstance(self.verdict, EvaluationVerdict):
            raise TypeError("verdict must be an EvaluationVerdict")
        self._validate_execution_results()
        _validate_reason_codes(self.reason_codes)
        self._validate_assertion_results()
        self._validate_score_results()
        self._validate_rubric_results()
        if self.verdict is EvaluationVerdict.PASS and self.reason_codes:
            raise ValueError("a PASS verdict does not require reason codes")
        if self.verdict is not EvaluationVerdict.PASS and not self.reason_codes:
            raise ValueError("a non-PASS verdict requires at least one reason code")
        statuses = tuple(result.status for result in self.execution_results)
        if CaseExecutionStatus.ERROR in statuses and self.verdict is not EvaluationVerdict.ERROR:
            raise ValueError("an execution error requires an ERROR evaluation verdict")
        if CaseExecutionStatus.SKIPPED in statuses and (
            self.verdict is not EvaluationVerdict.SKIPPED
            or any(status is not CaseExecutionStatus.SKIPPED for status in statuses)
        ):
            raise ValueError("skipped executions require a wholly SKIPPED case verdict")
        if self.verdict is EvaluationVerdict.SKIPPED and any(
            status is not CaseExecutionStatus.SKIPPED for status in statuses
        ):
            raise ValueError("a SKIPPED case verdict requires skipped executions")
        if self.verdict is EvaluationVerdict.PASS and any(
            result.verdict is not EvaluationVerdict.PASS
            for result in self.assertion_results
        ):
            raise ValueError("a non-PASS assertion result cannot aggregate to PASS")
        if self.verdict is EvaluationVerdict.SKIPPED and self.assertion_results:
            raise ValueError("a SKIPPED case has no assertion results")
        if self.verdict is EvaluationVerdict.SKIPPED and (
            self.score_results or self.rubric_results
        ):
            raise ValueError("a SKIPPED case has no score results")

    def _validate_execution_results(self) -> None:
        if type(self.execution_results) is not tuple:
            raise TypeError("execution_results must be a tuple")
        if not self.execution_results:
            raise ValueError("a case evaluation requires at least one execution result")
        if len(self.execution_results) > MAX_REPEAT_COUNT:
            raise ValueError("too many execution results for one case evaluation")
        if any(
            type(result) is not CaseExecutionResult for result in self.execution_results
        ):
            raise TypeError("execution_results must contain CaseExecutionResult values")
        if any(result.case_id != self.case_id for result in self.execution_results):
            raise ValueError("execution result case IDs must match the evaluated case")
        expected_indexes = tuple(range(1, len(self.execution_results) + 1))
        actual_indexes = tuple(
            result.repetition_index for result in self.execution_results
        )
        if actual_indexes != expected_indexes:
            raise ValueError("execution results must use contiguous ordered repetitions")

    def _validate_assertion_results(self) -> None:
        if type(self.assertion_results) is not tuple:
            raise TypeError("assertion_results must be a tuple")
        if len(self.assertion_results) > MAX_ASSERTION_REFS_PER_CASE:
            raise ValueError("too many assertion results for one case evaluation")
        if any(type(result) is not AssertionResult for result in self.assertion_results):
            raise TypeError("assertion_results must contain AssertionResult values")
        assertion_refs = tuple(
            result.assertion_ref for result in self.assertion_results
        )
        if len(assertion_refs) != len(set(assertion_refs)):
            raise ValueError("assertion result refs must be unique")

    def _validate_score_results(self) -> None:
        if type(self.score_results) is not tuple:
            raise TypeError("score_results must be a tuple")
        if len(self.score_results) > MAX_SCORE_RESULTS_PER_CASE:
            raise ValueError("too many score results for one case evaluation")
        if any(type(result) is not ScoreResult for result in self.score_results):
            raise TypeError("score_results must contain ScoreResult values")
        criterion_refs = tuple(result.criterion_ref for result in self.score_results)
        if len(criterion_refs) != len(set(criterion_refs)):
            raise ValueError("case score criterion refs must be unique")

    def _validate_rubric_results(self) -> None:
        if type(self.rubric_results) is not tuple:
            raise TypeError("rubric_results must be a tuple")
        if len(self.rubric_results) > MAX_RUBRIC_RESULTS_PER_CASE:
            raise ValueError("too many rubric results for one case evaluation")
        if any(
            type(result) is not RubricScoreResult for result in self.rubric_results
        ):
            raise TypeError("rubric_results must contain RubricScoreResult values")
        rubric_refs = tuple(result.rubric_ref for result in self.rubric_results)
        if len(rubric_refs) != len(set(rubric_refs)):
            raise ValueError("case rubric result refs must be unique")


@dataclass(frozen=True, slots=True)
class SuiteEvaluationResult:
    """Structural suite result without scoring or execution behavior."""

    schema_version: EvaluationSchemaVersion
    suite_id: EvaluationSuiteId
    verdict: EvaluationVerdict
    case_results: tuple[CaseEvaluationResult, ...]
    infrastructure_error: bool = False
    reason_codes: tuple[EvaluationReasonCode, ...] = ()

    def __post_init__(self) -> None:
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.suite_id, EvaluationSuiteId):
            raise TypeError("suite_id must be an EvaluationSuiteId")
        if not isinstance(self.verdict, EvaluationVerdict):
            raise TypeError("verdict must be an EvaluationVerdict")
        self._validate_case_results()
        if type(self.infrastructure_error) is not bool:
            raise TypeError("infrastructure_error must be a boolean")
        _validate_reason_codes(self.reason_codes)
        if self.verdict is EvaluationVerdict.PASS:
            if self.reason_codes:
                raise ValueError("a PASS verdict does not require reason codes")
            if any(
                result.verdict is not EvaluationVerdict.PASS
                for result in self.case_results
            ):
                raise ValueError("a non-PASS case result cannot aggregate to PASS")
        elif not self.reason_codes:
            raise ValueError("a non-PASS suite verdict requires a reason code")
        if self.infrastructure_error and self.verdict is not EvaluationVerdict.ERROR:
            raise ValueError("an infrastructure error requires an ERROR suite verdict")
        if self.verdict is EvaluationVerdict.SKIPPED and any(
            result.verdict is not EvaluationVerdict.SKIPPED
            for result in self.case_results
        ):
            raise ValueError("a SKIPPED suite requires only skipped case results")

    def _validate_case_results(self) -> None:
        if type(self.case_results) is not tuple:
            raise TypeError("case_results must be a tuple")
        if not self.case_results:
            raise ValueError("a suite evaluation requires at least one case result")
        if len(self.case_results) > MAX_CASES_PER_SUITE:
            raise ValueError("too many case results for one suite evaluation")
        if any(type(result) is not CaseEvaluationResult for result in self.case_results):
            raise TypeError("case_results must contain CaseEvaluationResult values")
        case_ids = tuple(result.case_id for result in self.case_results)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case result IDs must be unique within a suite result")

    @property
    def case_count(self) -> int:
        return len(self.case_results)

    def count_for(self, verdict: EvaluationVerdict) -> int:
        if not isinstance(verdict, EvaluationVerdict):
            raise TypeError("verdict must be an EvaluationVerdict")
        return sum(result.verdict is verdict for result in self.case_results)


def _validate_reason_codes(reason_codes: tuple[EvaluationReasonCode, ...]) -> None:
    if type(reason_codes) is not tuple:
        raise TypeError("reason_codes must be a tuple")
    if len(reason_codes) > MAX_REASON_CODES_PER_RESULT:
        raise ValueError("too many reason codes for one evaluation result")
    if any(type(code) is not EvaluationReasonCode for code in reason_codes):
        raise TypeError("reason_codes must contain EvaluationReasonCode values")
    if len(reason_codes) != len(set(reason_codes)):
        raise ValueError("reason codes must be unique")
