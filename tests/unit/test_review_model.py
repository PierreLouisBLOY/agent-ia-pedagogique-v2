from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from backend.agent_runtime.agents.review import (
    ReviewOperation,
    ReviewPort,
    ReviewPortError,
    ReviewPortErrorCode,
    ReviewPortRequest,
    ReviewPortResult,
    ReviewPortResultStatus,
)
from backend.agent_runtime.contracts import BudgetSpec, ReviewDimension
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from tests.support.review_fakes import RecordingReviewPort


def _target_ref() -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", "lesson-1")),
        VersionRef("v3"),
    )


def _request(**changes: object) -> ReviewPortRequest:
    values: dict[str, object] = {
        "source_step_id": "step-review-1",
        "operation": ReviewOperation.SEMANTIC_REVIEW,
        "capability_id": CapabilityId("CAP-V01"),
        "target_production_ref": _target_ref(),
        "target_content": "Caller-resolved lesson content.",
        "review_dimensions": (ReviewDimension.ACCURACY, ReviewDimension.SOURCES),
        "criteria": {"required": ["traceable"]},
        "evidence_refs": ("evidence:one",),
        "coverage_context": {"requested": ["full"]},
        "resolved_inputs": {"locale": "fr-FR"},
        "output_contract": {"format": "structured_review"},
        "review_budget": BudgetSpec(max_tokens=1000),
    }
    values.update(changes)
    return ReviewPortRequest(**values)  # type: ignore[arg-type]


def _result(**changes: object) -> ReviewPortResult:
    values: dict[str, object] = {
        "source_step_id": "step-review-1",
        "operation": ReviewOperation.SEMANTIC_REVIEW,
        "status": ReviewPortResultStatus.SUCCEEDED,
        "structured_payload": {"assessment": "technical-only"},
        "technical_findings": (
            {"finding_key": "f-1", "dimension": "REV-ACC"},
        ),
        "evidence_refs_used": ("evidence:one",),
        "execution_metadata": {"finish_reason": "stop"},
    }
    values.update(changes)
    return ReviewPortResult(**values)  # type: ignore[arg-type]


def test_review_operation_is_closed_and_matches_the_two_technical_operations() -> None:
    assert tuple(ReviewOperation) == (
        ReviewOperation.SEMANTIC_REVIEW,
        ReviewOperation.ASSESS_FINDINGS,
    )
    assert {item.name for item in ReviewOperation}.isdisjoint(
        {"PASS", "FAIL", "VALIDATE", "PROMOTE", "SEARCH", "CORRECT"}
    )


def test_semantic_review_request_is_nominal_and_caller_resolved() -> None:
    request = _request()
    assert request.operation is ReviewOperation.SEMANTIC_REVIEW
    assert request.capability_id == CapabilityId("CAP-V01")
    assert request.target_production_ref == _target_ref()
    assert request.review_budget == BudgetSpec(max_tokens=1000)


def test_assess_findings_request_is_nominal_without_capability_dispatch() -> None:
    request = _request(
        operation=ReviewOperation.ASSESS_FINDINGS,
        capability_id=CapabilityId("CAP-V02"),
        resolved_inputs={"finding_ids": ["f-1", "f-2"]},
    )
    assert request.operation is ReviewOperation.ASSESS_FINDINGS
    assert request.resolved_inputs == {"finding_ids": ("f-1", "f-2")}


def test_request_requires_an_exact_target_and_resolved_representation() -> None:
    with pytest.raises(TypeError, match="ObjectVersionRef"):
        _request(target_production_ref="production:v3")
    with pytest.raises(ValueError, match="target_content or target_payload"):
        _request(target_content=None, target_payload={})
    with pytest.raises(ValueError, match="target_content"):
        _request(target_content=" ")
    request = _request(target_content=None, target_payload={"sections": ["intro"]})
    assert request.target_payload == {"sections": ("intro",)}


def test_request_dimensions_are_typed_unique_and_immutable() -> None:
    request = _request()
    assert request.review_dimensions == (
        ReviewDimension.ACCURACY,
        ReviewDimension.SOURCES,
    )
    with pytest.raises(TypeError, match="must be a tuple"):
        _request(review_dimensions=[ReviewDimension.ACCURACY])
    with pytest.raises(ValueError, match="must not be empty"):
        _request(review_dimensions=())
    with pytest.raises(TypeError, match="ReviewDimension"):
        _request(review_dimensions=("REV-ACC",))
    with pytest.raises(ValueError, match="unique"):
        _request(
            review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.ACCURACY)
        )


def test_request_refs_and_structured_inputs_are_deeply_immutable() -> None:
    request = _request(
        evidence_refs=("evidence:one", "evidence:two"),
        criteria={"rules": ["one"]},
        coverage_context={"limits": {"sections": ["intro"]}},
        resolved_inputs={"facts": [{"id": "one"}]},
        output_contract={"required": ["technical_findings"]},
    )
    assert request.evidence_refs == ("evidence:one", "evidence:two")
    assert request.criteria == {"rules": ("one",)}
    assert request.coverage_context == {"limits": {"sections": ("intro",)}}
    assert request.resolved_inputs == {"facts": ({"id": "one"},)}
    assert request.output_contract == {"required": ("technical_findings",)}
    with pytest.raises(TypeError):
        request.resolved_inputs["facts"] = ()  # type: ignore[index]


def test_request_rejects_invalid_types_empty_step_and_duplicate_refs() -> None:
    with pytest.raises(ValueError, match="source_step_id"):
        _request(source_step_id=" ")
    with pytest.raises(TypeError, match="operation"):
        _request(operation="SEMANTIC_REVIEW")
    with pytest.raises(TypeError, match="capability_id"):
        _request(capability_id="CAP-V01")
    with pytest.raises(TypeError, match="evidence_refs must be a tuple"):
        _request(evidence_refs=["evidence:one"])
    with pytest.raises(ValueError, match="unique"):
        _request(evidence_refs=("evidence:one", "evidence:one"))
    with pytest.raises(TypeError, match="review_budget"):
        _request(review_budget={"max_tokens": 1000})


def test_request_output_contract_rejects_authority_and_private_data() -> None:
    with pytest.raises(ValueError, match="authority vocabulary"):
        _request(output_contract={"reviewPassed": True})
    with pytest.raises(ValueError, match="forbidden agent runtime data key"):
        _request(output_contract={"chain_of_thought": "hidden"})


def test_request_is_frozen_and_slotted() -> None:
    request = _request()
    with pytest.raises(FrozenInstanceError):
        request.source_step_id = "changed"  # type: ignore[misc]
    assert not hasattr(request, "__dict__")


def test_result_is_nominal_non_canonical_and_deeply_immutable() -> None:
    result = _result(
        limitations=({"code": "LIMIT"},),
        warnings=({"detail": {"codes": ["W1"]}},),
        uncertainties=({"basis": ["provider"]},),
    )
    assert result.structured_payload == {"assessment": "technical-only"}
    assert result.technical_findings[0] == {
        "finding_key": "f-1",
        "dimension": "REV-ACC",
    }
    assert result.warnings[0] == {"detail": {"codes": ("W1",)}}
    with pytest.raises(TypeError):
        result.execution_metadata["finish_reason"] = "changed"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        result.status = ReviewPortResultStatus.PARTIAL  # type: ignore[misc]
    assert not hasattr(result, "__dict__")


def test_result_status_is_closed_and_contains_no_business_pass_fail() -> None:
    assert tuple(ReviewPortResultStatus) == (
        ReviewPortResultStatus.SUCCEEDED,
        ReviewPortResultStatus.PARTIAL,
        ReviewPortResultStatus.REFUSED,
        ReviewPortResultStatus.FAILED,
    )
    assert {item.name for item in ReviewPortResultStatus}.isdisjoint(
        {"PASS", "VALIDATED", "APPROVED", "PROMOTED", "CANONICAL"}
    )


def test_result_status_invariants_are_technical_only() -> None:
    with pytest.raises(ValueError, match="SUCCEEDED requires"):
        _result(structured_payload={}, technical_findings=())
    with pytest.raises(ValueError, match="PARTIAL requires structured"):
        _result(
            status=ReviewPortResultStatus.PARTIAL,
            structured_payload={},
            technical_findings=(),
            limitations=({"code": "LIMIT"},),
        )
    with pytest.raises(ValueError, match="PARTIAL requires a limitation"):
        _result(status=ReviewPortResultStatus.PARTIAL)
    for status in (ReviewPortResultStatus.REFUSED, ReviewPortResultStatus.FAILED):
        with pytest.raises(ValueError, match="cannot contain"):
            _result(status=status, limitations=({"code": "STOP"},))
        result = _result(
            status=status,
            structured_payload={},
            technical_findings=(),
            limitations=({"code": "STOP"},),
        )
        assert result.status is status


def test_result_validates_source_operation_status_and_evidence_refs() -> None:
    with pytest.raises(ValueError, match="source_step_id"):
        _result(source_step_id=" ")
    with pytest.raises(TypeError, match="operation"):
        _result(operation="SEMANTIC_REVIEW")
    with pytest.raises(TypeError, match="status"):
        _result(status="SUCCEEDED")
    with pytest.raises(TypeError, match="evidence_refs_used must be a tuple"):
        _result(evidence_refs_used=["evidence:one"])
    with pytest.raises(ValueError, match="unique"):
        _result(evidence_refs_used=("evidence:one", "evidence:one"))


def test_result_mapping_tuples_require_tuples_and_safe_values() -> None:
    with pytest.raises(TypeError, match="warnings must be a tuple"):
        _result(warnings=[{"code": "W1"}])
    with pytest.raises(ValueError, match="forbidden agent runtime data key"):
        _result(technical_findings=({"private_reasoning": "hidden"},))
    with pytest.raises(ValueError, match="forbidden structured data key"):
        _result(execution_metadata={"database": {"sql": "select 1"}})


@pytest.mark.parametrize(
    "field_name, field_value",
    (
        ("structured_payload", {"validated": True}),
        ("technical_findings", ({"gateApproved": True},)),
        ("limitations", ({"permission-granted": True},)),
        ("warnings", ({"trusted": True},)),
        ("uncertainties", ({"review passed": True},)),
        ("execution_metadata", {"canonical": True}),
    ),
)
def test_result_rejects_authority_vocabulary_recursively(
    field_name: str,
    field_value: object,
) -> None:
    with pytest.raises(ValueError, match="authority vocabulary"):
        _result(**{field_name: field_value})


def test_result_exposes_no_canonical_review_or_promotion_fields() -> None:
    names = {item.name for item in fields(ReviewPortResult)}
    assert names.isdisjoint(
        {
            "canonical",
            "correction_request",
            "finding",
            "gate_approved",
            "overall_assessment",
            "permission_granted",
            "promoted",
            "review_passed",
            "review_result",
            "safe",
            "trusted",
            "validated",
        }
    )


def test_review_port_error_codes_and_messages_are_closed() -> None:
    assert tuple(ReviewPortErrorCode) == (
        ReviewPortErrorCode.UNAVAILABLE,
        ReviewPortErrorCode.INVALID_RESPONSE,
        ReviewPortErrorCode.REQUEST_REJECTED,
    )
    error = ReviewPortError(ReviewPortErrorCode.INVALID_RESPONSE)
    assert str(error) == error.safe_reason
    assert "lesson" not in error.safe_reason.casefold()
    assert "evidence" not in error.safe_reason.casefold()
    with pytest.raises(TypeError, match="code"):
        ReviewPortError("INVALID_RESPONSE")


def test_review_port_is_runtime_checkable_with_one_method() -> None:
    result = _result()
    port = RecordingReviewPort(result=result)
    assert isinstance(port, ReviewPort)
    assert port.review(request=_request()) is result


def test_recording_fake_records_once_and_returns_configured_result() -> None:
    request = _request()
    result = _result()
    port = RecordingReviewPort(result=result)
    assert port.review(request=request) is result
    assert port.calls == [request]


def test_recording_fake_propagates_configured_error_without_retry() -> None:
    request = _request()
    error = ReviewPortError(ReviewPortErrorCode.UNAVAILABLE)
    port = RecordingReviewPort(error=error)
    with pytest.raises(ReviewPortError) as raised:
        port.review(request=request)
    assert raised.value is error
    assert port.calls == [request]


def test_recording_fake_configuration_is_explicit() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        RecordingReviewPort(result=_result(), error=ReviewPortError(ReviewPortErrorCode.UNAVAILABLE))
    with pytest.raises(AssertionError, match="no test review result"):
        RecordingReviewPort().review(request=_request())
