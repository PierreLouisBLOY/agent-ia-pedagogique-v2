from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.review import (
    ResolvedReviewTarget,
    ReviewCoordinationError,
    ReviewCoordinationErrorCode,
    ReviewCoordinator,
    ReviewOperation,
    ReviewPortError,
    ReviewPortErrorCode,
    ReviewPortResult,
    ReviewPortResultStatus,
    ReviewPreparationRequest,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    InvocationStatus,
    ReviewDimension,
    ReviewRequest,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant
from tests.support.review_fakes import RecordingReviewPort

NOW = Instant(datetime(2026, 8, 26, 11, 0, tzinfo=UTC))


def _target_ref() -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", "lesson-integration")),
        VersionRef("v4"),
    )


def _request() -> ReviewRequest:
    return ReviewRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-integration-review",
            step_id="step-integration-review",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-integration-review"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
            status=InvocationStatus.PLANNED,
        ),
        target_production_ref=_target_ref(),
        review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.SOURCES),
        criteria={"required": ["grounded", "traceable"]},
        evidence_refs=("evidence:alpha", "evidence:beta"),
        severity_policy={"major": ["unsupported_claim"]},
        context_slice={"sections": ["content", "sources"]},
        independence_requirements={"separate_from_generation": True},
    )


def _result(
    operation: ReviewOperation,
    *,
    step_id: str = "step-integration-review",
    evidence_refs_used: tuple[str, ...] = ("evidence:alpha",),
) -> ReviewPortResult:
    return ReviewPortResult(
        source_step_id=step_id,
        operation=operation,
        status=ReviewPortResultStatus.SUCCEEDED,
        structured_payload={"coverage": ["REV-ACC", "REV-SRC"]},
        technical_findings=({"finding_key": "technical-1"},),
        evidence_refs_used=evidence_refs_used,
    )


def _execute(
    capability: str,
    result: ReviewPortResult,
) -> tuple[ReviewPortResult, RecordingReviewPort, object]:
    canonical = _request()
    port = RecordingReviewPort(result=result)
    coordinator = ReviewCoordinator(port)
    prepared = coordinator.prepare(
        request=ReviewPreparationRequest(
            capability_id=CapabilityId(capability),
            request=canonical,
            target=ResolvedReviewTarget(
                canonical.target_production_ref,
                content="Caller-resolved content.",
                structured_payload={"sections": ["content", "sources"]},
            ),
            resolved_inputs={"finding_candidates": [{"id": "f-1"}]},
            output_contract={"type": "technical_review"},
        )
    )
    returned = coordinator.execute(prepared=prepared)
    return returned, port, prepared


@pytest.mark.parametrize(
    ("capability", "operation"),
    (
        ("CAP-V01", ReviewOperation.SEMANTIC_REVIEW),
        ("CAP-V02", ReviewOperation.ASSESS_FINDINGS),
    ),
)
def test_review_crosses_boundary_once_with_exact_prepared_lineage(
    capability: str,
    operation: ReviewOperation,
) -> None:
    expected = _result(operation)
    returned, port, prepared = _execute(capability, expected)
    technical = prepared.port_request  # type: ignore[attr-defined]
    assert returned is expected
    assert port.calls == [technical]
    assert technical.operation is operation
    assert technical.source_step_id == "step-integration-review"
    assert technical.target_production_ref == _target_ref()
    assert technical.target_content == "Caller-resolved content."
    assert technical.coverage_context == {
        "severity_policy": {"major": ("unsupported_claim",)},
        "context_slice": {"sections": ("content", "sources")},
        "independence_requirements": {"separate_from_generation": True},
    }
    assert technical.resolved_inputs == {"finding_candidates": ({"id": "f-1"},)}


def test_evidence_subset_returns_technical_result_without_materialization() -> None:
    returned, port, prepared = _execute(
        "CAP-V01",
        _result(ReviewOperation.SEMANTIC_REVIEW, evidence_refs_used=("evidence:beta",)),
    )
    assert returned.evidence_refs_used == ("evidence:beta",)
    assert len(port.calls) == 1
    assert prepared.port_request.evidence_refs == (  # type: ignore[attr-defined]
        "evidence:alpha",
        "evidence:beta",
    )
    result_fields = {item.name for item in fields(returned)}
    assert result_fields.isdisjoint(
        {"meta", "review_id", "findings", "overall_assessment", "correction_required"}
    )


def test_foreign_evidence_is_rejected_after_one_boundary_call() -> None:
    canonical = _request()
    result = _result(
        ReviewOperation.SEMANTIC_REVIEW,
        evidence_refs_used=("evidence:foreign",),
    )
    port = RecordingReviewPort(result=result)
    coordinator = ReviewCoordinator(port)
    prepared = coordinator.prepare(
        request=ReviewPreparationRequest(
            CapabilityId("CAP-V01"),
            canonical,
            ResolvedReviewTarget(canonical.target_production_ref, content="Resolved."),
        )
    )
    with pytest.raises(ReviewCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is ReviewCoordinationErrorCode.EVIDENCE_REF_OUT_OF_SCOPE
    assert port.calls == [prepared.port_request]


@pytest.mark.parametrize(
    ("result", "code"),
    (
        (
            _result(ReviewOperation.SEMANTIC_REVIEW, step_id="foreign-step"),
            ReviewCoordinationErrorCode.SOURCE_STEP_MISMATCH,
        ),
        (
            _result(ReviewOperation.ASSESS_FINDINGS),
            ReviewCoordinationErrorCode.OPERATION_MISMATCH,
        ),
    ),
)
def test_result_lineage_mismatch_is_rejected_after_one_boundary_call(
    result: ReviewPortResult,
    code: ReviewCoordinationErrorCode,
) -> None:
    canonical = _request()
    port = RecordingReviewPort(result=result)
    coordinator = ReviewCoordinator(port)
    prepared = coordinator.prepare(
        request=ReviewPreparationRequest(
            CapabilityId("CAP-V01"),
            canonical,
            ResolvedReviewTarget(canonical.target_production_ref, content="Resolved."),
        )
    )
    with pytest.raises(ReviewCoordinationError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value.code is code
    assert port.calls == [prepared.port_request]


def test_technical_error_propagates_without_retry_or_translation() -> None:
    canonical = _request()
    error = ReviewPortError(ReviewPortErrorCode.UNAVAILABLE)
    port = RecordingReviewPort(error=error)
    coordinator = ReviewCoordinator(port)
    prepared = coordinator.prepare(
        request=ReviewPreparationRequest(
            CapabilityId("CAP-V01"),
            canonical,
            ResolvedReviewTarget(canonical.target_production_ref, content="Resolved."),
        )
    )
    with pytest.raises(ReviewPortError) as raised:
        coordinator.execute(prepared=prepared)
    assert raised.value is error
    assert port.calls == [prepared.port_request]
