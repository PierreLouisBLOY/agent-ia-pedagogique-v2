from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.review import (
    FindingsAssessmentRequest,
    ResolvedReviewTarget,
    ReviewAssessmentError,
    ReviewAssessmentErrorCode,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewOperation,
    ReviewPortRequest,
    ReviewPortResult,
    ReviewPortResultStatus,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    Finding,
    FindingSeverity,
    InvocationStatus,
    OverallAssessment,
    ReviewDimension,
    ReviewRequest,
    ReviewResult,
    ReviewStatus,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 15, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 26, 15, 1, tzinfo=UTC))


class FixedAssessmentPort:
    def __init__(self, result: ReviewPortResult) -> None:
        self.result = result
        self.calls: list[ReviewPortRequest] = []

    def review(self, *, request: ReviewPortRequest) -> ReviewPortResult:
        self.calls.append(request)
        return self.result


def _target_ref() -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", "assessment-integration")),
        VersionRef("v9"),
    )


def _canonical() -> ReviewRequest:
    return ReviewRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-assessment-integration",
            step_id="step-assessment-integration",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-assessment-integration"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
            status=InvocationStatus.PLANNED,
        ),
        target_production_ref=_target_ref(),
        review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.RISK),
        criteria={"required": ["safe", "grounded"]},
        evidence_refs=("evidence:alpha", "evidence:beta"),
        severity_policy={"blocking": ["unsafe"]},
        context_slice={"sections": ["content"]},
        independence_requirements={"independent": True},
    )


def _finding(
    finding_id: str,
    *,
    severity: FindingSeverity,
    correction_required: bool,
    evidence_refs: tuple[str, ...],
) -> Finding:
    return Finding(
        finding_id=finding_id,
        dimension=(
            ReviewDimension.RISK
            if severity is FindingSeverity.BLOCKING
            else ReviewDimension.ACCURACY
        ),
        severity=severity,
        description="Public issue.",
        target_locator={"section": "content"},
        rationale="Public rationale.",
        correction_required=correction_required,
        evidence_refs=evidence_refs,
        confidence={"level": "high"},
        suggested_action={"action": "revise"},
    )


def _source(
    canonical: ReviewRequest,
    *,
    findings: tuple[Finding, ...] = (),
    assessment: OverallAssessment = OverallAssessment.ACCEPTABLE,
    correction_required: bool = False,
) -> ReviewResult:
    return ReviewResult(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id=canonical.meta.run_id,
            step_id=canonical.meta.step_id,
            parent_step_id=None,
            correlation_id=canonical.meta.correlation_id,
            created_at=LATER,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
            status=ReviewStatus.COMPLETED,
        ),
        review_id="review:integration:source",
        target_production_ref=canonical.target_production_ref,
        findings=findings,
        overall_assessment=assessment,
        correction_required=correction_required,
        coverage=canonical.review_dimensions,
        evidence_refs_used=("evidence:alpha", "evidence:beta"),
        confidence={"level": "high"},
    )


def _technical(
    source: ReviewResult,
    *,
    status: ReviewPortResultStatus = ReviewPortResultStatus.SUCCEEDED,
    assessed_ids: tuple[str, ...] | None = None,
    blocking_ids: tuple[str, ...] | None = None,
) -> ReviewPortResult:
    all_ids = tuple(item.finding_id for item in source.findings)
    blocking = tuple(
        item.finding_id
        for item in source.findings
        if item.severity is FindingSeverity.BLOCKING
    )
    correction = tuple(
        item.finding_id
        for item in source.findings
        if item.correction_required or item.severity is FindingSeverity.BLOCKING
    )
    assessment = (
        OverallAssessment.INCOMPLETE
        if status is ReviewPortResultStatus.PARTIAL
        else source.overall_assessment
    )
    return ReviewPortResult(
        source_step_id="step-assessment-integration",
        operation=ReviewOperation.ASSESS_FINDINGS,
        status=status,
        structured_payload={
            "assessed_finding_ids": all_ids if assessed_ids is None else assessed_ids,
            "blocking_finding_ids": blocking if blocking_ids is None else blocking_ids,
            "correction_finding_ids": correction,
            "overall_assessment": assessment.value,
            "correction_required": bool(correction),
            "confidence": {"level": "high"},
        },
        evidence_refs_used=("evidence:alpha",),
        limitations=(
            ({"code": "PARTIAL_SCOPE"},)
            if status is ReviewPortResultStatus.PARTIAL
            else ()
        ),
    )


def _pipeline(source: ReviewResult, technical: ReviewPortResult):
    canonical = _canonical()
    assert source.target_production_ref == canonical.target_production_ref
    target = ResolvedReviewTarget(
        canonical.target_production_ref,
        content="Exact target content.",
        structured_payload={"sections": ["content"]},
    )
    port = FixedAssessmentPort(technical)
    agent = ReviewerAgent(ReviewCoordinator(port))
    signal, handoff = agent.assess_findings(
        request=FindingsAssessmentRequest(
            capability_id=CapabilityId("CAP-V02"),
            source_request=canonical,
            source_result=source,
            target=target,
            review_ref="review-ref:integration",
            resolved_inputs={"locale": "fr-FR"},
        )
    )
    return canonical, target, port, signal, handoff


def test_acceptable_c10_without_findings_emits_nonblocking_signal() -> None:
    canonical = _canonical()
    source = _source(canonical)
    _, _, port, signal, handoff = _pipeline(source, _technical(source))
    assert len(port.calls) == 1
    assert signal.overall_assessment is OverallAssessment.ACCEPTABLE
    assert signal.assessed_finding_ids == ()
    assert signal.promotion_blocked_by_review is False
    assert handoff is None


def test_reservations_without_correction_emit_no_handoff() -> None:
    canonical = _canonical()
    source = _source(
        canonical,
        findings=(
            _finding(
                "minor-1",
                severity=FindingSeverity.MINOR,
                correction_required=False,
                evidence_refs=("evidence:alpha",),
            ),
        ),
        assessment=OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS,
    )
    _, _, _, signal, handoff = _pipeline(source, _technical(source))
    assert signal.correction_required is False
    assert signal.correction_finding_ids == ()
    assert handoff is None


def test_major_explicit_correction_emits_ag01_handoff() -> None:
    canonical = _canonical()
    source = _source(
        canonical,
        findings=(
            _finding(
                "major-1",
                severity=FindingSeverity.MAJOR,
                correction_required=True,
                evidence_refs=("evidence:beta",),
            ),
        ),
        assessment=OverallAssessment.CORRECTION_REQUIRED,
        correction_required=True,
    )
    _, _, _, signal, handoff = _pipeline(source, _technical(source))
    assert signal.correction_finding_ids == ("major-1",)
    assert signal.promotion_blocked_by_review is False
    assert handoff is not None
    assert handoff.destination_agent_id is AgentId.AG_01
    assert handoff.evidence_refs == ("evidence:beta",)


def test_blocking_emits_promotion_blocked_signal_and_exact_handoff() -> None:
    canonical = _canonical()
    source = _source(
        canonical,
        findings=(
            _finding(
                "blocking-1",
                severity=FindingSeverity.BLOCKING,
                correction_required=False,
                evidence_refs=("evidence:alpha", "evidence:beta"),
            ),
        ),
        assessment=OverallAssessment.UNUSABLE,
        correction_required=True,
    )
    _, _, port, signal, handoff = _pipeline(source, _technical(source))
    assert len(port.calls) == 1
    assert signal.blocking_finding_ids == ("blocking-1",)
    assert signal.promotion_blocked_by_review is True
    assert handoff is not None
    assert handoff.finding_ids == ("blocking-1",)
    assert handoff.blocking_finding_ids == ("blocking-1",)


def test_provider_cannot_remove_blocking() -> None:
    canonical = _canonical()
    source = _source(
        canonical,
        findings=(
            _finding(
                "blocking-1",
                severity=FindingSeverity.BLOCKING,
                correction_required=True,
                evidence_refs=("evidence:alpha",),
            ),
        ),
        assessment=OverallAssessment.UNUSABLE,
        correction_required=True,
    )
    with pytest.raises(ReviewAssessmentError) as raised:
        _pipeline(source, _technical(source, blocking_ids=()))
    assert raised.value.code is ReviewAssessmentErrorCode.BLOCKING_IDS_MISMATCH


def test_provider_cannot_add_fake_finding() -> None:
    canonical = _canonical()
    source = _source(canonical)
    with pytest.raises(ReviewAssessmentError) as raised:
        _pipeline(source, _technical(source, assessed_ids=("fake",)))
    assert raised.value.code is ReviewAssessmentErrorCode.ASSESSED_IDS_MISMATCH


def test_partial_blocking_preserves_blocking_signal_and_limitations() -> None:
    canonical = _canonical()
    source = _source(
        canonical,
        findings=(
            _finding(
                "blocking-1",
                severity=FindingSeverity.BLOCKING,
                correction_required=True,
                evidence_refs=("evidence:alpha",),
            ),
        ),
        assessment=OverallAssessment.UNUSABLE,
        correction_required=True,
    )
    technical = _technical(source, status=ReviewPortResultStatus.PARTIAL)
    _, _, _, signal, handoff = _pipeline(source, technical)
    assert signal.technical_status is ReviewPortResultStatus.PARTIAL
    assert signal.overall_assessment is OverallAssessment.INCOMPLETE
    assert signal.promotion_blocked_by_review is True
    assert signal.limitations == technical.limitations
    assert handoff is not None


def test_source_c10_and_versioned_target_remain_unchanged() -> None:
    canonical = _canonical()
    source = _source(canonical)
    original = source
    _, target, _, signal, _ = _pipeline(source, _technical(source))
    assert source is original
    assert source.findings == ()
    assert signal.target_production_ref is canonical.target_production_ref
    assert target.target_production_ref == canonical.target_production_ref
    assert target.content == "Exact target content."


def test_handoff_contains_no_c11_or_direct_ag03_execution_surface() -> None:
    canonical = _canonical()
    source = _source(
        canonical,
        findings=(
            _finding(
                "major-1",
                severity=FindingSeverity.MAJOR,
                correction_required=True,
                evidence_refs=("evidence:alpha",),
            ),
        ),
        assessment=OverallAssessment.CORRECTION_REQUIRED,
        correction_required=True,
    )
    _, _, port, _, handoff = _pipeline(source, _technical(source))
    assert len(port.calls) == 1
    assert handoff is not None
    assert handoff.destination_agent_id is AgentId.AG_01
    assert not hasattr(handoff, "correction_request")
    assert not hasattr(handoff, "capability_id")
    assert not hasattr(handoff, "tool")
    assert not hasattr(handoff, "handler")
