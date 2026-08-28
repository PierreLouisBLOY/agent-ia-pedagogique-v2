from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from evaluation_harness.contracts.assertion import AssertionKind, AssertionReasonCode
from evaluation_harness.contracts.identity import (
    MAX_ASSERTION_REFS_PER_CASE,
    MAX_CASES_PER_SUITE,
    MAX_DURATION_MILLISECONDS,
    MAX_REASON_CODES_PER_RESULT,
    MAX_REPEAT_COUNT,
    EvaluationAssertionRef,
    EvaluationCaseCode,
    EvaluationCaseId,
    EvaluationCriterionRef,
    EvaluationReasonCode,
    EvaluationRubricRef,
    EvaluationSchemaVersion,
    EvaluationScorerRef,
    EvaluationSuiteCode,
    EvaluationSuiteId,
    require_supported_schema_version,
)
from evaluation_harness.contracts.result import CaseExecutionStatus
from evaluation_harness.contracts.scoring import (
    MAX_RUBRIC_CRITERIA,
    MAX_RUBRIC_RESULTS_PER_CASE,
    MAX_SCORE_RESULTS_PER_CASE,
    NormalizedScore,
    ScoreReasonCode,
    ScoreStatus,
)
from evaluation_harness.contracts.verdict import EvaluationVerdict


@dataclass(frozen=True, slots=True)
class EvaluationReportSchemaVersion:
    major: int
    minor: int

    def __post_init__(self) -> None:
        if type(self.major) is not int or type(self.minor) is not int:
            raise TypeError("report schema components must be integers")
        if self.major != 1 or self.minor != 0:
            raise ValueError("unsupported evaluation report schema version")


EVALUATION_REPORT_SCHEMA_V1_0: Final = EvaluationReportSchemaVersion(1, 0)


@dataclass(frozen=True, slots=True)
class EvaluationAssertionReport:
    assertion_ref: EvaluationAssertionRef
    kind: AssertionKind
    verdict: EvaluationVerdict
    reason_code: AssertionReasonCode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.assertion_ref, EvaluationAssertionRef):
            raise TypeError("assertion_ref must be an EvaluationAssertionRef")
        if not isinstance(self.kind, AssertionKind):
            raise TypeError("kind must be an AssertionKind")
        if not isinstance(self.verdict, EvaluationVerdict):
            raise TypeError("verdict must be an EvaluationVerdict")
        if self.reason_code is not None and not isinstance(
            self.reason_code, AssertionReasonCode
        ):
            raise TypeError("reason_code must be an AssertionReasonCode or None")


@dataclass(frozen=True, slots=True)
class EvaluationScoreReport:
    criterion_ref: EvaluationCriterionRef
    scorer_ref: EvaluationScorerRef
    status: ScoreStatus
    score: NormalizedScore | None = None
    reason_code: ScoreReasonCode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.criterion_ref, EvaluationCriterionRef):
            raise TypeError("criterion_ref must be an EvaluationCriterionRef")
        if not isinstance(self.scorer_ref, EvaluationScorerRef):
            raise TypeError("scorer_ref must be an EvaluationScorerRef")
        _validate_score_state(self.status, self.score, self.reason_code)


@dataclass(frozen=True, slots=True)
class EvaluationRubricReport:
    rubric_ref: EvaluationRubricRef
    status: ScoreStatus
    criterion_refs: tuple[EvaluationCriterionRef, ...]
    score: NormalizedScore | None = None
    reason_code: ScoreReasonCode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rubric_ref, EvaluationRubricRef):
            raise TypeError("rubric_ref must be an EvaluationRubricRef")
        if type(self.criterion_refs) is not tuple:
            raise TypeError("criterion_refs must be a tuple")
        if len(self.criterion_refs) > MAX_RUBRIC_CRITERIA:
            raise ValueError("too many rubric criterion refs")
        if any(type(ref) is not EvaluationCriterionRef for ref in self.criterion_refs):
            raise TypeError("criterion_refs contain an unsupported value")
        if len(self.criterion_refs) != len(set(self.criterion_refs)):
            raise ValueError("rubric criterion refs must be unique")
        _validate_score_state(self.status, self.score, self.reason_code)


@dataclass(frozen=True, slots=True)
class EvaluationRepetitionReport:
    repetition_index: int
    execution_status: CaseExecutionStatus
    verdict: EvaluationVerdict | None
    duration_milliseconds: int | None
    reason_code: EvaluationReasonCode | None
    infrastructure_error: bool
    assertions: tuple[EvaluationAssertionReport, ...] = ()
    scores: tuple[EvaluationScoreReport, ...] = ()
    rubrics: tuple[EvaluationRubricReport, ...] = ()

    def __post_init__(self) -> None:
        if type(self.repetition_index) is not int or not 1 <= self.repetition_index <= MAX_REPEAT_COUNT:
            raise ValueError("repetition_index exceeds the report limit")
        if not isinstance(self.execution_status, CaseExecutionStatus):
            raise TypeError("execution_status must be a CaseExecutionStatus")
        if self.verdict is not None and not isinstance(self.verdict, EvaluationVerdict):
            raise TypeError("verdict must be an EvaluationVerdict or None")
        if self.duration_milliseconds is not None:
            if type(self.duration_milliseconds) is not int:
                raise TypeError("duration_milliseconds must be an integer or None")
            if not 0 <= self.duration_milliseconds <= MAX_DURATION_MILLISECONDS:
                raise ValueError("duration_milliseconds exceeds the report limit")
        if self.reason_code is not None and not isinstance(self.reason_code, EvaluationReasonCode):
            raise TypeError("reason_code must be an EvaluationReasonCode or None")
        if type(self.infrastructure_error) is not bool:
            raise TypeError("infrastructure_error must be a boolean")
        _validate_unique_reports(self.assertions, MAX_ASSERTION_REFS_PER_CASE, "assertion_ref")
        _validate_unique_reports(self.scores, MAX_SCORE_RESULTS_PER_CASE, "criterion_ref")
        _validate_unique_reports(self.rubrics, MAX_RUBRIC_RESULTS_PER_CASE, "rubric_ref")


@dataclass(frozen=True, slots=True)
class EvaluationCaseReport:
    case_id: EvaluationCaseId
    case_code: EvaluationCaseCode
    verdict: EvaluationVerdict
    reason_codes: tuple[EvaluationReasonCode, ...]
    infrastructure_error: bool
    repetitions: tuple[EvaluationRepetitionReport, ...]
    assertions: tuple[EvaluationAssertionReport, ...] = ()
    scores: tuple[EvaluationScoreReport, ...] = ()
    rubrics: tuple[EvaluationRubricReport, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, EvaluationCaseId) or not isinstance(self.case_code, EvaluationCaseCode):
            raise TypeError("case identity is invalid")
        if not isinstance(self.verdict, EvaluationVerdict):
            raise TypeError("verdict must be an EvaluationVerdict")
        _validate_reason_codes(self.reason_codes)
        if type(self.infrastructure_error) is not bool:
            raise TypeError("infrastructure_error must be a boolean")
        if type(self.repetitions) is not tuple or not self.repetitions:
            raise ValueError("case report requires ordered repetitions")
        if len(self.repetitions) > MAX_REPEAT_COUNT:
            raise ValueError("too many repetitions in case report")
        if tuple(item.repetition_index for item in self.repetitions) != tuple(range(1, len(self.repetitions) + 1)):
            raise ValueError("repetitions must be contiguous and ordered")
        _validate_unique_reports(self.assertions, MAX_ASSERTION_REFS_PER_CASE, "assertion_ref")
        _validate_unique_reports(self.scores, MAX_SCORE_RESULTS_PER_CASE, "criterion_ref")
        _validate_unique_reports(self.rubrics, MAX_RUBRIC_RESULTS_PER_CASE, "rubric_ref")


@dataclass(frozen=True, slots=True)
class EvaluationReportSummary:
    case_count: int
    repetition_count: int
    pass_count: int
    fail_count: int
    inconclusive_count: int
    error_count: int
    skipped_count: int

    def __post_init__(self) -> None:
        values = tuple(getattr(self, name) for name in self.__slots__)
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("report counts must be non-negative integers")
        if self.case_count != sum((self.pass_count, self.fail_count, self.inconclusive_count, self.error_count, self.skipped_count)):
            raise ValueError("case verdict counts must equal case_count")


@dataclass(frozen=True, slots=True)
class EvaluationSuiteReport:
    report_schema_version: EvaluationReportSchemaVersion
    evaluation_schema_version: EvaluationSchemaVersion
    suite_id: EvaluationSuiteId
    suite_code: EvaluationSuiteCode
    verdict: EvaluationVerdict
    infrastructure_error: bool
    reason_codes: tuple[EvaluationReasonCode, ...]
    cases: tuple[EvaluationCaseReport, ...]
    summary: EvaluationReportSummary

    def __post_init__(self) -> None:
        if self.report_schema_version != EVALUATION_REPORT_SCHEMA_V1_0:
            raise ValueError("unsupported report schema version")
        require_supported_schema_version(self.evaluation_schema_version)
        if not isinstance(self.suite_id, EvaluationSuiteId) or not isinstance(self.suite_code, EvaluationSuiteCode):
            raise TypeError("suite identity is invalid")
        if not isinstance(self.verdict, EvaluationVerdict):
            raise TypeError("verdict must be an EvaluationVerdict")
        if type(self.infrastructure_error) is not bool:
            raise TypeError("infrastructure_error must be a boolean")
        _validate_reason_codes(self.reason_codes)
        if type(self.cases) is not tuple or not self.cases:
            raise ValueError("suite report requires cases")
        if len(self.cases) > MAX_CASES_PER_SUITE:
            raise ValueError("too many cases in suite report")
        ids = tuple(item.case_id for item in self.cases)
        if len(ids) != len(set(ids)):
            raise ValueError("case report IDs must be unique")
        if type(self.summary) is not EvaluationReportSummary:
            raise TypeError("summary must be an EvaluationReportSummary")
        if self.summary.case_count != len(self.cases) or self.summary.repetition_count != sum(len(item.repetitions) for item in self.cases):
            raise ValueError("report summary counts must match cases")


def _validate_score_state(status: ScoreStatus, score: NormalizedScore | None, reason: ScoreReasonCode | None) -> None:
    if not isinstance(status, ScoreStatus):
        raise TypeError("status must be a ScoreStatus")
    if score is not None and type(score) is not NormalizedScore:
        raise TypeError("score must be a NormalizedScore or None")
    if reason is not None and not isinstance(reason, ScoreReasonCode):
        raise TypeError("reason_code must be a ScoreReasonCode or None")
    if status is ScoreStatus.SCORED:
        if score is None or reason is not None:
            raise ValueError("SCORED requires an exact score only")
    elif score is not None or reason is None:
        raise ValueError("non-SCORED requires a closed reason only")


def _validate_unique_reports(values: tuple[object, ...], limit: int, identity_field: str) -> None:
    if type(values) is not tuple:
        raise TypeError("report collections must be tuples")
    if len(values) > limit:
        raise ValueError("report collection exceeds its limit")
    identities = tuple(getattr(value, identity_field, None) for value in values)
    if None in identities or len(identities) != len(set(identities)):
        raise ValueError("report identities must be present and unique")


def _validate_reason_codes(values: tuple[EvaluationReasonCode, ...]) -> None:
    if type(values) is not tuple or len(values) > MAX_REASON_CODES_PER_RESULT:
        raise ValueError("reason codes exceed the report limit")
    if any(type(value) is not EvaluationReasonCode for value in values):
        raise TypeError("reason_codes contain an unsupported value")
    if len(values) != len(set(values)):
        raise ValueError("reason codes must be unique")
