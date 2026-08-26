from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.review import (
    ResolvedReviewTarget,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewMaterializationError,
    ReviewMaterializationErrorCode,
    ReviewOperation,
    ReviewPortRequest,
    ReviewPortResult,
    ReviewPortResultStatus,
    ReviewPreparationRequest,
    ReviewResultMaterializationRequest,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    FindingSeverity,
    InvocationStatus,
    OverallAssessment,
    ReviewDimension,
    ReviewRequest,
    ReviewStatus,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 13, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 26, 13, 1, tzinfo=UTC))


class FixedReviewPort:
    def __init__(self, result: ReviewPortResult) -> None:
        self.result = result
        self.calls: list[ReviewPortRequest] = []

    def review(self, *, request: ReviewPortRequest) -> ReviewPortResult:
        self.calls.append(request)
        return self.result


def _target_ref() -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", "lesson-materialization")),
        VersionRef("v7"),
    )


def _canonical() -> ReviewRequest:
    return ReviewRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-review-materialization",
            step_id="step-review-materialization",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-review-materialization"),
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
        independence_requirements={"independent": True},
    )


def _finding(
    *,
    dimension: str = ReviewDimension.ACCURACY.value,
    evidence_refs: tuple[str, ...] = ("evidence:alpha",),
    correction_required: bool = False,
) -> dict[str, object]:
    return {
        "finding_id": "finding-integration-1",
        "dimension": dimension,
        "severity": FindingSeverity.MINOR.value,
        "description": "A claim needs a more precise citation.",
        "target_locator": {
            "kind": "text_span",
            "start": 0,
            "end": 5,
            "quote": "Exact",
        },
        "rationale": "The available reference supports only part of the statement.",
        "correction_required": correction_required,
        "evidence_refs": evidence_refs,
        "confidence": {"level": "medium"},
        "suggested_action": {"action": "narrow_claim"},
    }


def _technical(
    *,
    status: ReviewPortResultStatus = ReviewPortResultStatus.SUCCEEDED,
    finding: dict[str, object] | None = None,
    evidence_refs_used: tuple[str, ...] = ("evidence:alpha",),
    assessment: OverallAssessment | None = None,
    correction_required: bool = False,
) -> ReviewPortResult:
    if status in {ReviewPortResultStatus.REFUSED, ReviewPortResultStatus.FAILED}:
        return ReviewPortResult(
            source_step_id="step-review-materialization",
            operation=ReviewOperation.SEMANTIC_REVIEW,
            status=status,
            limitations=({"code": status.value},),
        )
    assessment = assessment or (
        OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS
        if status is ReviewPortResultStatus.PARTIAL
        else OverallAssessment.ACCEPTABLE
    )
    return ReviewPortResult(
        source_step_id="step-review-materialization",
        operation=ReviewOperation.SEMANTIC_REVIEW,
        status=status,
        structured_payload={
            "overall_assessment": assessment.value,
            "correction_required": correction_required,
            "coverage": (
                ReviewDimension.ACCURACY.value,
                ReviewDimension.SOURCES.value,
            ),
            "confidence": {"level": "high"},
        },
        technical_findings=(finding or _finding(),),
        evidence_refs_used=evidence_refs_used,
        limitations=(
            ({"code": "LIMITED_SCOPE"},) if status is ReviewPortResultStatus.PARTIAL else ()
        ),
        warnings=(({"code": "PARTIAL"},) if status is ReviewPortResultStatus.PARTIAL else ()),
    )


def _meta(canonical: ReviewRequest, status: ReviewStatus) -> ContractMeta[ReviewStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id=canonical.meta.run_id,
        step_id=canonical.meta.step_id,
        parent_step_id=None,
        correlation_id=canonical.meta.correlation_id,
        created_at=LATER,
        actor=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
        status=status,
    )


def _pipeline(
    technical: ReviewPortResult,
    *,
    meta_status: ReviewStatus | None = None,
):
    canonical = _canonical()
    target = ResolvedReviewTarget(
        canonical.target_production_ref,
        content="Exact caller-resolved target.",
        structured_payload={"sections": ["content", "sources"]},
    )
    port = FixedReviewPort(technical)
    agent = ReviewerAgent(ReviewCoordinator(port))
    prepared, returned = agent.semantic_review(
        request=ReviewPreparationRequest(
            CapabilityId("CAP-V01"),
            canonical,
            target,
            resolved_inputs={"authorized": "resolved"},
            output_contract={"type": "review_result"},
        )
    )
    status = meta_status or (
        ReviewStatus.INCOMPLETE
        if technical.status is ReviewPortResultStatus.PARTIAL
        else ReviewStatus.COMPLETED
    )
    build_request = ReviewResultMaterializationRequest(
        prepared=prepared,
        technical_result=returned,
        result_meta=_meta(canonical, status),
        review_id="review:integration:caller",
    )
    result = agent.build_review_result(request=build_request)
    return canonical, target, port, prepared, returned, result


def test_c09_cap_v01_to_one_port_call_to_completed_c10() -> None:
    canonical, target, port, prepared, technical, result = _pipeline(_technical())
    assert port.calls == [prepared.port_request]
    assert result.meta.status is ReviewStatus.COMPLETED
    assert result.review_id == "review:integration:caller"
    assert result.target_production_ref == canonical.target_production_ref
    assert result.findings[0].dimension is ReviewDimension.ACCURACY
    assert result.evidence_refs_used == technical.evidence_refs_used
    assert prepared.target is target


def test_partial_technical_result_materializes_incomplete_c10() -> None:
    _, _, port, prepared, technical, result = _pipeline(
        _technical(status=ReviewPortResultStatus.PARTIAL)
    )
    assert port.calls == [prepared.port_request]
    assert result.meta.status is ReviewStatus.INCOMPLETE
    assert result.overall_assessment is OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS
    assert result.limitations == technical.limitations


def test_finding_evidence_subset_is_preserved_exactly() -> None:
    _, _, _, _, _, result = _pipeline(
        _technical(
            finding=_finding(evidence_refs=("evidence:beta",)),
            evidence_refs_used=("evidence:alpha", "evidence:beta"),
        )
    )
    assert result.findings[0].evidence_refs == ("evidence:beta",)
    assert result.evidence_refs_used == ("evidence:alpha", "evidence:beta")


def test_finding_evidence_outside_c09_is_blocked_before_c10() -> None:
    with pytest.raises(ReviewMaterializationError) as raised:
        _pipeline(
            _technical(
                finding=_finding(evidence_refs=("evidence:foreign",)),
                evidence_refs_used=("evidence:alpha",),
            )
        )
    assert raised.value.code is ReviewMaterializationErrorCode.FINDING_EVIDENCE_OUT_OF_SCOPE


def test_finding_dimension_outside_request_is_blocked_before_c10() -> None:
    with pytest.raises(ReviewMaterializationError) as raised:
        _pipeline(_technical(finding=_finding(dimension=ReviewDimension.RISK.value)))
    assert raised.value.code is ReviewMaterializationErrorCode.FINDING_DIMENSION_OUT_OF_SCOPE


def test_incoherent_assessment_is_blocked_before_c10() -> None:
    with pytest.raises(ReviewMaterializationError) as raised:
        _pipeline(
            _technical(
                finding=_finding(correction_required=True),
                assessment=OverallAssessment.ACCEPTABLE,
                correction_required=True,
            )
        )
    assert raised.value.code is ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH


@pytest.mark.parametrize(
    "status",
    (ReviewPortResultStatus.REFUSED, ReviewPortResultStatus.FAILED),
)
def test_refused_and_failed_technical_results_create_no_c10(
    status: ReviewPortResultStatus,
) -> None:
    with pytest.raises(ReviewMaterializationError) as raised:
        _pipeline(_technical(status=status))
    assert raised.value.code is ReviewMaterializationErrorCode.NON_MATERIALIZABLE_STATUS


def test_versioned_target_is_preserved_without_mutation_or_c11() -> None:
    canonical, target, _, prepared, _, result = _pipeline(_technical())
    assert result.target_production_ref is canonical.target_production_ref
    assert prepared.target.target_production_ref is canonical.target_production_ref
    assert prepared.target.content == "Exact caller-resolved target."
    assert prepared.target.structured_payload == {"sections": ("content", "sources")}
    assert not hasattr(result, "correction_request")
    assert not hasattr(result, "correction_result")
    assert target == prepared.target
