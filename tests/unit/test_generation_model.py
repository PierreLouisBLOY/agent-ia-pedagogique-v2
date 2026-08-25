from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from backend.agent_runtime.agents.generation import (
    GenerationOperation,
    GenerationPort,
    GenerationPortError,
    GenerationPortErrorCode,
    GenerationPortRequest,
    GenerationPortResult,
    GenerationPortResultStatus,
)
from backend.agent_runtime.contracts import ProductionCandidate


def _request(**overrides: object) -> GenerationPortRequest:
    values: dict[str, object] = {
        "operation": GenerationOperation.GENERATE,
        "source_step_id": "step-generation-1",
        "production_kind": "lesson_plan",
        "objective": "Prepare a structured lesson plan",
        "output_format": "markdown",
        "resolved_inputs": {"audience": {"level": "beginner"}},
        "constraints": {"max_sections": 4},
        "evidence_refs": ("evidence:one", "evidence:two"),
        "target_ref": None,
        "expected_sections": ("Objectives", "Activities"),
        "output_contract": {"sections": ["title", "body"]},
    }
    values.update(overrides)
    return GenerationPortRequest(**values)  # type: ignore[arg-type]


def _result(**overrides: object) -> GenerationPortResult:
    values: dict[str, object] = {
        "source_step_id": "step-generation-1",
        "operation": GenerationOperation.GENERATE,
        "status": GenerationPortResultStatus.SUCCEEDED,
        "content": "Generated lesson plan.",
        "evidence_refs_used": ("evidence:one",),
    }
    values.update(overrides)
    return GenerationPortResult(**values)  # type: ignore[arg-type]


def test_generation_operation_has_exactly_three_values() -> None:
    assert tuple(GenerationOperation) == (
        GenerationOperation.GENERATE,
        GenerationOperation.TRANSFORM,
        GenerationOperation.CORRECT,
    )
    assert tuple(item.value for item in GenerationOperation) == (
        "GENERATE",
        "TRANSFORM",
        "CORRECT",
    )


def test_generation_operation_excludes_authority_and_search_vocabulary() -> None:
    assert {item.name for item in GenerationOperation}.isdisjoint(
        {"REVIEW", "VALIDATE", "PROMOTE", "SEARCH", "EXPORT", "TOOL", "UNKNOWN"}
    )


def test_generation_result_status_has_exactly_four_values() -> None:
    assert tuple(item.value for item in GenerationPortResultStatus) == (
        "SUCCEEDED",
        "PARTIAL",
        "REFUSED",
        "INSUFFICIENT_EVIDENCE",
    )


def test_generation_result_status_excludes_canonical_authority_states() -> None:
    assert {item.name for item in GenerationPortResultStatus}.isdisjoint(
        {"FAILED", "VALIDATED", "APPROVED", "PROMOTED", "CANONICAL", "REVIEWED"}
    )


def test_request_rejects_non_operation_value() -> None:
    with pytest.raises(TypeError, match="operation"):
        _request(operation="GENERATE")


@pytest.mark.parametrize(
    "field_name",
    ("source_step_id", "production_kind", "objective", "output_format"),
)
def test_request_rejects_empty_required_strings(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        _request(**{field_name: "  "})


def test_request_resolved_inputs_are_deeply_immutable() -> None:
    request = _request(resolved_inputs={"nested": {"items": ["a", "b"]}})
    assert request.resolved_inputs["nested"] == {"items": ("a", "b")}
    with pytest.raises(TypeError):
        request.resolved_inputs["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        request.resolved_inputs["nested"]["items"] = ()  # type: ignore[index]


def test_request_constraints_are_deeply_immutable() -> None:
    request = _request(constraints={"style": {"allowed": ["clear"]}})
    assert request.constraints["style"] == {"allowed": ("clear",)}
    with pytest.raises(TypeError):
        request.constraints["style"] = {}  # type: ignore[index]


def test_request_output_contract_is_deeply_immutable() -> None:
    request = _request(output_contract={"schema": {"required": ["title"]}})
    assert request.output_contract["schema"] == {"required": ("title",)}
    with pytest.raises(TypeError):
        request.output_contract["schema"] = {}  # type: ignore[index]


def test_request_requires_evidence_refs_to_be_a_tuple() -> None:
    with pytest.raises(TypeError, match="evidence_refs must be a tuple"):
        _request(evidence_refs=["evidence:one"])


def test_request_accepts_valid_contract_refs() -> None:
    assert _request(evidence_refs=("evidence:one", "evidence:two")).evidence_refs == (
        "evidence:one",
        "evidence:two",
    )


def test_request_rejects_invalid_evidence_ref() -> None:
    with pytest.raises(TypeError, match="evidence_refs item"):
        _request(evidence_refs=(object(),))


def test_request_rejects_invalid_target_ref() -> None:
    with pytest.raises(TypeError, match="target_ref"):
        _request(target_ref=object())


def test_request_rejects_non_tuple_expected_sections() -> None:
    with pytest.raises(TypeError, match="expected_sections must be a tuple"):
        _request(expected_sections=["Objectives"])


def test_request_rejects_empty_expected_section() -> None:
    with pytest.raises(ValueError, match="expected_sections item"):
        _request(expected_sections=("Objectives", " "))


def test_request_rejects_duplicate_expected_sections() -> None:
    with pytest.raises(ValueError, match="unique"):
        _request(expected_sections=("Objectives", "Objectives"))


def test_request_is_frozen_and_slotted() -> None:
    request = _request()
    with pytest.raises(FrozenInstanceError):
        request.objective = "Changed"  # type: ignore[misc]
    assert not hasattr(request, "__dict__")


def test_request_has_no_provider_prompt_or_authority_fields() -> None:
    names = {item.name for item in fields(GenerationPortRequest)}
    assert names.isdisjoint(
        {
            "api_key",
            "messages",
            "model",
            "permission_scope",
            "prompt",
            "system_prompt",
            "temperature",
            "tool_calls",
            "top_p",
        }
    )


def test_succeeded_requires_content_or_structured_payload() -> None:
    with pytest.raises(ValueError, match="SUCCEEDED requires"):
        _result(content=None, structured_payload={})


def test_succeeded_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="content"):
        _result(content=" ")


def test_succeeded_accepts_structured_payload_without_text_content() -> None:
    result = _result(content=None, structured_payload={"sections": ["one"]})
    assert result.content is None
    assert result.structured_payload == {"sections": ("one",)}


def test_partial_requires_content_or_structured_payload() -> None:
    with pytest.raises(ValueError, match="PARTIAL requires content"):
        _result(
            status=GenerationPortResultStatus.PARTIAL,
            content=None,
            warnings=({"code": "TRUNCATED"},),
        )


def test_partial_requires_warning_or_uncertainty() -> None:
    with pytest.raises(ValueError, match="warning or uncertainty"):
        _result(status=GenerationPortResultStatus.PARTIAL)


def test_partial_accepts_explicit_uncertainty() -> None:
    result = _result(
        status=GenerationPortResultStatus.PARTIAL,
        uncertainties=({"code": "SCOPE_LIMIT"},),
    )
    assert result.status is GenerationPortResultStatus.PARTIAL


def test_refused_rejects_content() -> None:
    with pytest.raises(ValueError, match="cannot contain"):
        _result(
            status=GenerationPortResultStatus.REFUSED,
            warnings=({"code": "REFUSAL"},),
        )


def test_refused_requires_explicit_limitation() -> None:
    with pytest.raises(ValueError, match="warning or uncertainty"):
        _result(
            status=GenerationPortResultStatus.REFUSED,
            content=None,
        )


def test_refused_accepts_warning_without_output() -> None:
    result = _result(
        status=GenerationPortResultStatus.REFUSED,
        content=None,
        warnings=({"code": "POLICY_REFUSAL"},),
    )
    assert not result.structured_payload


def test_insufficient_evidence_rejects_structured_payload() -> None:
    with pytest.raises(ValueError, match="cannot contain"):
        _result(
            status=GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
            content=None,
            structured_payload={"invented": True},
            warnings=({"code": "EVIDENCE_GAP"},),
        )


def test_insufficient_evidence_requires_explicit_limitation() -> None:
    with pytest.raises(ValueError, match="warning or uncertainty"):
        _result(
            status=GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
            content=None,
        )


def test_warnings_are_deeply_immutable() -> None:
    result = _result(warnings=({"detail": {"codes": ["A", "B"]}},))
    assert result.warnings[0]["detail"] == {"codes": ("A", "B")}
    with pytest.raises(TypeError):
        result.warnings[0]["detail"] = {}  # type: ignore[index]


def test_uncertainties_are_deeply_immutable() -> None:
    result = _result(uncertainties=({"basis": {"refs": ["one"]}},))
    assert result.uncertainties[0]["basis"] == {"refs": ("one",)}
    with pytest.raises(TypeError):
        result.uncertainties[0]["basis"] = {}  # type: ignore[index]


def test_execution_metadata_is_deeply_immutable() -> None:
    result = _result(execution_metadata={"technical": {"finish": ["stop"]}})
    assert result.execution_metadata["technical"] == {"finish": ("stop",)}
    with pytest.raises(TypeError):
        result.execution_metadata["technical"] = {}  # type: ignore[index]


def test_result_rejects_non_tuple_warnings_and_uncertainties() -> None:
    with pytest.raises(TypeError, match="warnings must be a tuple"):
        _result(warnings=[{"code": "ONE"}])
    with pytest.raises(TypeError, match="uncertainties must be a tuple"):
        _result(uncertainties=[{"code": "ONE"}])


def test_result_rejects_empty_source_step_id() -> None:
    with pytest.raises(ValueError, match="source_step_id"):
        _result(source_step_id=" ")


def test_result_requires_valid_evidence_ref_tuple() -> None:
    with pytest.raises(TypeError, match="evidence_refs_used must be a tuple"):
        _result(evidence_refs_used=["evidence:one"])
    with pytest.raises(TypeError, match="evidence_refs_used item"):
        _result(evidence_refs_used=(object(),))


def test_result_rejects_invalid_operation_and_status_types() -> None:
    with pytest.raises(TypeError, match="operation"):
        _result(operation="GENERATE")
    with pytest.raises(TypeError, match="status"):
        _result(status="SUCCEEDED")


def test_result_is_frozen_and_slotted() -> None:
    result = _result()
    with pytest.raises(FrozenInstanceError):
        result.content = "Changed"  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


def test_result_is_distinct_from_production_candidate() -> None:
    result = _result()
    assert not isinstance(result, ProductionCandidate)
    assert {item.name for item in fields(result)}.isdisjoint(
        {"meta", "production_id", "lineage", "validation_state"}
    )


def test_result_exposes_no_validation_promotion_or_private_provider_metadata() -> None:
    names = {item.name for item in fields(GenerationPortResult)}
    assert names.isdisjoint(
        {
            "gate_decision",
            "parent_production_ref",
            "permission_scope",
            "private_reasoning",
            "production_id",
            "provider_response",
            "promoted",
            "secret",
            "system_prompt",
            "tool_calls",
            "validated",
            "validation_state",
        }
    )


class MinimalGenerationPort:
    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        return GenerationPortResult(
            source_step_id=request.source_step_id,
            operation=request.operation,
            status=GenerationPortResultStatus.SUCCEEDED,
            content="Fake technical output.",
        )


def test_generation_port_is_runtime_checkable_with_minimal_fake() -> None:
    fake = MinimalGenerationPort()
    assert isinstance(fake, GenerationPort)
    assert fake.generate(request=_request()).source_step_id == "step-generation-1"


def test_generation_port_error_codes_are_closed_and_minimal() -> None:
    assert tuple(GenerationPortErrorCode) == (
        GenerationPortErrorCode.UNAVAILABLE,
        GenerationPortErrorCode.INVALID_RESPONSE,
    )


def test_generation_port_error_rejects_empty_safe_reason() -> None:
    with pytest.raises(ValueError, match="safe_reason"):
        GenerationPortError(GenerationPortErrorCode.UNAVAILABLE, " ")


def test_generation_port_error_rejects_invalid_code() -> None:
    with pytest.raises(TypeError, match="code"):
        GenerationPortError("UNAVAILABLE", "Temporarily unavailable")  # type: ignore[arg-type]


def test_generation_port_error_exposes_only_safe_public_reason() -> None:
    error = GenerationPortError(
        GenerationPortErrorCode.INVALID_RESPONSE,
        "Response did not match the technical contract",
    )
    assert str(error) == error.safe_reason
    assert error.code is GenerationPortErrorCode.INVALID_RESPONSE
