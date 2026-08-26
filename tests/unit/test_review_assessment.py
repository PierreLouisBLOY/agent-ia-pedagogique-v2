from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.agents.review import (
    CorrectionHandoffSignal,
    FindingsAssessmentRequest,
    ResolvedReviewTarget,
    ReviewAssessmentError,
    ReviewAssessmentErrorCode,
    ReviewAssessmentSignal,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewOperation,
    ReviewPortError,
    ReviewPortErrorCode,
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
from tests.support.review_fakes import RecordingReviewPort

NOW = Instant(datetime(2026, 8, 26, 14, 0, tzinfo=UTC))
LATER = Instant(datetime(2026, 8, 26, 14, 1, tzinfo=UTC))
V02 = CapabilityId("CAP-V02")


def _target_ref(name: str = "lesson-assessment") -> ObjectVersionRef:
    return ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", name)),
        VersionRef("v8"),
    )


def _canonical(*, target_ref: ObjectVersionRef | None = None) -> ReviewRequest:
    return ReviewRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="run-review-assessment",
            step_id="step-review-assessment",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-review-assessment"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
            status=InvocationStatus.PLANNED,
        ),
        target_production_ref=target_ref or _target_ref(),
        review_dimensions=(
            ReviewDimension.ACCURACY,
            ReviewDimension.SOURCES,
            ReviewDimension.RISK,
        ),
        criteria={"required": ["grounded"]},
        evidence_refs=("evidence:one", "evidence:two", "evidence:three"),
        severity_policy={"blocking": ["unsafe_instruction"]},
        context_slice={"sections": ["content", "sources"]},
        independence_requirements={"independent": True},
    )


def _finding(
    finding_id: str,
    *,
    dimension: ReviewDimension = ReviewDimension.ACCURACY,
    severity: FindingSeverity = FindingSeverity.MINOR,
    correction_required: bool = False,
    evidence_refs: tuple[str, ...] = ("evidence:one",),
    suggested_action: dict[str, object] | None = None,
) -> Finding:
    return Finding(
        finding_id=finding_id,
        dimension=dimension,
        severity=severity,
        description="Public finding description.",
        target_locator={"section": "content", "paragraph": 2},
        rationale="Public concise rationale.",
        correction_required=correction_required,
        evidence_refs=evidence_refs,
        confidence={"level": "high"},
        suggested_action=suggested_action or {"action": "revise_claim"},
    )


def _source_result(
    canonical: ReviewRequest,
    *,
    findings: tuple[Finding, ...] = (),
    assessment: OverallAssessment | None = None,
    correction_required: bool | None = None,
    status: ReviewStatus = ReviewStatus.COMPLETED,
    evidence_refs_used: tuple[str, ...] = (
        "evidence:one",
        "evidence:two",
        "evidence:three",
    ),
) -> ReviewResult:
    correction = (
        any(
            item.correction_required or item.severity is FindingSeverity.BLOCKING
            for item in findings
        )
        if correction_required is None
        else correction_required
    )
    blocking = any(item.severity is FindingSeverity.BLOCKING for item in findings)
    if assessment is None:
        assessment = (
            OverallAssessment.UNUSABLE
            if blocking
            else (
                OverallAssessment.CORRECTION_REQUIRED
                if correction
                else OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS
            )
        )
    return ReviewResult(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id=canonical.meta.run_id,
            step_id=canonical.meta.step_id,
            parent_step_id=None,
            correlation_id=canonical.meta.correlation_id,
            created_at=LATER,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
            status=status,
        ),
        review_id="review:source:1",
        target_production_ref=canonical.target_production_ref,
        findings=findings,
        overall_assessment=assessment,
        correction_required=correction,
        coverage=canonical.review_dimensions,
        evidence_refs_used=evidence_refs_used,
        confidence={"level": "high"},
        limitations=({"code": "SOURCE_LIMIT"},),
        warnings=({"code": "SOURCE_WARNING"},),
    )


def _expected_ids(source: ReviewResult) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    all_ids = tuple(item.finding_id for item in source.findings)
    blocking_ids = tuple(
        item.finding_id
        for item in source.findings
        if item.severity is FindingSeverity.BLOCKING
    )
    correction_ids = tuple(
        item.finding_id
        for item in source.findings
        if item.correction_required or item.severity is FindingSeverity.BLOCKING
    )
    return all_ids, blocking_ids, correction_ids


def _technical(
    source: ReviewResult,
    *,
    status: ReviewPortResultStatus = ReviewPortResultStatus.SUCCEEDED,
    assessed_ids: tuple[str, ...] | None = None,
    blocking_ids: tuple[str, ...] | None = None,
    correction_ids: tuple[str, ...] | None = None,
    assessment: OverallAssessment | None = None,
    correction_required: bool | None = None,
    technical_findings: tuple[dict[str, object], ...] = (),
    execution_metadata: dict[str, object] | None = None,
) -> ReviewPortResult:
    if status in {ReviewPortResultStatus.REFUSED, ReviewPortResultStatus.FAILED}:
        return ReviewPortResult(
            source_step_id="step-review-assessment",
            operation=ReviewOperation.ASSESS_FINDINGS,
            status=status,
            limitations=({"code": status.value},),
        )
    expected_all, expected_blocking, expected_correction = _expected_ids(source)
    if assessment is None:
        assessment = (
            OverallAssessment.INCOMPLETE
            if status is ReviewPortResultStatus.PARTIAL
            else source.overall_assessment
        )
    return ReviewPortResult(
        source_step_id="step-review-assessment",
        operation=ReviewOperation.ASSESS_FINDINGS,
        status=status,
        structured_payload={
            "assessed_finding_ids": (
                expected_all if assessed_ids is None else assessed_ids
            ),
            "blocking_finding_ids": (
                expected_blocking if blocking_ids is None else blocking_ids
            ),
            "correction_finding_ids": (
                expected_correction if correction_ids is None else correction_ids
            ),
            "overall_assessment": assessment.value,
            "correction_required": (
                bool(expected_correction)
                if correction_required is None
                else correction_required
            ),
            "confidence": {"level": "high"},
        },
        technical_findings=technical_findings,
        evidence_refs_used=("evidence:one",),
        limitations=(
            ({"code": "PARTIAL_SCOPE"},)
            if status is ReviewPortResultStatus.PARTIAL
            else ()
        ),
        warnings=(
            ({"code": "PARTIAL"},)
            if status is ReviewPortResultStatus.PARTIAL
            else ()
        ),
        execution_metadata=execution_metadata or {},
    )


def _request(
    canonical: ReviewRequest,
    source: ReviewResult,
    *,
    target: ResolvedReviewTarget | None = None,
    review_ref: str = "review-ref:caller",
    capability: CapabilityId = V02,
    resolved_inputs: dict[str, object] | None = None,
    output_contract: dict[str, object] | None = None,
) -> FindingsAssessmentRequest:
    values: dict[str, object] = {
        "capability_id": capability,
        "source_request": canonical,
        "source_result": source,
        "target": target
        or ResolvedReviewTarget(
            canonical.target_production_ref,
            content="Caller-resolved assessment target.",
        ),
        "review_ref": review_ref,
        "resolved_inputs": resolved_inputs or {"locale": "fr-FR"},
    }
    if output_contract is not None:
        values["output_contract"] = output_contract
    return FindingsAssessmentRequest(**values)  # type: ignore[arg-type]


def _agent(
    technical: ReviewPortResult | None = None,
    error: ReviewPortError | None = None,
) -> tuple[ReviewerAgent, RecordingReviewPort]:
    port = RecordingReviewPort(result=technical, error=error)
    return ReviewerAgent(ReviewCoordinator(port)), port


def _forge_result(result: ReviewPortResult, **changes: object) -> ReviewPortResult:
    forged = object.__new__(ReviewPortResult)
    for item in fields(ReviewPortResult):
        object.__setattr__(
            forged,
            item.name,
            changes.get(item.name, getattr(result, item.name)),
        )
    return forged


def test_assessment_error_vocabulary_is_closed_and_exact() -> None:
    assert tuple(item.value for item in ReviewAssessmentErrorCode) == (
        "UNSUPPORTED_CAPABILITY",
        "SOURCE_REVIEW_MISMATCH",
        "TARGET_MISMATCH",
        "REVIEW_REF_INVALID",
        "SNAPSHOT_MISMATCH",
        "NON_ASSESSABLE_STATUS",
        "SOURCE_STEP_MISMATCH",
        "OPERATION_MISMATCH",
        "TECHNICAL_FINDINGS_FORBIDDEN",
        "INVALID_TECHNICAL_PAYLOAD",
        "ASSESSED_IDS_MISMATCH",
        "BLOCKING_IDS_MISMATCH",
        "CORRECTION_IDS_MISMATCH",
        "INVALID_ASSESSMENT",
        "ASSESSMENT_INCOHERENT",
        "EVIDENCE_OUT_OF_SCOPE",
        "AUTHORITY_METADATA_FORBIDDEN",
    )


def test_cap_v02_nominal_assesses_all_findings_with_one_call() -> None:
    canonical = _canonical()
    source = _source_result(
        canonical,
        findings=(_finding("f-1"), _finding("f-2", dimension=ReviewDimension.SOURCES)),
    )
    technical = _technical(source)
    agent, port = _agent(technical)
    signal, handoff = agent.assess_findings(request=_request(canonical, source))
    assert port.calls and len(port.calls) == 1
    assert port.calls[0].operation is ReviewOperation.ASSESS_FINDINGS
    assert signal.assessed_finding_ids == ("f-1", "f-2")
    assert signal.blocking_finding_ids == ()
    assert signal.correction_finding_ids == ()
    assert signal.promotion_blocked_by_review is False
    assert handoff is None


def test_provider_snapshot_is_exact_closed_and_immutable() -> None:
    canonical = _canonical()
    finding = _finding(
        "f-1",
        dimension=ReviewDimension.SOURCES,
        severity=FindingSeverity.MAJOR,
        correction_required=True,
        evidence_refs=("evidence:two",),
    )
    source = _source_result(canonical, findings=(finding,))
    agent, port = _agent(_technical(source))
    agent.assess_findings(
        request=_request(
            canonical,
            source,
            resolved_inputs={"locale": "fr-FR", "rubric": {"version": 2}},
        )
    )
    resolved = port.calls[0].resolved_inputs
    assert resolved["additional_inputs"] == {
        "locale": "fr-FR",
        "rubric": {"version": 2},
    }
    snapshot = resolved["source_review"]
    assert isinstance(snapshot, dict | type(resolved))
    assert snapshot["review_id"] == source.review_id  # type: ignore[index]
    assert snapshot["review_ref"] == "review-ref:caller"  # type: ignore[index]
    technical_finding = snapshot["findings"][0]  # type: ignore[index]
    assert set(technical_finding) == {
        "finding_id",
        "dimension",
        "severity",
        "description",
        "target_locator",
        "rationale",
        "correction_required",
        "evidence_refs",
        "confidence",
        "suggested_action",
    }
    assert technical_finding["severity"] == FindingSeverity.MAJOR.value
    with pytest.raises(TypeError):
        technical_finding["severity"] = "minor"


def test_blocking_recalculation_sets_signal_and_exact_ag01_handoff() -> None:
    canonical = _canonical()
    source = _source_result(
        canonical,
        findings=(
            _finding(
                "blocking-1",
                severity=FindingSeverity.BLOCKING,
                evidence_refs=("evidence:one", "evidence:two"),
                suggested_action={"action": "remove_unsafe_instruction"},
            ),
            _finding(
                "minor-1",
                severity=FindingSeverity.MINOR,
                evidence_refs=("evidence:three",),
            ),
        ),
    )
    signal, handoff = _agent(_technical(source))[0].assess_findings(
        request=_request(canonical, source)
    )
    assert signal.blocking_finding_ids == ("blocking-1",)
    assert signal.correction_finding_ids == ("blocking-1",)
    assert signal.correction_required is True
    assert signal.promotion_blocked_by_review is True
    assert isinstance(handoff, CorrectionHandoffSignal)
    assert handoff.destination_agent_id is AgentId.AG_01
    assert handoff.finding_ids == ("blocking-1",)
    assert handoff.blocking_finding_ids == ("blocking-1",)
    assert handoff.evidence_refs == ("evidence:one", "evidence:two")
    assert handoff.suggested_actions == (
        {
            "finding_id": "blocking-1",
            "suggested_action": {"action": "remove_unsafe_instruction"},
        },
    )
    assert "allowed_changes" not in handoff.suggested_actions[0]


def test_correction_flag_recalculation_emits_handoff_without_blocking_signal() -> None:
    canonical = _canonical()
    source = _source_result(
        canonical,
        findings=(
            _finding(
                "major-1",
                severity=FindingSeverity.MAJOR,
                correction_required=True,
                evidence_refs=("evidence:two",),
            ),
        ),
    )
    signal, handoff = _agent(_technical(source))[0].assess_findings(
        request=_request(canonical, source)
    )
    assert signal.blocking_finding_ids == ()
    assert signal.correction_finding_ids == ("major-1",)
    assert signal.promotion_blocked_by_review is False
    assert handoff is not None and handoff.finding_ids == ("major-1",)


@pytest.mark.parametrize(
    ("changes", "code"),
    (
        (
            {"assessed_ids": ()},
            ReviewAssessmentErrorCode.ASSESSED_IDS_MISMATCH,
        ),
        (
            {"assessed_ids": ("f-1", "fake")},
            ReviewAssessmentErrorCode.ASSESSED_IDS_MISMATCH,
        ),
        (
            {"blocking_ids": ()},
            ReviewAssessmentErrorCode.BLOCKING_IDS_MISMATCH,
        ),
        (
            {"blocking_ids": ("f-1", "fake")},
            ReviewAssessmentErrorCode.BLOCKING_IDS_MISMATCH,
        ),
        (
            {"correction_ids": ()},
            ReviewAssessmentErrorCode.CORRECTION_IDS_MISMATCH,
        ),
        (
            {"correction_ids": ("fake",)},
            ReviewAssessmentErrorCode.CORRECTION_IDS_MISMATCH,
        ),
    ),
)
def test_provider_cannot_falsify_assessed_blocking_or_correction_ids(
    changes: dict[str, object],
    code: ReviewAssessmentErrorCode,
) -> None:
    canonical = _canonical()
    source = _source_result(
        canonical,
        findings=(
            _finding(
                "f-1",
                severity=FindingSeverity.BLOCKING,
                correction_required=True,
            ),
        ),
    )
    technical = _technical(source, **changes)  # type: ignore[arg-type]
    with pytest.raises(ReviewAssessmentError) as raised:
        _agent(technical)[0].assess_findings(request=_request(canonical, source))
    assert raised.value.code is code


def test_cap_v02_refuses_new_technical_findings() -> None:
    canonical = _canonical()
    source = _source_result(canonical)
    technical = _technical(source, technical_findings=({"finding_id": "invented"},))
    with pytest.raises(ReviewAssessmentError) as raised:
        _agent(technical)[0].assess_findings(request=_request(canonical, source))
    assert raised.value.code is ReviewAssessmentErrorCode.TECHNICAL_FINDINGS_FORBIDDEN


@pytest.mark.parametrize(
    ("assessment", "code"),
    (
        (OverallAssessment.ACCEPTABLE, ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT),
        (
            OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS,
            ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT,
        ),
    ),
)
def test_blocking_cannot_be_presented_as_acceptable_or_reservations(
    assessment: OverallAssessment,
    code: ReviewAssessmentErrorCode,
) -> None:
    canonical = _canonical()
    source = _source_result(
        canonical,
        findings=(_finding("f-1", severity=FindingSeverity.BLOCKING),),
    )
    with pytest.raises(ReviewAssessmentError) as raised:
        _agent(_technical(source, assessment=assessment))[0].assess_findings(
            request=_request(canonical, source)
        )
    assert raised.value.code is code


def test_partial_with_blocking_preserves_incomplete_and_blocking_signal() -> None:
    canonical = _canonical()
    source = _source_result(
        canonical,
        findings=(_finding("f-1", severity=FindingSeverity.BLOCKING),),
    )
    technical = _technical(source, status=ReviewPortResultStatus.PARTIAL)
    signal, handoff = _agent(technical)[0].assess_findings(
        request=_request(canonical, source)
    )
    assert signal.technical_status is ReviewPortResultStatus.PARTIAL
    assert signal.overall_assessment is OverallAssessment.INCOMPLETE
    assert signal.promotion_blocked_by_review is True
    assert signal.limitations == source.limitations + technical.limitations
    assert handoff is not None


def test_partial_cannot_be_presented_as_non_incomplete() -> None:
    canonical = _canonical()
    source = _source_result(canonical)
    with pytest.raises(ReviewAssessmentError) as raised:
        _agent(
            _technical(
                source,
                status=ReviewPortResultStatus.PARTIAL,
                assessment=OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS,
            )
        )[0].assess_findings(request=_request(canonical, source))
    assert raised.value.code is ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT


@pytest.mark.parametrize(
    "status",
    (ReviewPortResultStatus.REFUSED, ReviewPortResultStatus.FAILED),
)
def test_refused_and_failed_create_no_assessment_signal(
    status: ReviewPortResultStatus,
) -> None:
    canonical = _canonical()
    source = _source_result(canonical)
    with pytest.raises(ReviewAssessmentError) as raised:
        _agent(_technical(source, status=status))[0].assess_findings(
            request=_request(canonical, source)
        )
    assert raised.value.code is ReviewAssessmentErrorCode.NON_ASSESSABLE_STATUS


def test_request_rejects_target_review_ref_capability_and_output_contract_drift() -> None:
    canonical = _canonical()
    source = _source_result(canonical)
    with pytest.raises(ReviewAssessmentError) as target_error:
        _request(
            canonical,
            source,
            target=ResolvedReviewTarget(_target_ref("foreign"), content="Foreign."),
        )
    assert target_error.value.code is ReviewAssessmentErrorCode.TARGET_MISMATCH
    with pytest.raises(ReviewAssessmentError) as ref_error:
        _request(canonical, source, review_ref=" ")
    assert ref_error.value.code is ReviewAssessmentErrorCode.REVIEW_REF_INVALID
    with pytest.raises(ReviewAssessmentError) as capability_error:
        _request(canonical, source, capability=CapabilityId("CAP-V01"))
    assert capability_error.value.code is ReviewAssessmentErrorCode.UNSUPPORTED_CAPABILITY
    with pytest.raises(ReviewAssessmentError) as contract_error:
        _request(canonical, source, output_contract={"type": "forged"})
    assert contract_error.value.code is ReviewAssessmentErrorCode.SNAPSHOT_MISMATCH


def test_blocking_source_c10_without_global_correction_fails_closed() -> None:
    canonical = _canonical()
    source = _source_result(
        canonical,
        findings=(_finding("f-1", severity=FindingSeverity.BLOCKING),),
        assessment=OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS,
        correction_required=False,
    )
    with pytest.raises(ReviewAssessmentError) as raised:
        _request(canonical, source)
    assert raised.value.code is ReviewAssessmentErrorCode.ASSESSMENT_INCOHERENT


def test_technical_authority_metadata_is_rejected_even_when_forged() -> None:
    canonical = _canonical()
    source = _source_result(canonical)
    forged = _forge_result(
        _technical(source),
        execution_metadata={"gate_approved": True},
    )
    with pytest.raises(ReviewAssessmentError) as raised:
        _agent(forged)[0].assess_findings(request=_request(canonical, source))
    assert raised.value.code is ReviewAssessmentErrorCode.AUTHORITY_METADATA_FORBIDDEN


def test_caller_inputs_cannot_smuggle_authority_metadata() -> None:
    canonical = _canonical()
    source = _source_result(canonical)
    with pytest.raises(ReviewAssessmentError) as raised:
        _request(
            canonical,
            source,
            resolved_inputs={"nested": {"gate_approved": True}},
        )
    assert raised.value.code is ReviewAssessmentErrorCode.AUTHORITY_METADATA_FORBIDDEN


def test_forged_payload_confidence_cannot_smuggle_authority_metadata() -> None:
    canonical = _canonical()
    source = _source_result(canonical)
    technical = _technical(source)
    forged_payload = dict(technical.structured_payload)
    forged_payload["confidence"] = {"validated": True}
    forged = _forge_result(technical, structured_payload=forged_payload)
    with pytest.raises(ReviewAssessmentError) as raised:
        _agent(forged)[0].assess_findings(request=_request(canonical, source))
    assert raised.value.code is ReviewAssessmentErrorCode.AUTHORITY_METADATA_FORBIDDEN


def test_port_error_is_propagated_once_without_retry() -> None:
    canonical = _canonical()
    source = _source_result(canonical)
    error = ReviewPortError(ReviewPortErrorCode.UNAVAILABLE)
    agent, port = _agent(error=error)
    with pytest.raises(ReviewPortError) as raised:
        agent.assess_findings(request=_request(canonical, source))
    assert raised.value is error
    assert len(port.calls) == 1


def test_signals_are_frozen_slotted_noncanonical_and_contain_no_c11() -> None:
    canonical = _canonical()
    source = _source_result(
        canonical,
        findings=(_finding("f-1", correction_required=True),),
    )
    signal, handoff = _agent(_technical(source))[0].assess_findings(
        request=_request(canonical, source)
    )
    assert isinstance(signal, ReviewAssessmentSignal)
    assert handoff is not None
    with pytest.raises(FrozenInstanceError):
        signal.promotion_blocked_by_review = True  # type: ignore[misc]
    assert not hasattr(signal, "__dict__")
    assert not hasattr(handoff, "__dict__")
    assert not hasattr(handoff, "correction_request")
    assert not hasattr(handoff, "capability_id")
    assert not hasattr(handoff, "allowed_changes")


def test_errors_are_fixed_and_agent_safe() -> None:
    for code in ReviewAssessmentErrorCode:
        error = ReviewAssessmentError(code)
        assert str(error) == error.safe_reason
        assert "lesson-assessment" not in error.safe_reason
        assert "evidence:one" not in error.safe_reason
