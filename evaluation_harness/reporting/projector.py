from __future__ import annotations

from collections.abc import Iterable

from evaluation_harness.contracts.assertion import AssertionResult
from evaluation_harness.contracts.case import EvaluationCase
from evaluation_harness.contracts.identity import EvaluationReasonCode
from evaluation_harness.contracts.result import (
    CaseEvaluationResult,
    CaseExecutionResult,
    RepetitionEvaluationResult,
    SuiteEvaluationResult,
)
from evaluation_harness.contracts.scoring import RubricScoreResult, ScoreResult
from evaluation_harness.contracts.suite import EvaluationSuite
from evaluation_harness.contracts.verdict import EvaluationVerdict
from evaluation_harness.reporting.model import (
    EVALUATION_REPORT_SCHEMA_V1_0,
    EvaluationAssertionReport,
    EvaluationCaseReport,
    EvaluationRepetitionReport,
    EvaluationReportSummary,
    EvaluationRubricReport,
    EvaluationScoreReport,
    EvaluationSuiteReport,
)


class EvaluationReportProjector:
    """Pure allowlisted projection from declarations and safe results."""

    def project(
        self,
        suite: EvaluationSuite,
        result: SuiteEvaluationResult,
    ) -> EvaluationSuiteReport:
        if type(suite) is not EvaluationSuite:
            raise TypeError("suite must be an EvaluationSuite")
        if type(result) is not SuiteEvaluationResult:
            raise TypeError("result must be a SuiteEvaluationResult")
        if suite.suite_id != result.suite_id:
            raise ValueError("suite definition and result IDs must match")
        if suite.schema_version != result.schema_version:
            raise ValueError("suite definition and result schemas must match")
        if tuple(case.case_id for case in suite.cases) != tuple(
            item.case_id for item in result.case_results
        ):
            raise ValueError("suite definition and result case order must match")

        cases = tuple(
            self._project_case(case, case_result)
            for case, case_result in zip(
                suite.cases, result.case_results, strict=True
            )
        )
        counts = {verdict: 0 for verdict in EvaluationVerdict}
        for case in cases:
            counts[case.verdict] += 1
        summary = EvaluationReportSummary(
            case_count=len(cases),
            repetition_count=sum(len(case.repetitions) for case in cases),
            pass_count=counts[EvaluationVerdict.PASS],
            fail_count=counts[EvaluationVerdict.FAIL],
            inconclusive_count=counts[EvaluationVerdict.INCONCLUSIVE],
            error_count=counts[EvaluationVerdict.ERROR],
            skipped_count=counts[EvaluationVerdict.SKIPPED],
        )
        return EvaluationSuiteReport(
            EVALUATION_REPORT_SCHEMA_V1_0,
            result.schema_version,
            result.suite_id,
            suite.code,
            result.verdict,
            result.infrastructure_error,
            result.reason_codes,
            cases,
            summary,
        )

    def _project_case(
        self,
        case: EvaluationCase,
        result: CaseEvaluationResult,
    ) -> EvaluationCaseReport:
        if case.case_id != result.case_id or case.schema_version != result.schema_version:
            raise ValueError("case definition and result must match")
        if len(result.execution_results) != case.repeat_count:
            raise ValueError("case definition and result repetition counts must match")
        repetitions = (
            tuple(_project_repetition(item) for item in result.repetition_results)
            if result.repetition_results
            else tuple(_project_legacy_execution(item) for item in result.execution_results)
        )
        return EvaluationCaseReport(
            result.case_id,
            case.code,
            result.verdict,
            result.reason_codes,
            any(item.infrastructure_error for item in repetitions),
            repetitions,
            assertions=_project_assertions(result.assertion_results),
            scores=_project_scores(result.score_results),
            rubrics=_project_rubrics(result.rubric_results),
        )


def _project_repetition(result: RepetitionEvaluationResult) -> EvaluationRepetitionReport:
    reason = (
        EvaluationReasonCode(result.reason_code.value)
        if result.reason_code is not None
        else result.execution_result.error_code
    )
    return EvaluationRepetitionReport(
        result.repetition_index,
        result.execution_result.status,
        result.verdict,
        result.execution_result.duration_milliseconds,
        reason,
        result.infrastructure_error,
        assertions=_project_assertions(result.assertion_results),
        scores=_project_scores(result.score_results),
        rubrics=_project_rubrics(result.rubric_results),
    )


def _project_legacy_execution(result: CaseExecutionResult) -> EvaluationRepetitionReport:
    return EvaluationRepetitionReport(
        result.repetition_index,
        result.status,
        None,
        result.duration_milliseconds,
        result.error_code,
        infrastructure_error=result.error_code is not None,
    )


def _project_assertions(
    results: Iterable[AssertionResult],
) -> tuple[EvaluationAssertionReport, ...]:
    return tuple(
        EvaluationAssertionReport(
            item.assertion_ref, item.kind, item.verdict, item.reason_code
        )
        for item in results
    )


def _project_scores(results: Iterable[ScoreResult]) -> tuple[EvaluationScoreReport, ...]:
    return tuple(
        EvaluationScoreReport(
            item.criterion_ref,
            item.scorer_ref,
            item.status,
            item.score,
            item.reason_code,
        )
        for item in results
    )


def _project_rubrics(
    results: Iterable[RubricScoreResult],
) -> tuple[EvaluationRubricReport, ...]:
    return tuple(
        EvaluationRubricReport(
            item.rubric_ref,
            item.status,
            tuple(score.criterion_ref for score in item.criterion_results),
            item.score,
            item.reason_code,
        )
        for item in results
    )
