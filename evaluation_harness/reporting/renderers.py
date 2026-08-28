from __future__ import annotations

import json
from typing import Final

from evaluation_harness.contracts.identity import EvaluationReasonCode
from evaluation_harness.contracts.scoring import NormalizedScore
from evaluation_harness.reporting.model import (
    EvaluationAssertionReport,
    EvaluationCaseReport,
    EvaluationRepetitionReport,
    EvaluationRubricReport,
    EvaluationScoreReport,
    EvaluationSuiteReport,
)

MAX_SERIALIZED_REPORT_BYTES: Final = 2_000_000


class ReportSizeLimitError(ValueError):
    pass


class EvaluationJsonReportRenderer:
    def __init__(self, max_output_bytes: int = MAX_SERIALIZED_REPORT_BYTES) -> None:
        self._max_output_bytes = _validate_limit(max_output_bytes)

    def render(self, report: EvaluationSuiteReport) -> bytes:
        if type(report) is not EvaluationSuiteReport:
            raise TypeError("report must be an EvaluationSuiteReport")
        rendered = json.dumps(
            _suite_payload(report),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return _enforce_size(rendered, self._max_output_bytes)


class EvaluationMarkdownReportRenderer:
    def __init__(self, max_output_bytes: int = MAX_SERIALIZED_REPORT_BYTES) -> None:
        self._max_output_bytes = _validate_limit(max_output_bytes)

    def render(self, report: EvaluationSuiteReport) -> bytes:
        if type(report) is not EvaluationSuiteReport:
            raise TypeError("report must be an EvaluationSuiteReport")
        lines = [
            f"# Evaluation suite `{_md(report.suite_code.value)}`",
            "",
            f"- Report schema: `{report.report_schema_version.major}.{report.report_schema_version.minor}`",
            f"- Evaluation schema: `{report.evaluation_schema_version.major}.{report.evaluation_schema_version.minor}`",
            f"- Suite ID: `{_md(report.suite_id.value)}`",
            f"- Verdict: `{report.verdict.value}`",
            f"- Infrastructure error: `{str(report.infrastructure_error).lower()}`",
            f"- Reasons: `{_reasons(report.reason_codes)}`",
            f"- Cases: `{report.summary.case_count}`",
            f"- Repetitions: `{report.summary.repetition_count}`",
            f"- PASS cases: `{report.summary.pass_count}`",
            f"- FAIL cases: `{report.summary.fail_count}`",
            f"- INCONCLUSIVE cases: `{report.summary.inconclusive_count}`",
            f"- ERROR cases: `{report.summary.error_count}`",
            f"- SKIPPED cases: `{report.summary.skipped_count}`",
            "",
        ]
        for case in report.cases:
            lines.extend(_case_lines(case))
        rendered = ("\n".join(lines).rstrip() + "\n").encode("utf-8")
        return _enforce_size(rendered, self._max_output_bytes)


def _suite_payload(report: EvaluationSuiteReport) -> dict[str, object]:
    return {
        "report_schema": {
            "major": report.report_schema_version.major,
            "minor": report.report_schema_version.minor,
        },
        "evaluation_schema": {
            "major": report.evaluation_schema_version.major,
            "minor": report.evaluation_schema_version.minor,
        },
        "suite_id": report.suite_id.value,
        "suite_code": report.suite_code.value,
        "verdict": report.verdict.value,
        "infrastructure_error": report.infrastructure_error,
        "reason_codes": [item.value for item in report.reason_codes],
        "summary": {
            "case_count": report.summary.case_count,
            "repetition_count": report.summary.repetition_count,
            "pass_count": report.summary.pass_count,
            "fail_count": report.summary.fail_count,
            "inconclusive_count": report.summary.inconclusive_count,
            "error_count": report.summary.error_count,
            "skipped_count": report.summary.skipped_count,
        },
        "cases": [_case_payload(item) for item in report.cases],
    }


def _case_payload(report: EvaluationCaseReport) -> dict[str, object]:
    return {
        "case_id": report.case_id.value,
        "case_code": report.case_code.value,
        "verdict": report.verdict.value,
        "infrastructure_error": report.infrastructure_error,
        "reason_codes": [item.value for item in report.reason_codes],
        "assertions": [_assertion_payload(item) for item in report.assertions],
        "scores": [_score_payload(item) for item in report.scores],
        "rubrics": [_rubric_payload(item) for item in report.rubrics],
        "repetitions": [_repetition_payload(item) for item in report.repetitions],
    }


def _repetition_payload(report: EvaluationRepetitionReport) -> dict[str, object]:
    return {
        "repetition_index": report.repetition_index,
        "execution_status": report.execution_status.value,
        "verdict": report.verdict.value if report.verdict is not None else None,
        "duration_milliseconds": report.duration_milliseconds,
        "reason_code": report.reason_code.value if report.reason_code is not None else None,
        "infrastructure_error": report.infrastructure_error,
        "assertions": [_assertion_payload(item) for item in report.assertions],
        "scores": [_score_payload(item) for item in report.scores],
        "rubrics": [_rubric_payload(item) for item in report.rubrics],
    }


def _assertion_payload(report: EvaluationAssertionReport) -> dict[str, object]:
    return {
        "assertion_ref": report.assertion_ref.value,
        "kind": report.kind.value,
        "verdict": report.verdict.value,
        "reason_code": report.reason_code.value if report.reason_code is not None else None,
    }


def _score_payload(report: EvaluationScoreReport) -> dict[str, object]:
    return {
        "criterion_ref": report.criterion_ref.value,
        "scorer_ref": report.scorer_ref.value,
        "status": report.status.value,
        "score": _score_value(report.score),
        "reason_code": report.reason_code.value if report.reason_code is not None else None,
    }


def _rubric_payload(report: EvaluationRubricReport) -> dict[str, object]:
    return {
        "rubric_ref": report.rubric_ref.value,
        "status": report.status.value,
        "criterion_refs": [item.value for item in report.criterion_refs],
        "score": _score_value(report.score),
        "reason_code": report.reason_code.value if report.reason_code is not None else None,
    }


def _score_value(score: NormalizedScore | None) -> dict[str, int] | None:
    if score is None:
        return None
    return {"numerator": score.numerator, "denominator": score.denominator}


def _case_lines(report: EvaluationCaseReport) -> list[str]:
    lines = [
        f"## Case `{_md(report.case_code.value)}`",
        "",
        f"- Case ID: `{_md(report.case_id.value)}`",
        f"- Verdict: `{report.verdict.value}`",
        f"- Infrastructure error: `{str(report.infrastructure_error).lower()}`",
        f"- Reasons: `{_reasons(report.reason_codes)}`",
    ]
    lines.extend(_evaluation_lines(report.assertions, report.scores, report.rubrics, "  "))
    for repetition in report.repetitions:
        lines.extend(
            [
                "",
                f"### Repetition {repetition.repetition_index}",
                "",
                f"- Execution: `{repetition.execution_status.value}`",
                f"- Verdict: `{repetition.verdict.value if repetition.verdict is not None else 'UNATTRIBUTED'}`",
                f"- Duration ms: `{repetition.duration_milliseconds if repetition.duration_milliseconds is not None else 'NONE'}`",
                f"- Reason: `{repetition.reason_code.value if repetition.reason_code is not None else 'NONE'}`",
                f"- Infrastructure error: `{str(repetition.infrastructure_error).lower()}`",
            ]
        )
        lines.extend(_evaluation_lines(repetition.assertions, repetition.scores, repetition.rubrics, "  "))
    lines.append("")
    return lines


def _evaluation_lines(
    assertions: tuple[EvaluationAssertionReport, ...],
    scores: tuple[EvaluationScoreReport, ...],
    rubrics: tuple[EvaluationRubricReport, ...],
    prefix: str,
) -> list[str]:
    lines: list[str] = []
    for assertion in assertions:
        lines.append(
            f"{prefix}- Assertion `{_md(assertion.assertion_ref.value)}`: `{assertion.kind.value}` / `{assertion.verdict.value}` / `{assertion.reason_code.value if assertion.reason_code is not None else 'NONE'}`"
        )
    for score in scores:
        lines.append(
            f"{prefix}- Score `{_md(score.criterion_ref.value)}` via `{_md(score.scorer_ref.value)}`: `{score.status.value}` / `{_score_text(score.score)}` / `{score.reason_code.value if score.reason_code is not None else 'NONE'}`"
        )
    for rubric in rubrics:
        criteria = ",".join(_md(ref.value) for ref in rubric.criterion_refs) or "NONE"
        lines.append(
            f"{prefix}- Rubric `{_md(rubric.rubric_ref.value)}`: `{rubric.status.value}` / `{_score_text(rubric.score)}` / criteria `{criteria}` / `{rubric.reason_code.value if rubric.reason_code is not None else 'NONE'}`"
        )
    return lines


def _score_text(score: NormalizedScore | None) -> str:
    return "NONE" if score is None else f"{score.numerator}/{score.denominator}"


def _reasons(values: tuple[EvaluationReasonCode, ...]) -> str:
    return ",".join(item.value for item in values) or "NONE"


def _md(value: str) -> str:
    for character in ("\\", "`", "*", "_", "[", "]", "<", ">"):
        value = value.replace(character, f"\\{character}")
    return value


def _validate_limit(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_SERIALIZED_REPORT_BYTES:
        raise ValueError("max_output_bytes exceeds the canonical report limit")
    return value


def _enforce_size(rendered: bytes, limit: int) -> bytes:
    if len(rendered) > limit:
        raise ReportSizeLimitError("serialized report exceeds the configured limit")
    return rendered
