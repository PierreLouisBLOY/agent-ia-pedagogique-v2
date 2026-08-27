from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, fields

import pytest

from backend.agent_runtime.contracts import AgentResultStatus, GateDecisionValue
from backend.agent_runtime.contracts.errors import EffectState
from backend.agent_runtime.policy import ToolCallDisposition
from backend.agent_runtime.security.runtime_composition import RuntimeSecurityDisposition
from evaluation_harness import (
    EVALUATION_SCHEMA_V1_0,
    MAX_ASSERTION_REFS_PER_CASE,
    MAX_CASES_PER_SUITE,
    MAX_REPEAT_COUNT,
    MAX_TAGS,
    CaseEvaluationResult,
    CaseExecutionResult,
    CaseExecutionStatus,
    EvaluationAssertionRef,
    EvaluationCase,
    EvaluationCaseCode,
    EvaluationCaseId,
    EvaluationFixtureRef,
    EvaluationInfrastructureErrorPolicy,
    EvaluationInputFactoryRef,
    EvaluationObservationRef,
    EvaluationReasonCode,
    EvaluationSchemaVersion,
    EvaluationSuite,
    EvaluationSuiteCode,
    EvaluationSuiteId,
    EvaluationTagCode,
    EvaluationTargetCode,
    EvaluationTargetKind,
    EvaluationTargetRef,
    EvaluationVerdict,
    SuiteEvaluationResult,
)


def _case(index: int = 1, **overrides: object) -> EvaluationCase:
    values: dict[str, object] = {
        "case_id": EvaluationCaseId(f"case-{index:02d}"),
        "schema_version": EVALUATION_SCHEMA_V1_0,
        "code": EvaluationCaseCode(f"EVAL.CASE.{index:02d}"),
        "title": f"Evaluation case {index}",
        "target": EvaluationTargetRef(
            EvaluationTargetKind.AGENT,
            EvaluationTargetCode("AG-01"),
        ),
        "input_factory_ref": EvaluationInputFactoryRef("factory.agent-input"),
        "assertion_refs": (EvaluationAssertionRef("assertion.status"),),
        "fixture_ref": EvaluationFixtureRef("fixture.agent"),
        "repeat_count": 1,
        "tags": (EvaluationTagCode("deterministic"),),
        "timeout_seconds": 30,
    }
    values.update(overrides)
    return EvaluationCase(**values)  # type: ignore[arg-type]


def _execution(
    case_id: EvaluationCaseId | None = None,
    *,
    repetition_index: int = 1,
    status: CaseExecutionStatus = CaseExecutionStatus.COMPLETED,
    error_code: EvaluationReasonCode | None = None,
) -> CaseExecutionResult:
    return CaseExecutionResult(
        schema_version=EVALUATION_SCHEMA_V1_0,
        case_id=case_id or EvaluationCaseId("case-01"),
        repetition_index=repetition_index,
        status=status,
        observation_refs=(EvaluationObservationRef("observation-01"),)
        if status is not CaseExecutionStatus.SKIPPED
        else (),
        duration_milliseconds=12 if status is not CaseExecutionStatus.SKIPPED else None,
        error_code=error_code,
    )


def _case_result(
    case_id: EvaluationCaseId | None = None,
    *,
    verdict: EvaluationVerdict = EvaluationVerdict.PASS,
) -> CaseEvaluationResult:
    resolved_case_id = case_id or EvaluationCaseId("case-01")
    status = {
        EvaluationVerdict.ERROR: CaseExecutionStatus.ERROR,
        EvaluationVerdict.SKIPPED: CaseExecutionStatus.SKIPPED,
    }.get(verdict, CaseExecutionStatus.COMPLETED)
    return CaseEvaluationResult(
        schema_version=EVALUATION_SCHEMA_V1_0,
        case_id=resolved_case_id,
        verdict=verdict,
        execution_results=(
            _execution(
                resolved_case_id,
                status=status,
                error_code=EvaluationReasonCode("EXECUTION.ERROR")
                if status is CaseExecutionStatus.ERROR
                else None,
            ),
        ),
        reason_codes=()
        if verdict is EvaluationVerdict.PASS
        else (EvaluationReasonCode(f"CASE.{verdict.value}"),),
    )


def test_evaluation_verdict_is_exact_closed_and_not_a_string_enum() -> None:
    assert [item.value for item in EvaluationVerdict] == [
        "PASS",
        "FAIL",
        "INCONCLUSIVE",
        "ERROR",
        "SKIPPED",
    ]
    assert EvaluationVerdict.PASS != "PASS"


def test_evaluation_pass_is_distinct_from_all_authority_and_runtime_statuses() -> None:
    assert EvaluationVerdict.PASS != ToolCallDisposition.ALLOW
    assert EvaluationVerdict.PASS != GateDecisionValue.APPROVED
    assert EvaluationVerdict.PASS != AgentResultStatus.SUCCEEDED
    assert EvaluationVerdict.PASS != EffectState.COMMITTED
    assert EvaluationVerdict.PASS != RuntimeSecurityDisposition.PASS


@pytest.mark.parametrize(
    "factory",
    [
        EvaluationCaseId,
        EvaluationSuiteId,
        EvaluationCaseCode,
        EvaluationSuiteCode,
        EvaluationTargetCode,
        EvaluationFixtureRef,
        EvaluationInputFactoryRef,
        EvaluationAssertionRef,
        EvaluationObservationRef,
    ],
)
def test_safe_identifiers_accept_caller_supplied_opaque_values(factory: type[object]) -> None:
    value = factory("evaluation.ref-01")
    assert str(value) == "evaluation.ref-01"


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "contains spaces",
        "../private",
        "C:\\private\\result.json",
        "/private/result.json",
        "https://example.test/result",
        "x" * 129,
        "sk-" + "a" * 40,
    ],
)
def test_safe_identifiers_reject_unbounded_path_url_and_secret_values(invalid: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        EvaluationCaseId(invalid)


def test_safe_identifiers_reject_non_strings_without_echoing_the_value() -> None:
    with pytest.raises(TypeError, match="EvaluationCaseId") as raised:
        EvaluationCaseId(object())  # type: ignore[arg-type]
    assert "object at" not in str(raised.value)


@pytest.mark.parametrize("valid", ["security", "recovery", "smoke", "agent.ag-01"])
def test_tag_codes_accept_normalized_bounded_values(valid: str) -> None:
    assert EvaluationTagCode(valid).value == valid


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "Security",
        "has space",
        "provider/openai",
        "x" * 65,
        "sk-" + "a" * 40,
    ],
)
def test_tag_codes_reject_non_normalized_or_unbounded_values(invalid: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        EvaluationTagCode(invalid)


@pytest.mark.parametrize(
    "invalid",
    ["", "case failed", "lower.case", "X" * 129, "AKIA" + "A" * 16],
)
def test_reason_codes_are_uppercase_bounded_codes(invalid: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        EvaluationReasonCode(invalid)


def test_evaluation_schema_is_independent_bounded_and_explicit() -> None:
    assert EVALUATION_SCHEMA_V1_0 == EvaluationSchemaVersion(1, 0)
    with pytest.raises(ValueError):
        EvaluationSchemaVersion(0, 1)
    with pytest.raises(ValueError):
        _case(schema_version=EvaluationSchemaVersion(2, 0))


def test_target_vocabulary_is_closed_minimal_and_provider_neutral() -> None:
    assert [kind.value for kind in EvaluationTargetKind] == [
        "SYSTEM",
        "WORKFLOW",
        "AGENT",
        "PIPELINE",
        "BOUNDARY",
        "COMPONENT",
    ]
    assert all(
        provider not in {kind.value for kind in EvaluationTargetKind}
        for provider in ("OPENAI", "ANTHROPIC", "GEMINI")
    )


def test_target_ref_is_data_only_typed_and_immutable() -> None:
    target = EvaluationTargetRef(
        EvaluationTargetKind.BOUNDARY,
        EvaluationTargetCode("runtime.routing"),
    )
    assert not hasattr(target, "resolve")
    assert not hasattr(target, "__dict__")
    with pytest.raises(FrozenInstanceError):
        target.kind = EvaluationTargetKind.SYSTEM  # type: ignore[misc]
    with pytest.raises(TypeError):
        EvaluationTargetRef("AGENT", EvaluationTargetCode("AG-01"))  # type: ignore[arg-type]


def test_evaluation_case_has_only_bounded_typed_structural_fields() -> None:
    case = _case()
    assert tuple(item.name for item in fields(EvaluationCase)) == (
        "case_id",
        "schema_version",
        "code",
        "title",
        "target",
        "input_factory_ref",
        "assertion_refs",
        "fixture_ref",
        "repeat_count",
        "tags",
        "timeout_seconds",
    )
    assert case.repeat_count == 1
    assert not hasattr(case, "payload")
    assert not hasattr(case, "metadata")
    assert not hasattr(case, "__dict__")


@pytest.mark.parametrize(
    "invalid_title",
    ["", " leading", "trailing ", "line\nbreak", "https://example.test", "x" * 257],
)
def test_case_title_is_bounded_and_safe(invalid_title: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        _case(title=invalid_title)


def test_case_rejects_callable_or_untyped_factory_reference() -> None:
    with pytest.raises(TypeError, match="input_factory_ref"):
        _case(input_factory_ref=lambda: object())


def test_case_requires_unique_bounded_assertion_refs() -> None:
    reference = EvaluationAssertionRef("assertion.status")
    with pytest.raises(ValueError, match="unique"):
        _case(assertion_refs=(reference, reference))
    with pytest.raises(ValueError, match="too many"):
        _case(
            assertion_refs=tuple(
                EvaluationAssertionRef(f"assertion-{index}")
                for index in range(MAX_ASSERTION_REFS_PER_CASE + 1)
            )
        )
    with pytest.raises(ValueError, match="at least one"):
        _case(assertion_refs=())


def test_case_requires_unique_bounded_immutable_tags() -> None:
    tag = EvaluationTagCode("security")
    with pytest.raises(ValueError, match="unique"):
        _case(tags=(tag, tag))
    with pytest.raises(ValueError, match="too many"):
        _case(
            tags=tuple(EvaluationTagCode(f"tag-{index}") for index in range(MAX_TAGS + 1))
        )
    with pytest.raises(TypeError, match="tuple"):
        _case(tags=[tag])


@pytest.mark.parametrize("repeat_count", [0, MAX_REPEAT_COUNT + 1, True])
def test_case_rejects_invalid_repeat_count(repeat_count: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _case(repeat_count=repeat_count)


@pytest.mark.parametrize("timeout", [0, 86_401, 1.5])
def test_case_rejects_invalid_timeout(timeout: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _case(timeout_seconds=timeout)


def test_case_is_frozen() -> None:
    case = _case()
    with pytest.raises(FrozenInstanceError):
        case.repeat_count = 2  # type: ignore[misc]


def test_suite_embeds_cases_in_caller_order_with_continue_as_default() -> None:
    first = _case(1)
    second = _case(2)
    suite = EvaluationSuite(
        EvaluationSuiteId("suite-01"),
        EVALUATION_SCHEMA_V1_0,
        EvaluationSuiteCode("EVAL.SUITE.01"),
        "Evaluation suite",
        (first, second),
    )
    assert suite.cases == (first, second)
    assert (
        suite.infrastructure_error_policy
        is EvaluationInfrastructureErrorPolicy.CONTINUE
    )
    assert not hasattr(suite, "selector")
    assert not hasattr(suite, "suites")


def test_suite_rejects_empty_duplicate_untyped_and_excessive_cases() -> None:
    common = (
        EvaluationSuiteId("suite-01"),
        EVALUATION_SCHEMA_V1_0,
        EvaluationSuiteCode("EVAL.SUITE.01"),
        "Evaluation suite",
    )
    with pytest.raises(ValueError, match="at least one"):
        EvaluationSuite(*common, ())
    case = _case()
    with pytest.raises(ValueError, match="unique"):
        EvaluationSuite(*common, (case, case))
    with pytest.raises(TypeError, match="tuple"):
        EvaluationSuite(*common, [case])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="too many"):
        EvaluationSuite(
            *common,
            tuple(_case(index) for index in range(1, MAX_CASES_PER_SUITE + 2)),
        )


def test_suite_rejects_untyped_infrastructure_error_policy() -> None:
    with pytest.raises(TypeError, match="infrastructure_error_policy"):
        EvaluationSuite(
            EvaluationSuiteId("suite-01"),
            EVALUATION_SCHEMA_V1_0,
            EvaluationSuiteCode("EVAL.SUITE.01"),
            "Evaluation suite",
            (_case(),),
            "CONTINUE",  # type: ignore[arg-type]
        )


def test_execution_result_is_bounded_and_caller_supplied() -> None:
    result = _execution()
    assert result.status is CaseExecutionStatus.COMPLETED
    assert result.duration_milliseconds == 12
    assert not hasattr(result, "started_at")
    assert not hasattr(result, "payload")
    assert not hasattr(result, "exception")


def test_execution_error_requires_only_a_safe_code() -> None:
    with pytest.raises(ValueError, match="requires"):
        _execution(status=CaseExecutionStatus.ERROR)
    with pytest.raises(ValueError, match="only"):
        _execution(error_code=EvaluationReasonCode("EXECUTION.ERROR"))


def test_skipped_execution_has_no_observation_or_duration() -> None:
    result = _execution(status=CaseExecutionStatus.SKIPPED)
    assert result.observation_refs == ()
    assert result.duration_milliseconds is None
    with pytest.raises(ValueError, match="skipped"):
        CaseExecutionResult(
            EVALUATION_SCHEMA_V1_0,
            EvaluationCaseId("case-01"),
            1,
            CaseExecutionStatus.SKIPPED,
            (EvaluationObservationRef("observation-01"),),
        )


def test_case_evaluation_requires_ordered_matching_repetitions() -> None:
    case_id = EvaluationCaseId("case-01")
    result = CaseEvaluationResult(
        EVALUATION_SCHEMA_V1_0,
        case_id,
        EvaluationVerdict.PASS,
        (
            _execution(case_id, repetition_index=1),
            _execution(case_id, repetition_index=2),
        ),
    )
    assert tuple(item.repetition_index for item in result.execution_results) == (1, 2)
    with pytest.raises(ValueError, match="contiguous"):
        CaseEvaluationResult(
            EVALUATION_SCHEMA_V1_0,
            case_id,
            EvaluationVerdict.PASS,
            (_execution(case_id, repetition_index=2),),
        )


def test_case_evaluation_rejects_mismatched_ids_and_silent_error_or_skip() -> None:
    with pytest.raises(ValueError, match="match"):
        CaseEvaluationResult(
            EVALUATION_SCHEMA_V1_0,
            EvaluationCaseId("case-01"),
            EvaluationVerdict.PASS,
            (_execution(EvaluationCaseId("case-02")),),
        )
    with pytest.raises(ValueError, match="ERROR"):
        CaseEvaluationResult(
            EVALUATION_SCHEMA_V1_0,
            EvaluationCaseId("case-01"),
            EvaluationVerdict.FAIL,
            (
                _execution(
                    status=CaseExecutionStatus.ERROR,
                    error_code=EvaluationReasonCode("EXECUTION.ERROR"),
                ),
            ),
            (EvaluationReasonCode("CASE.FAIL"),),
        )


def test_non_pass_case_verdict_requires_a_bounded_reason() -> None:
    with pytest.raises(ValueError, match="requires"):
        CaseEvaluationResult(
            EVALUATION_SCHEMA_V1_0,
            EvaluationCaseId("case-01"),
            EvaluationVerdict.INCONCLUSIVE,
            (_execution(),),
        )


def test_suite_result_counts_cases_without_weighted_scoring() -> None:
    first = _case_result(EvaluationCaseId("case-01"))
    second = _case_result(EvaluationCaseId("case-02"))
    result = SuiteEvaluationResult(
        EVALUATION_SCHEMA_V1_0,
        EvaluationSuiteId("suite-01"),
        EvaluationVerdict.PASS,
        (first, second),
    )
    assert result.case_count == 2
    assert result.count_for(EvaluationVerdict.PASS) == 2
    assert not hasattr(result, "score")
    assert not hasattr(result, "weights")


@pytest.mark.parametrize(
    "child_verdict",
    [
        EvaluationVerdict.FAIL,
        EvaluationVerdict.INCONCLUSIVE,
        EvaluationVerdict.ERROR,
        EvaluationVerdict.SKIPPED,
    ],
)
def test_non_pass_case_cannot_silently_aggregate_to_pass(
    child_verdict: EvaluationVerdict,
) -> None:
    with pytest.raises(ValueError, match="cannot aggregate"):
        SuiteEvaluationResult(
            EVALUATION_SCHEMA_V1_0,
            EvaluationSuiteId("suite-01"),
            EvaluationVerdict.PASS,
            (_case_result(verdict=child_verdict),),
        )


def test_infrastructure_error_is_distinct_from_case_failure() -> None:
    failed_case = _case_result(verdict=EvaluationVerdict.FAIL)
    result = SuiteEvaluationResult(
        EVALUATION_SCHEMA_V1_0,
        EvaluationSuiteId("suite-01"),
        EvaluationVerdict.FAIL,
        (failed_case,),
        infrastructure_error=False,
        reason_codes=(EvaluationReasonCode("SUITE.CASE_FAILED"),),
    )
    assert not result.infrastructure_error
    with pytest.raises(ValueError, match="ERROR"):
        SuiteEvaluationResult(
            EVALUATION_SCHEMA_V1_0,
            EvaluationSuiteId("suite-01"),
            EvaluationVerdict.FAIL,
            (failed_case,),
            infrastructure_error=True,
            reason_codes=(EvaluationReasonCode("SUITE.INFRASTRUCTURE_ERROR"),),
        )


def test_result_contracts_are_frozen_slotted_and_have_no_raw_data_channels() -> None:
    result = _case_result()
    with pytest.raises(FrozenInstanceError):
        result.verdict = EvaluationVerdict.FAIL  # type: ignore[misc]
    for contract in (CaseExecutionResult, CaseEvaluationResult, SuiteEvaluationResult):
        names = {item.name for item in fields(contract)}
        assert names.isdisjoint(
            {"prompt", "payload", "output", "exception", "metadata", "reasoning"}
        )
        assert "**" not in str(inspect.signature(contract))
