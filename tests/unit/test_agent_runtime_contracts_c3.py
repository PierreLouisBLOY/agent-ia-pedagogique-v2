from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.contracts import (
    ActorKind,
    ActorRef,
    AgentResultStatus,
    ContractMeta,
    CorrectionRequest,
    CorrectionResult,
    Finding,
    FindingSeverity,
    GateRequest,
    GateStatus,
    InvocationStatus,
    OverallAssessment,
    ProductionCandidate,
    ReviewDimension,
    ReviewRequest,
    ReviewResult,
    ReviewStatus,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))


def _meta[TStatus](
    status: TStatus,
    *,
    step_id: str = "step-correction",
    correlation_id: str = "corr-1",
    run_id: str = "run-1",
) -> ContractMeta[TStatus]:
    return ContractMeta(
        schema_version="12.3-C3",
        run_id=run_id,
        step_id=step_id,
        parent_step_id=None,
        correlation_id=CorrelationId(correlation_id),
        created_at=NOW,
        actor=ActorRef(ActorKind.AGENT, "AG-03"),
        status=status,
    )


def _production_identity(production_id: str = "production-1") -> TypedEntityRef:
    return TypedEntityRef(TypedEntityId("production", production_id))


def _production_version(
    version: str = "v1",
    production_id: str = "production-1",
) -> ObjectVersionRef:
    return ObjectVersionRef(
        object_ref=_production_identity(production_id),
        version_ref=VersionRef(version),
    )


def _finding(
    *,
    finding_id: str = "finding-1",
    dimension: ReviewDimension = ReviewDimension.ACCURACY,
    correction_required: bool = True,
) -> Finding:
    return Finding(
        finding_id=finding_id,
        dimension=dimension,
        severity=FindingSeverity.MAJOR,
        description="A public criterion is unmet",
        target_locator={"section": "intro"},
        rationale="The cited source does not support the claim.",
        correction_required=correction_required,
    )


def _correction_request(
    *,
    target: ObjectVersionRef | None = None,
    finding_ids: tuple[str, ...] = ("finding-1", "finding-2"),
) -> CorrectionRequest:
    return CorrectionRequest(
        meta=_meta(InvocationStatus.PLANNED),
        target_production_ref=target or _production_version(),
        review_ref="review-1",
        finding_ids=finding_ids,
    )


@pytest.mark.parametrize(
    "invalid_target",
    ["production-1", _production_identity()],
)
def test_review_and_correction_contracts_require_exact_version_targets(
    invalid_target: object,
) -> None:
    with pytest.raises(TypeError):
        ReviewRequest(
            meta=_meta(InvocationStatus.PLANNED),
            target_production_ref=invalid_target,  # type: ignore[arg-type]
            review_dimensions=(ReviewDimension.ACCURACY,),
        )
    with pytest.raises(TypeError):
        ReviewResult(
            meta=_meta(ReviewStatus.COMPLETED),
            review_id="review-1",
            target_production_ref=invalid_target,  # type: ignore[arg-type]
            findings=(),
            overall_assessment=OverallAssessment.ACCEPTABLE,
            correction_required=False,
            coverage=(ReviewDimension.ACCURACY,),
            evidence_refs_used=(),
        )
    with pytest.raises(TypeError):
        CorrectionRequest(
            meta=_meta(InvocationStatus.PLANNED),
            target_production_ref=invalid_target,  # type: ignore[arg-type]
            review_ref="review-1",
            finding_ids=("finding-1",),
        )


def test_completed_review_requires_coverage() -> None:
    with pytest.raises(ValueError):
        ReviewResult(
            meta=_meta(ReviewStatus.COMPLETED),
            review_id="review-1",
            target_production_ref=_production_version(),
            findings=(),
            overall_assessment=OverallAssessment.ACCEPTABLE,
            correction_required=False,
            coverage=(),
            evidence_refs_used=(),
        )


def test_review_finding_dimension_must_be_covered() -> None:
    with pytest.raises(ValueError):
        ReviewResult(
            meta=_meta(ReviewStatus.COMPLETED),
            review_id="review-1",
            target_production_ref=_production_version(),
            findings=(_finding(dimension=ReviewDimension.SOURCES),),
            overall_assessment=OverallAssessment.CORRECTION_REQUIRED,
            correction_required=True,
            coverage=(ReviewDimension.ACCURACY,),
            evidence_refs_used=(),
        )


def test_finding_correction_requirement_must_be_reflected_by_review() -> None:
    with pytest.raises(ValueError):
        ReviewResult(
            meta=_meta(ReviewStatus.COMPLETED),
            review_id="review-1",
            target_production_ref=_production_version(),
            findings=(_finding(),),
            overall_assessment=OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS,
            correction_required=False,
            coverage=(ReviewDimension.ACCURACY,),
            evidence_refs_used=(),
        )


def test_correction_required_assessment_requires_aggregate_flag() -> None:
    with pytest.raises(ValueError):
        ReviewResult(
            meta=_meta(ReviewStatus.COMPLETED),
            review_id="review-1",
            target_production_ref=_production_version(),
            findings=(),
            overall_assessment=OverallAssessment.CORRECTION_REQUIRED,
            correction_required=False,
            coverage=(ReviewDimension.ACCURACY,),
            evidence_refs_used=(),
        )


def test_acceptable_assessment_rejects_correction_finding() -> None:
    with pytest.raises(ValueError):
        ReviewResult(
            meta=_meta(ReviewStatus.COMPLETED),
            review_id="review-1",
            target_production_ref=_production_version(),
            findings=(_finding(),),
            overall_assessment=OverallAssessment.ACCEPTABLE,
            correction_required=True,
            coverage=(ReviewDimension.ACCURACY,),
            evidence_refs_used=(),
        )


def test_incomplete_review_cannot_be_acceptable() -> None:
    with pytest.raises(ValueError):
        ReviewResult(
            meta=_meta(ReviewStatus.INCOMPLETE),
            review_id="review-1",
            target_production_ref=_production_version(),
            findings=(),
            overall_assessment=OverallAssessment.ACCEPTABLE,
            correction_required=False,
            coverage=(),
            evidence_refs_used=(),
        )


@pytest.mark.parametrize(
    ("status", "assessment", "coverage"),
    [
        (ReviewStatus.INCOMPLETE, OverallAssessment.INCOMPLETE, ()),
        (
            ReviewStatus.COMPLETED,
            OverallAssessment.ACCEPTABLE,
            (ReviewDimension.ACCURACY,),
        ),
    ],
)
def test_review_status_and_assessment_allow_non_contradictory_pairs(
    status: ReviewStatus,
    assessment: OverallAssessment,
    coverage: tuple[ReviewDimension, ...],
) -> None:
    result = ReviewResult(
        meta=_meta(status),
        review_id="review-1",
        target_production_ref=_production_version(),
        findings=(),
        overall_assessment=assessment,
        correction_required=False,
        coverage=coverage,
        evidence_refs_used=(),
    )

    assert result.overall_assessment is assessment


def test_correction_request_requires_finding_ids() -> None:
    with pytest.raises(ValueError):
        _correction_request(finding_ids=())


def test_correction_result_records_complete_immutable_delta() -> None:
    request = _correction_request()
    result = CorrectionResult(
        meta=_meta(AgentResultStatus.SUCCEEDED),
        request=request,
        new_production_ref=_production_version("v2"),
        parent_production_ref=request.target_production_ref,
        addressed_findings=("finding-1",),
        unresolved_findings=("finding-2",),
        change_summary="Corrected the unsupported claim.",
        lineage={
            "parent_production_ref": request.target_production_ref,
            "new_production_ref": _production_version("v2"),
        },
        new_warnings=({"code": "FINDING_REMAINS"},),
    )

    assert result.parent_production_ref == request.target_production_ref
    assert result.new_production_ref != result.parent_production_ref
    with pytest.raises(FrozenInstanceError):
        result.change_summary = "Changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.lineage["status"] = "validated"  # type: ignore[index]


def test_correction_result_rejects_incoherent_parent_and_new_version() -> None:
    request = _correction_request()
    with pytest.raises(ValueError):
        CorrectionResult(
            meta=_meta(AgentResultStatus.SUCCEEDED),
            request=request,
            new_production_ref=_production_version("v2"),
            parent_production_ref=_production_version("v1", "other-production"),
            addressed_findings=request.finding_ids,
            unresolved_findings=(),
            change_summary="Changed",
            lineage={},
        )
    with pytest.raises(ValueError):
        CorrectionResult(
            meta=_meta(AgentResultStatus.SUCCEEDED),
            request=request,
            new_production_ref=request.target_production_ref,
            parent_production_ref=request.target_production_ref,
            addressed_findings=request.finding_ids,
            unresolved_findings=(),
            change_summary="Changed",
            lineage={},
        )


def test_correction_result_rejects_new_version_for_another_production() -> None:
    request = _correction_request()
    with pytest.raises(ValueError):
        CorrectionResult(
            meta=_meta(AgentResultStatus.SUCCEEDED),
            request=request,
            new_production_ref=_production_version("v2", "other-production"),
            parent_production_ref=request.target_production_ref,
            addressed_findings=request.finding_ids,
            unresolved_findings=(),
            change_summary="Changed",
            lineage={},
        )


@pytest.mark.parametrize(
    ("addressed", "unresolved"),
    [
        (("finding-1",), ()),
        (("finding-1",), ("finding-1", "finding-2")),
        (("finding-1", "finding-1"), ("finding-2",)),
    ],
)
def test_correction_result_requires_exact_finding_partition(
    addressed: tuple[str, ...],
    unresolved: tuple[str, ...],
) -> None:
    request = _correction_request()
    with pytest.raises(ValueError):
        CorrectionResult(
            meta=_meta(AgentResultStatus.SUCCEEDED),
            request=request,
            new_production_ref=_production_version("v2"),
            parent_production_ref=request.target_production_ref,
            addressed_findings=addressed,
            unresolved_findings=unresolved,
            change_summary="Changed",
            lineage={},
        )


@pytest.mark.parametrize(
    "meta",
    [
        _meta(AgentResultStatus.SUCCEEDED, step_id="other-step"),
        _meta(AgentResultStatus.SUCCEEDED, correlation_id="other-correlation"),
    ],
)
def test_correction_result_requires_request_correlation(
    meta: ContractMeta[AgentResultStatus],
) -> None:
    request = _correction_request()
    with pytest.raises(ValueError):
        CorrectionResult(
            meta=meta,
            request=request,
            new_production_ref=_production_version("v2"),
            parent_production_ref=request.target_production_ref,
            addressed_findings=request.finding_ids,
            unresolved_findings=(),
            change_summary="Changed",
            lineage={},
        )


def test_correction_result_requires_request_run_id() -> None:
    request = _correction_request()
    with pytest.raises(ValueError):
        CorrectionResult(
            meta=_meta(AgentResultStatus.SUCCEEDED, run_id="other-run"),
            request=request,
            new_production_ref=_production_version("v2"),
            parent_production_ref=request.target_production_ref,
            addressed_findings=request.finding_ids,
            unresolved_findings=(),
            change_summary="Changed",
            lineage={},
        )


def test_production_candidate_validates_lineage_refs_when_present() -> None:
    candidate = ProductionCandidate(
        meta=_meta(AgentResultStatus.SUCCEEDED),
        production_id="production-2",
        production_kind="lesson",
        content="Draft",
        lineage={"parent_production_ref": _production_version()},
    )
    assert candidate.lineage["parent_production_ref"] == _production_version()

    ProductionCandidate(
        meta=_meta(AgentResultStatus.SUCCEEDED),
        production_id="production-new",
        production_kind="lesson",
        content="New draft",
    )
    with pytest.raises(TypeError):
        ProductionCandidate(
            meta=_meta(AgentResultStatus.SUCCEEDED),
            production_id="production-3",
            production_kind="lesson",
            content="Draft",
            lineage={"target_ref": {"value": "not-a-ref"}},
        )


@pytest.mark.parametrize(
    "expires_at",
    [
        NOW,
        Instant(datetime(2026, 8, 24, 11, 59, tzinfo=UTC)),
    ],
)
def test_gate_request_expiration_must_follow_creation(expires_at: Instant) -> None:
    with pytest.raises(ValueError):
        GateRequest(
            meta=_meta(GateStatus.PENDING),
            gate_id="gate-1",
            gate_type="approval",
            reason="Authority required",
            options=(),
            required_actor=ActorRef(ActorKind.USER, "user-1"),
            expires_at=expires_at,
        )
