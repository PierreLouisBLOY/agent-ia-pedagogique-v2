from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.review import (
    PreparedReviewCall,
    ResolvedReviewTarget,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewMaterializationError,
    ReviewMaterializationErrorCode,
    ReviewOperation,
    ReviewPortError,
    ReviewPortErrorCode,
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
from tests.support.review_fakes import RecordingReviewPort

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 26, 12, 1, tzinfo=UTC))
V01 = CapabilityId("CAP-V01")
V02 = CapabilityId("CAP-V02")


def _target_ref(name: str = "lesson-agent") -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", name)),
        VersionRef("v5"),
    )


def _canonical(
    *,
    target_ref: ObjectVersionRef | None = None,
    dimensions: tuple[ReviewDimension, ...] = (
        ReviewDimension.ACCURACY,
        ReviewDimension.SOURCES,
    ),
) -> ReviewRequest:
    return ReviewRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-review-agent",
            step_id="step-review-agent",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-review-agent"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
            status=InvocationStatus.PLANNED,
        ),
        target_production_ref=target_ref or _target_ref(),
        review_dimensions=dimensions,
        criteria={"required": ["grounded"]},
        evidence_refs=("evidence:one", "evidence:two"),
        severity_policy={"major": ["unsupported_claim"]},
        context_slice={"sections": ["content", "sources"]},
        independence_requirements={"separate_from_generation": True},
    )


def _meta(
    canonical: ReviewRequest,
    status: ReviewStatus = ReviewStatus.COMPLETED,
    *,
    run_id: str | None = None,
    step_id: str | None = None,
    actor: ActorRef | None = None,
) -> ContractMeta[ReviewStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id=run_id or canonical.meta.run_id,
        step_id=step_id or canonical.meta.step_id,
        parent_step_id=None,
        correlation_id=canonical.meta.correlation_id,
        created_at=LATER,
        actor=actor or ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
        status=status,
    )


def _finding(
    *,
    finding_id: str = "finding-1",
    dimension: str = ReviewDimension.ACCURACY.value,
    severity: str = FindingSeverity.MINOR.value,
    description: str = "A claim needs clearer support.",
    rationale: str = "The cited source only supports part of the claim.",
    correction_required: bool = False,
    evidence_refs: tuple[str, ...] = ("evidence:one",),
    target_locator: object | None = None,
    confidence: object | None = None,
    suggested_action: object | None = None,
) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "dimension": dimension,
        "severity": severity,
        "description": description,
        "target_locator": target_locator
        or {"kind": "text_span", "start": 0, "end": 6, "quote": "Caller"},
        "rationale": rationale,
        "correction_required": correction_required,
        "evidence_refs": evidence_refs,
        "confidence": confidence or {"level": "medium"},
        "suggested_action": suggested_action or {"action": "add_source"},
    }


def _technical(
    *,
    status: ReviewPortResultStatus = ReviewPortResultStatus.SUCCEEDED,
    operation: ReviewOperation = ReviewOperation.SEMANTIC_REVIEW,
    source_step_id: str = "step-review-agent",
    technical_findings: tuple[dict[str, object], ...] | None = None,
    evidence_refs_used: tuple[str, ...] = ("evidence:one",),
    assessment: str | None = None,
    correction_required: bool = False,
    coverage: tuple[str, ...] = (
        ReviewDimension.ACCURACY.value,
        ReviewDimension.SOURCES.value,
    ),
) -> ReviewPortResult:
    if status in {ReviewPortResultStatus.REFUSED, ReviewPortResultStatus.FAILED}:
        return ReviewPortResult(
            source_step_id=source_step_id,
            operation=operation,
            status=status,
            evidence_refs_used=evidence_refs_used,
            limitations=({"code": status.value},),
        )
    if assessment is None:
        assessment = (
            OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS.value
            if status is ReviewPortResultStatus.PARTIAL
            else OverallAssessment.ACCEPTABLE.value
        )
    findings = (_finding(),) if technical_findings is None else technical_findings
    return ReviewPortResult(
        source_step_id=source_step_id,
        operation=operation,
        status=status,
        structured_payload={
            "overall_assessment": assessment,
            "correction_required": correction_required,
            "coverage": coverage,
            "confidence": {"level": "high"},
        },
        technical_findings=findings,
        evidence_refs_used=evidence_refs_used,
        limitations=(
            ({"code": "LIMITED_SCOPE"},) if status is ReviewPortResultStatus.PARTIAL else ()
        ),
        warnings=(
            ({"code": "PARTIAL_REVIEW"},) if status is ReviewPortResultStatus.PARTIAL else ()
        ),
    )


def _prepared(
    *,
    canonical: ReviewRequest | None = None,
    capability: CapabilityId = V01,
) -> PreparedReviewCall:
    canonical = canonical or _canonical()
    technical = _technical(
        operation=(
            ReviewOperation.ASSESS_FINDINGS
            if capability == V02
            else ReviewOperation.SEMANTIC_REVIEW
        )
    )
    return ReviewCoordinator(RecordingReviewPort(result=technical)).prepare(
        request=ReviewPreparationRequest(
            capability,
            canonical,
            ResolvedReviewTarget(
                canonical.target_production_ref,
                content="Caller-resolved target content.",
            ),
            resolved_inputs={"authorized": "resolved"},
            output_contract={"type": "semantic_review"},
        )
    )


def _materialization_request(
    *,
    canonical: ReviewRequest | None = None,
    prepared: PreparedReviewCall | None = None,
    technical: ReviewPortResult | None = None,
    meta: ContractMeta[ReviewStatus] | None = None,
    review_id: str = "review:caller-supplied",
) -> ReviewResultMaterializationRequest:
    canonical = canonical or _canonical()
    prepared = prepared or _prepared(canonical=canonical)
    technical = technical or _technical(
        operation=prepared.port_request.operation,
        source_step_id=canonical.meta.step_id,
    )
    expected_status = (
        ReviewStatus.INCOMPLETE
        if technical.status is ReviewPortResultStatus.PARTIAL
        else ReviewStatus.COMPLETED
    )
    return ReviewResultMaterializationRequest(
        prepared=prepared,
        technical_result=technical,
        result_meta=meta or _meta(canonical, expected_status),
        review_id=review_id,
    )


def _agent(
    technical: ReviewPortResult | None = None,
    error: ReviewPortError | None = None,
) -> tuple[ReviewerAgent, RecordingReviewPort]:
    port = RecordingReviewPort(result=technical, error=error)
    return ReviewerAgent(ReviewCoordinator(port)), port


def _forge_prepared(
    prepared: PreparedReviewCall,
    **changes: object,
) -> PreparedReviewCall:
    forged = object.__new__(PreparedReviewCall)
    for item in fields(PreparedReviewCall):
        object.__setattr__(
            forged,
            item.name,
            changes.get(item.name, getattr(prepared, item.name)),
        )
    return forged


def _forge_result(result: ReviewPortResult, **changes: object) -> ReviewPortResult:
    forged = object.__new__(ReviewPortResult)
    for item in fields(ReviewPortResult):
        object.__setattr__(
            forged,
            item.name,
            changes.get(item.name, getattr(result, item.name)),
        )
    return forged


def test_materialization_error_vocabulary_is_exact_and_closed() -> None:
    assert tuple(item.value for item in ReviewMaterializationErrorCode) == (
        "UNSUPPORTED_CAPABILITY",
        "NON_MATERIALIZABLE_STATUS",
        "STATUS_MISMATCH",
        "SOURCE_STEP_MISMATCH",
        "OPERATION_MISMATCH",
        "TARGET_MISMATCH",
        "INVALID_TECHNICAL_FINDING",
        "DUPLICATE_FINDING_ID",
        "FINDING_DIMENSION_OUT_OF_SCOPE",
        "FINDING_EVIDENCE_OUT_OF_SCOPE",
        "FINDING_EVIDENCE_NOT_USED",
        "INVALID_OVERALL_ASSESSMENT",
        "COVERAGE_OUT_OF_SCOPE",
        "MATERIALIZATION_MISMATCH",
    )


def test_semantic_review_executes_cap_v01_through_one_port_call() -> None:
    canonical = _canonical()
    technical = _technical()
    agent, port = _agent(technical)
    preparation = ReviewPreparationRequest(
        V01,
        canonical,
        ResolvedReviewTarget(canonical.target_production_ref, content="Resolved."),
    )
    prepared, returned = agent.semantic_review(request=preparation)
    assert returned is technical
    assert prepared.preparation_request is preparation
    assert port.calls == [prepared.port_request]


@pytest.mark.parametrize("capability", (V02, CapabilityId("CAP-E01")))
def test_semantic_review_rejects_every_non_v01_capability_without_port_call(
    capability: CapabilityId,
) -> None:
    canonical = _canonical()
    agent, port = _agent(_technical())
    with pytest.raises(ReviewMaterializationError) as raised:
        agent.semantic_review(
            request=ReviewPreparationRequest(
                capability,
                canonical,
                ResolvedReviewTarget(canonical.target_production_ref, content="Resolved."),
            )
        )
    assert raised.value.code is ReviewMaterializationErrorCode.UNSUPPORTED_CAPABILITY
    assert port.calls == []


def test_semantic_review_propagates_port_error_without_retry() -> None:
    canonical = _canonical()
    error = ReviewPortError(ReviewPortErrorCode.UNAVAILABLE)
    agent, port = _agent(error=error)
    preparation = ReviewPreparationRequest(
        V01,
        canonical,
        ResolvedReviewTarget(canonical.target_production_ref, content="Resolved."),
    )
    with pytest.raises(ReviewPortError) as raised:
        agent.semantic_review(request=preparation)
    assert raised.value is error
    assert len(port.calls) == 1


def test_build_review_result_materializes_exact_c10_and_caller_identity() -> None:
    request = _materialization_request(review_id="review:external-id")
    result = ReviewerAgent(ReviewCoordinator(RecordingReviewPort())).build_review_result(
        request=request
    )
    assert result.meta is request.result_meta
    assert result.review_id == "review:external-id"
    assert result.target_production_ref == request.prepared.canonical_request.target_production_ref
    assert result.overall_assessment is OverallAssessment.ACCEPTABLE
    assert result.correction_required is False
    assert result.coverage == (
        ReviewDimension.ACCURACY,
        ReviewDimension.SOURCES,
    )
    assert result.evidence_refs_used == ("evidence:one",)
    finding = result.findings[0]
    assert finding.finding_id == "finding-1"
    assert finding.dimension is ReviewDimension.ACCURACY
    assert finding.severity is FindingSeverity.MINOR
    assert finding.evidence_refs == ("evidence:one",)


def test_multiple_findings_are_materialized_and_mappings_are_immutable() -> None:
    technical = _technical(
        technical_findings=(
            _finding(),
            _finding(
                finding_id="finding-2",
                dimension=ReviewDimension.SOURCES.value,
                severity=FindingSeverity.INFO.value,
                evidence_refs=("evidence:two",),
                target_locator={
                    "kind": "text_span",
                    "start": 7,
                    "end": 15,
                    "quote": "resolved",
                },
            ),
        ),
        evidence_refs_used=("evidence:one", "evidence:two"),
    )
    request = _materialization_request(technical=technical)
    result = ReviewerAgent(ReviewCoordinator(RecordingReviewPort())).build_review_result(
        request=request
    )
    assert tuple(item.finding_id for item in result.findings) == (
        "finding-1",
        "finding-2",
    )
    assert result.findings[1].target_locator == {
        "kind": "text_span",
        "start": 7,
        "end": 15,
        "quote": "resolved",
    }
    with pytest.raises(TypeError):
        result.findings[1].target_locator["start"] = 0  # type: ignore[index]


def test_duplicate_finding_ids_are_rejected() -> None:
    technical = _technical(
        technical_findings=(_finding(), _finding()),
    )
    with pytest.raises(ReviewMaterializationError) as raised:
        _materialization_request(technical=technical)
    assert raised.value.code is ReviewMaterializationErrorCode.DUPLICATE_FINDING_ID


@pytest.mark.parametrize(
    ("change", "code"),
    (
        (
            {"dimension": ReviewDimension.RISK.value},
            ReviewMaterializationErrorCode.FINDING_DIMENSION_OUT_OF_SCOPE,
        ),
        (
            {"dimension": "REV-UNKNOWN"},
            ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING,
        ),
        (
            {"severity": "critical"},
            ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING,
        ),
        (
            {"evidence_refs": ("evidence:foreign",)},
            ReviewMaterializationErrorCode.FINDING_EVIDENCE_OUT_OF_SCOPE,
        ),
        (
            {"evidence_refs": ("evidence:two",)},
            ReviewMaterializationErrorCode.FINDING_EVIDENCE_NOT_USED,
        ),
        (
            {"description": " "},
            ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING,
        ),
        (
            {"rationale": " "},
            ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING,
        ),
    ),
)
def test_invalid_technical_finding_is_rejected(
    change: dict[str, object],
    code: ReviewMaterializationErrorCode,
) -> None:
    finding = _finding()
    finding.update(change)
    technical = _technical(technical_findings=(finding,))
    with pytest.raises(ReviewMaterializationError) as raised:
        _materialization_request(technical=technical)
    assert raised.value.code is code


def test_closed_finding_schema_rejects_missing_and_extra_fields() -> None:
    missing = _finding()
    missing.pop("rationale")
    extra = _finding()
    extra["provider_note"] = "not canonical"
    for finding in (missing, extra):
        with pytest.raises(ReviewMaterializationError) as raised:
            _materialization_request(technical=_technical(technical_findings=(finding,)))
        assert raised.value.code is ReviewMaterializationErrorCode.INVALID_TECHNICAL_FINDING


@pytest.mark.parametrize(
    ("technical_status", "review_status"),
    (
        (ReviewPortResultStatus.SUCCEEDED, ReviewStatus.COMPLETED),
        (ReviewPortResultStatus.PARTIAL, ReviewStatus.INCOMPLETE),
    ),
)
def test_status_mapping_materializes_only_completed_or_incomplete(
    technical_status: ReviewPortResultStatus,
    review_status: ReviewStatus,
) -> None:
    canonical = _canonical()
    technical = _technical(status=technical_status)
    request = _materialization_request(
        canonical=canonical,
        technical=technical,
        meta=_meta(canonical, review_status),
    )
    result = ReviewerAgent(ReviewCoordinator(RecordingReviewPort())).build_review_result(
        request=request
    )
    assert result.meta.status is review_status
    assert result.limitations == technical.limitations
    assert result.warnings == technical.warnings


@pytest.mark.parametrize(
    "status",
    (ReviewPortResultStatus.REFUSED, ReviewPortResultStatus.FAILED),
)
def test_refused_and_failed_results_are_not_materializable(
    status: ReviewPortResultStatus,
) -> None:
    with pytest.raises(ReviewMaterializationError) as raised:
        _materialization_request(technical=_technical(status=status))
    assert raised.value.code is ReviewMaterializationErrorCode.NON_MATERIALIZABLE_STATUS


def test_result_meta_status_and_lineage_must_match() -> None:
    canonical = _canonical()
    with pytest.raises(ReviewMaterializationError) as status_error:
        _materialization_request(
            canonical=canonical,
            technical=_technical(),
            meta=_meta(canonical, ReviewStatus.INCOMPLETE),
        )
    assert status_error.value.code is ReviewMaterializationErrorCode.STATUS_MISMATCH
    for meta in (
        _meta(canonical, run_id="foreign-run"),
        _meta(canonical, step_id="foreign-step"),
        _meta(
            canonical,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
        ),
    ):
        with pytest.raises(ReviewMaterializationError) as lineage_error:
            _materialization_request(canonical=canonical, meta=meta)
        assert lineage_error.value.code is ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH


@pytest.mark.parametrize(
    ("payload_change", "code"),
    (
        (
            {"overall_assessment": "unknown"},
            ReviewMaterializationErrorCode.INVALID_OVERALL_ASSESSMENT,
        ),
        (
            {"coverage": (ReviewDimension.RISK.value,)},
            ReviewMaterializationErrorCode.COVERAGE_OUT_OF_SCOPE,
        ),
        (
            {"coverage": ()},
            ReviewMaterializationErrorCode.COVERAGE_OUT_OF_SCOPE,
        ),
        (
            {
                "overall_assessment": OverallAssessment.CORRECTION_REQUIRED.value,
                "correction_required": False,
            },
            ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH,
        ),
    ),
)
def test_payload_scope_assessment_and_c10_coherence_are_fail_closed(
    payload_change: dict[str, object],
    code: ReviewMaterializationErrorCode,
) -> None:
    technical = _technical()
    payload = dict(technical.structured_payload)
    payload.update(payload_change)
    forged = replace(technical, structured_payload=payload)
    with pytest.raises(ReviewMaterializationError) as raised:
        _materialization_request(technical=forged)
    assert raised.value.code is code


def test_closed_payload_schema_rejects_missing_and_extra_fields() -> None:
    technical = _technical()
    missing = dict(technical.structured_payload)
    missing.pop("confidence")
    extra = dict(technical.structured_payload)
    extra["review_id"] = "provider-controlled"
    for payload in (missing, extra):
        with pytest.raises(ReviewMaterializationError) as raised:
            _materialization_request(technical=replace(technical, structured_payload=payload))
        assert raised.value.code is ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH


def test_finding_correction_requirement_must_be_reflected_by_result() -> None:
    technical = _technical(
        technical_findings=(_finding(correction_required=True),),
        assessment=OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS.value,
        correction_required=False,
    )
    with pytest.raises(ReviewMaterializationError) as raised:
        _materialization_request(technical=technical)
    assert raised.value.code is ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH


def test_prepared_and_technical_lineage_forgery_are_rejected() -> None:
    prepared = _prepared()
    forged_target = _forge_prepared(
        prepared,
        target=ResolvedReviewTarget(_target_ref("foreign"), content="Forged."),
    )
    with pytest.raises(ReviewMaterializationError) as target_error:
        _materialization_request(prepared=forged_target)
    assert target_error.value.code is ReviewMaterializationErrorCode.TARGET_MISMATCH

    forged_prepared = _forge_prepared(
        prepared,
        port_request=replace(prepared.port_request, target_content="Forged."),
    )
    with pytest.raises(ReviewMaterializationError) as prepared_error:
        _materialization_request(prepared=forged_prepared)
    assert prepared_error.value.code is ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH

    with pytest.raises(ReviewMaterializationError) as step_error:
        _materialization_request(technical=_technical(source_step_id="forged-step"))
    assert step_error.value.code is ReviewMaterializationErrorCode.SOURCE_STEP_MISMATCH

    with pytest.raises(ReviewMaterializationError) as operation_error:
        _materialization_request(technical=_technical(operation=ReviewOperation.ASSESS_FINDINGS))
    assert operation_error.value.code is ReviewMaterializationErrorCode.OPERATION_MISMATCH


def test_forged_duplicate_result_evidence_is_rejected() -> None:
    forged = _forge_result(
        _technical(),
        evidence_refs_used=("evidence:one", "evidence:one"),
    )
    with pytest.raises(ReviewMaterializationError) as raised:
        _materialization_request(technical=forged)
    assert raised.value.code is ReviewMaterializationErrorCode.MATERIALIZATION_MISMATCH


def test_materialization_request_is_frozen_and_slotted_and_errors_are_safe() -> None:
    request = _materialization_request()
    with pytest.raises(FrozenInstanceError):
        request.review_id = "changed"  # type: ignore[misc]
    assert not hasattr(request, "__dict__")
    for code in ReviewMaterializationErrorCode:
        error = ReviewMaterializationError(code)
        assert str(error) == error.safe_reason
        assert "lesson-agent" not in error.safe_reason
        assert "evidence:one" not in error.safe_reason
