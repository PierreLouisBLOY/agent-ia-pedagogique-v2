from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResult,
    AgentResultStatus,
    BudgetSpec,
    ContractMeta,
    CorrectionRequest,
    DelegationEnvelope,
    DelegationResult,
    EvidenceItem,
    EvidenceRequest,
    EvidenceSet,
    ExecutorKind,
    ExecutorRef,
    Finding,
    FindingSeverity,
    GateDecision,
    GateDecisionValue,
    GateRequest,
    GateStatus,
    InvocationStatus,
    OverallAssessment,
    PermissionScope,
    ProductionCandidate,
    ProductionRequest,
    ProductionValidationState,
    ReviewDimension,
    ReviewRequest,
    ReviewResult,
    ReviewStatus,
    StepKind,
    StepSpec,
    ToolCallRequest,
    ToolCallResult,
    UseCaseRequest,
    UseCaseResult,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowStatus,
)
from backend.core_contracts.capability import CapabilityId
from backend.core_contracts.invocation import UseCaseContext
from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))


def _actor(
    kind: ActorKind = ActorKind.AGENT, actor_id: str = AgentId.AG_02.value
) -> ActorRef:
    return ActorRef(kind=kind, actor_id=actor_id)


def _meta[TStatus](
    status: TStatus,
    *,
    actor: ActorRef | None = None,
    step_id: str = "step-1",
    created_at: Instant = NOW,
    correlation_id: str = "corr-1",
) -> ContractMeta[TStatus]:
    return ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id="run-1",
        step_id=step_id,
        parent_step_id=None,
        correlation_id=CorrelationId(correlation_id),
        created_at=created_at,
        actor=actor or _actor(),
        status=status,
    )


def _permission_scope(agent_id: AgentId = AgentId.AG_02) -> PermissionScope:
    return PermissionScope(
        principal=_actor(actor_id=agent_id.value),
        capability_ids=(CapabilityId("course.generate"),),
    )


def _step() -> StepSpec:
    return StepSpec(
        step_id="step-1",
        kind=StepKind.AGENT,
        capability_id=CapabilityId("course.generate"),
        executor=ExecutorRef(ExecutorKind.AG_02),
        objective="Generate a candidate",
        output_contract={"type": "production_candidate"},
    )


def _delegation() -> DelegationEnvelope:
    return DelegationEnvelope(
        delegation_id="delegation-1",
        source_step=_step(),
        target_agent=AgentId.AG_02,
        context_slice={},
        evidence_refs=(),
        constraints={},
        permission_scope=_permission_scope(),
    )


def _evidence_item(evidence_id: str = "evidence-1") -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        source_ref="source-1",
        source_kind="curriculum",
        locator="chapter-2",
        retrieved_at=NOW,
        relevance={"basis": "direct"},
        authority={"level": "official"},
    )


def _production_version(
    version: str = "v1",
    production_id: str = "production-1",
) -> ObjectVersionRef:
    return ObjectVersionRef(
        object_ref=TypedEntityRef(
            TypedEntityId(entity_type="production", value=production_id)
        ),
        version_ref=VersionRef(version),
    )


def _gate_request(
    *,
    gate_id: str = "gate-1",
    required_actor: ActorRef | None = None,
    step_id: str = "step-1",
    correlation_id: str = "corr-1",
    expires_at: Instant | None = None,
) -> GateRequest:
    return GateRequest(
        meta=_meta(
            GateStatus.PENDING,
            step_id=step_id,
            correlation_id=correlation_id,
        ),
        gate_id=gate_id,
        gate_type="approval",
        reason="Canonical promotion requires authority",
        options=({"id": "approve"}, {"id": "reject"}),
        required_actor=required_actor or _actor(ActorKind.USER, "user-1"),
        expires_at=expires_at,
    )


def test_c2_types_are_publicly_materialized() -> None:
    assert all(
        item is not None
        for item in (
            DelegationResult,
            EvidenceRequest,
            EvidenceItem,
            EvidenceSet,
            ProductionRequest,
            ProductionCandidate,
            ReviewRequest,
            Finding,
            ReviewResult,
            CorrectionRequest,
            UseCaseRequest,
            UseCaseResult,
            ToolCallRequest,
            ToolCallResult,
            GateRequest,
            GateDecision,
            WorkflowEvent,
        )
    )


def test_c2_enums_have_exact_canonical_values() -> None:
    assert [item.value for item in ProductionValidationState] == ["candidate"]
    assert [item.value for item in ReviewStatus] == ["completed", "incomplete", "failed"]
    assert [item.value for item in ReviewDimension] == [
        "REV-ACC",
        "REV-COV",
        "REV-PED",
        "REV-INS",
        "REV-STR",
        "REV-SRC",
        "REV-CON",
        "REV-FMT",
        "REV-RSK",
    ]
    assert [item.value for item in FindingSeverity] == [
        "info",
        "minor",
        "major",
        "blocking",
    ]
    assert [item.value for item in OverallAssessment] == [
        "acceptable",
        "acceptable_with_reservations",
        "correction_required",
        "unusable",
        "incomplete",
    ]
    assert [item.value for item in GateStatus] == [
        "pending",
        "approved",
        "rejected",
        "deferred",
        "expired",
    ]
    assert [item.value for item in GateDecisionValue] == [
        "approved",
        "rejected",
        "deferred",
    ]
    assert [item.value for item in WorkflowEventType] == [
        "planned",
        "routed",
        "delegated",
        "tool_called",
        "usecase_called",
        "reviewed",
        "corrected",
        "gated",
        "stopped",
    ]
    assert [item.value for item in WorkflowStatus] == [
        "planned",
        "running",
        "waiting_gate",
        "replanning",
        "succeeded",
        "partial",
        "failed",
        "cancelled",
        "escalated",
    ]


def test_delegation_result_enforces_identity_and_local_lineage() -> None:
    delegation = _delegation()
    agent_result = AgentResult[dict[str, object]](
        meta=_meta(AgentResultStatus.SUCCEEDED),
        invocation_id="invocation-1",
        payload={"ok": True},
    )
    result = DelegationResult(
        delegation_id="delegation-1",
        source_agent=AgentId.AG_02,
        agent_result=agent_result,
        delegation=delegation,
    )
    assert result.agent_result is agent_result

    with pytest.raises(ValueError):
        DelegationResult(
            delegation_id="",
            source_agent=AgentId.AG_02,
            agent_result=agent_result,
        )
    with pytest.raises(ValueError):
        DelegationResult(
            delegation_id="delegation-1",
            source_agent=AgentId.AG_01,
            agent_result=agent_result,
        )
    with pytest.raises(ValueError):
        DelegationResult(
            delegation_id="other",
            source_agent=AgentId.AG_02,
            agent_result=agent_result,
            delegation=delegation,
        )


def test_evidence_request_is_data_only_safe_and_accepts_zero_max_items() -> None:
    request = EvidenceRequest(
        meta=_meta(InvocationStatus.PLANNED),
        search_goal="Find curriculum authority",
        scope={"grade": 6},
        max_items=0,
    )
    assert request.max_items == 0
    with pytest.raises(TypeError):
        request.scope["grade"] = 7  # type: ignore[index]
    with pytest.raises(ValueError):
        EvidenceRequest(
            meta=_meta(InvocationStatus.PLANNED),
            search_goal="Find evidence",
            filters={"provider_payload": {"raw": True}},
        )


def test_evidence_item_requires_minimum_provenance() -> None:
    assert _evidence_item().source_ref == "source-1"
    with pytest.raises(ValueError):
        EvidenceItem(
            evidence_id="evidence-1",
            source_ref="",
            source_kind="curriculum",
            locator="chapter-2",
            retrieved_at=NOW,
        )
    with pytest.raises(ValueError):
        EvidenceItem(
            evidence_id="evidence-1",
            source_ref="generation-1",
            source_kind="llm_output",
            locator="response",
            retrieved_at=NOW,
        )
    with pytest.raises(ValueError):
        EvidenceItem(
            evidence_id="evidence-1",
            source_ref="source-1",
            source_kind="",
            locator="chapter-2",
            retrieved_at=NOW,
        )


@pytest.mark.parametrize(
    "source_kind",
    [
        "llm",
        "llm_output",
        "llm-output",
        "generated_by_llm",
        "llmGenerated",
        "model_output",
        "model-generated-output",
        "agent_output",
        "agentOutput",
        "generated_agent_output",
    ],
)
def test_evidence_item_rejects_lexical_generative_source_kinds(
    source_kind: str,
) -> None:
    with pytest.raises(ValueError):
        EvidenceItem(
            evidence_id="evidence-1",
            source_ref="generation-1",
            source_kind=source_kind,
            locator="response",
            retrieved_at=NOW,
        )


@pytest.mark.parametrize(
    "source_kind",
    [
        "official_document",
        "user_document",
        "database_record",
        "web_source",
        "tool_observation",
        "data_model",
    ],
)
def test_evidence_item_accepts_legitimate_source_kinds(source_kind: str) -> None:
    item = EvidenceItem(
        evidence_id="evidence-1",
        source_ref="source-1",
        source_kind=source_kind,
        locator="section-1",
        retrieved_at=NOW,
    )

    assert item.source_kind == source_kind


def test_evidence_set_accepts_empty_and_rejects_duplicate_ids() -> None:
    empty = EvidenceSet(meta=_meta(AgentResultStatus.SUCCEEDED))
    assert empty.evidence_items == ()
    item = _evidence_item()
    with pytest.raises(ValueError):
        EvidenceSet(
            meta=_meta(AgentResultStatus.SUCCEEDED),
            evidence_items=(item, item),
        )


def test_production_request_and_candidate_preserve_refs_and_candidate_state() -> None:
    request = ProductionRequest(
        meta=_meta(InvocationStatus.PLANNED),
        production_kind="lesson",
        brief="Build a lesson",
        output_format="structured",
        evidence_refs=("evidence-1",),
    )
    candidate = ProductionCandidate(
        meta=_meta(AgentResultStatus.SUCCEEDED),
        production_id="production-1",
        production_kind=request.production_kind,
        structured_payload={"sections": ["intro"]},
        lineage={"target_ref": "production-0"},
        evidence_refs_used=request.evidence_refs,
    )
    assert candidate.validation_state is ProductionValidationState.CANDIDATE
    assert candidate.evidence_refs_used == ("evidence-1",)
    with pytest.raises(ValueError):
        ProductionCandidate(
            meta=_meta(AgentResultStatus.SUCCEEDED),
            production_id="production-2",
            production_kind="lesson",
            content="draft",
            validation_state="validated",  # type: ignore[arg-type]
        )


def test_production_candidate_rejects_private_generation_metadata() -> None:
    with pytest.raises(ValueError):
        ProductionCandidate(
            meta=_meta(AgentResultStatus.SUCCEEDED),
            production_id="production-1",
            production_kind="lesson",
            content="draft",
            generation_metadata={"audit": {"privateReasoning": "hidden"}},
        )


def test_review_request_result_and_finding_keep_review_separate_from_validation() -> None:
    request = ReviewRequest(
        meta=_meta(InvocationStatus.PLANNED),
        target_production_ref=_production_version(),
        review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.SOURCES),
        review_budget=BudgetSpec(max_steps=2),
    )
    finding = Finding(
        finding_id="finding-1",
        dimension=ReviewDimension.ACCURACY,
        severity=FindingSeverity.MAJOR,
        description="A citation is missing",
        target_locator={"section": "intro"},
        rationale="The claim has no source.",
        correction_required=True,
        confidence={"level": "high"},
        suggested_action={"kind": "add_source"},
    )
    result = ReviewResult(
        meta=_meta(ReviewStatus.COMPLETED),
        review_id="review-1",
        target_production_ref=request.target_production_ref,
        findings=(finding,),
        overall_assessment=OverallAssessment.CORRECTION_REQUIRED,
        correction_required=True,
        coverage=request.review_dimensions,
        evidence_refs_used=("evidence-1",),
    )
    assert result.target_production_ref == request.target_production_ref
    assert "validated" not in {item.name for item in fields(ReviewResult)}
    assert "promotion" not in {item.name for item in fields(ReviewResult)}


def test_finding_rejects_nested_private_reasoning() -> None:
    with pytest.raises(ValueError):
        Finding(
            finding_id="finding-1",
            dimension=ReviewDimension.ACCURACY,
            severity=FindingSeverity.MAJOR,
            description="Issue",
            target_locator={"debug": {"chain-of-thought": "hidden"}},
            rationale="Public rationale",
            correction_required=True,
        )


def test_review_request_rejects_duplicate_dimensions() -> None:
    with pytest.raises(ValueError):
        ReviewRequest(
            meta=_meta(InvocationStatus.PLANNED),
            target_production_ref=_production_version(),
            review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.ACCURACY),
        )


def test_finding_fields_are_safe_without_deriving_correction_policy() -> None:
    finding = Finding(
        finding_id="finding-1",
        dimension=ReviewDimension.RISK,
        severity=FindingSeverity.BLOCKING,
        description="A risk needs authority review",
        target_locator={"section": "safety"},
        rationale="The public criterion is unmet.",
        correction_required=False,
        confidence={"level": "high"},
        suggested_action={"kind": "escalate"},
    )

    assert finding.correction_required is False
    with pytest.raises(TypeError):
        finding.confidence["level"] = "low"  # type: ignore[index]
    with pytest.raises(ValueError):
        Finding(
            finding_id="finding-2",
            dimension=ReviewDimension.RISK,
            severity=FindingSeverity.MINOR,
            description="Issue",
            target_locator={"section": "safety"},
            rationale="Public rationale",
            correction_required=True,
            suggested_action={"privateReasoning": "hidden"},
        )
    with pytest.raises(TypeError):
        Finding(
            finding_id="finding-3",
            dimension=ReviewDimension.ACCURACY,
            severity=FindingSeverity.INFO,
            description="Issue",
            target_locator={"section": "intro"},
            rationale="Public rationale",
            correction_required="yes",  # type: ignore[arg-type]
        )


def test_review_result_validates_coverage_and_evidence_refs() -> None:
    with pytest.raises(ValueError):
        ReviewResult(
            meta=_meta(ReviewStatus.COMPLETED),
            review_id="review-1",
            target_production_ref=_production_version(),
            findings=(),
            overall_assessment=OverallAssessment.ACCEPTABLE,
            correction_required=False,
            coverage=(ReviewDimension.ACCURACY, ReviewDimension.ACCURACY),
            evidence_refs_used=(),
        )
    with pytest.raises(ValueError):
        ReviewResult(
            meta=_meta(ReviewStatus.INCOMPLETE),
            review_id="review-2",
            target_production_ref=_production_version(),
            findings=(),
            overall_assessment=OverallAssessment.INCOMPLETE,
            correction_required=False,
            coverage=(),
            evidence_refs_used=("",),
        )

    structurally_independent = ReviewResult(
        meta=_meta(ReviewStatus.COMPLETED),
        review_id="review-3",
        target_production_ref=_production_version(),
        findings=(),
        overall_assessment=OverallAssessment.ACCEPTABLE_WITH_RESERVATIONS,
        correction_required=True,
        coverage=(ReviewDimension.FORMAT,),
        evidence_refs_used=(),
    )
    assert structurally_independent.correction_required is True


def test_correction_request_is_immutable_and_version_oriented() -> None:
    request = CorrectionRequest(
        meta=_meta(InvocationStatus.PLANNED),
        target_production_ref=_production_version(),
        review_ref="review-1",
        finding_ids=("finding-1",),
        evidence_refs=("evidence-1",),
        expected_delta={"new_version": True},
    )
    assert request.target_production_ref == _production_version()
    assert request.review_ref == "review-1"
    assert request.evidence_refs == ("evidence-1",)
    with pytest.raises(FrozenInstanceError):
        request.review_ref = "review-2"  # type: ignore[misc]
    with pytest.raises(ValueError):
        CorrectionRequest(
            meta=_meta(InvocationStatus.PLANNED),
            target_production_ref=_production_version(),
            review_ref="review-1",
            finding_ids=("finding-1",),
            evidence_refs=("",),
        )


def test_use_case_request_composes_context_and_rejects_private_payload() -> None:
    context = UseCaseContext(correlation_id=CorrelationId("corr-1"))
    request = UseCaseRequest(
        meta=_meta(InvocationStatus.PLANNED),
        use_case_id="lesson.create",
        payload={"title": "Fractions"},
        actor_context=context,
        precondition_refs=("production-1",),
        requested_effect={"kind": "create"},
    )
    assert request.actor_context is context
    with pytest.raises(ValueError):
        UseCaseRequest(
            meta=_meta(InvocationStatus.PLANNED),
            use_case_id="lesson.create",
            payload={"system_prompt": "hidden"},
            actor_context=context,
        )


def test_use_case_result_composes_application_outcome_without_masking_errors() -> None:
    outcome: ApplicationOutcome[dict[str, object], object] = ApplicationOutcome(
        outcome_status=OutcomeStatus.SUCCESS,
        success=True,
        correlation_id=CorrelationId("corr-1"),
        data={"created": True},
    )
    result = UseCaseResult(
        meta=_meta(OutcomeStatus.SUCCESS),
        use_case_id="lesson.create",
        outcome=outcome,
        result_ref="lesson-1",
        domain_events=({"event_type": "lesson_created"},),
    )
    assert result.outcome is outcome
    assert result.outcome.business_errors == ()


def test_tool_call_request_requires_capability_scope_and_safe_arguments() -> None:
    request = ToolCallRequest(
        meta=_meta(InvocationStatus.PLANNED),
        tool_id="search.catalog",
        capability_id=CapabilityId("search.read"),
        arguments={"query": "fractions"},
        permission_scope=_permission_scope(),
        timeout=0,
    )
    assert request.tool_id == "search.catalog"
    with pytest.raises(TypeError):
        ToolCallRequest(
            meta=_meta(InvocationStatus.PLANNED),
            tool_id="search.catalog",
            capability_id=None,  # type: ignore[arg-type]
            arguments={},
            permission_scope=_permission_scope(),
        )
    with pytest.raises(TypeError):
        ToolCallRequest(
            meta=_meta(InvocationStatus.PLANNED),
            tool_id="search.catalog",
            capability_id=CapabilityId("search.read"),
            arguments={},
            permission_scope=None,  # type: ignore[arg-type]
        )


def test_tool_call_result_preserves_refs_and_can_be_correlated_locally() -> None:
    request = ToolCallRequest(
        meta=_meta(InvocationStatus.PLANNED),
        tool_id="search.catalog",
        capability_id=CapabilityId("search.read"),
        arguments={},
        permission_scope=_permission_scope(),
    )
    result = ToolCallResult(
        meta=_meta(AgentResultStatus.SUCCEEDED),
        tool_id="search.catalog",
        output={"items": []},
        artifacts=("artifact-1",),
    )
    assert result.tool_id == request.tool_id
    assert result.artifacts == ("artifact-1",)


def test_gate_request_is_pending_and_decision_refuses_ag_01() -> None:
    approver = _actor(ActorKind.USER, "user-1")
    request = _gate_request(required_actor=approver)
    decision = GateDecision(
        meta=_meta(GateStatus.APPROVED, actor=approver),
        gate_id="gate-1",
        decision=GateDecisionValue.APPROVED,
        actor=approver,
        decided_at=NOW,
        decision_ref="decision-1",
        request=request,
        selected_option={"id": "approve"},
    )
    assert decision.gate_id == request.gate_id

    ag_01 = _actor(actor_id=AgentId.AG_01.value)
    ag_01_request = _gate_request(required_actor=ag_01)
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.REJECTED, actor=ag_01),
            gate_id="gate-1",
            decision=GateDecisionValue.REJECTED,
            actor=ag_01,
            decided_at=NOW,
            decision_ref="decision-2",
            request=ag_01_request,
        )


def test_gate_decision_requires_utc_and_matching_status() -> None:
    approver = _actor(ActorKind.USER, "user-1")
    request = _gate_request(required_actor=approver)
    non_utc = Instant(datetime(2026, 8, 24, 14, 0, tzinfo=timezone(timedelta(hours=2))))
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.APPROVED, actor=approver),
            gate_id="gate-1",
            decision=GateDecisionValue.APPROVED,
            actor=approver,
            decided_at=non_utc,
            decision_ref="decision-1",
            request=request,
        )
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.REJECTED, actor=approver),
            gate_id="gate-1",
            decision=GateDecisionValue.APPROVED,
            actor=approver,
            decided_at=NOW,
            decision_ref="decision-1",
            request=request,
        )


def test_gate_decision_rejects_mismatched_gate_id_and_required_actor() -> None:
    approver = _actor(ActorKind.USER, "user-1")
    request = _gate_request(required_actor=approver)
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.APPROVED, actor=approver),
            gate_id="other-gate",
            decision=GateDecisionValue.APPROVED,
            actor=approver,
            decided_at=NOW,
            decision_ref="decision-1",
            request=request,
        )

    other_actor = _actor(ActorKind.USER, "user-2")
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.APPROVED, actor=other_actor),
            gate_id="gate-1",
            decision=GateDecisionValue.APPROVED,
            actor=other_actor,
            decided_at=NOW,
            decision_ref="decision-1",
            request=request,
        )


def test_gate_decision_rejects_mismatched_correlation_and_step() -> None:
    approver = _actor(ActorKind.USER, "user-1")
    request = _gate_request(required_actor=approver)
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.APPROVED, actor=approver, correlation_id="other"),
            gate_id="gate-1",
            decision=GateDecisionValue.APPROVED,
            actor=approver,
            decided_at=NOW,
            decision_ref="decision-1",
            request=request,
        )
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.APPROVED, actor=approver, step_id="other-step"),
            gate_id="gate-1",
            decision=GateDecisionValue.APPROVED,
            actor=approver,
            decided_at=NOW,
            decision_ref="decision-1",
            request=request,
        )


def test_gate_decision_enforces_request_time_window() -> None:
    approver = _actor(ActorKind.USER, "user-1")
    expires_at = Instant(datetime(2026, 8, 24, 12, 30, tzinfo=UTC))
    request = _gate_request(required_actor=approver, expires_at=expires_at)
    after_expiration = Instant(datetime(2026, 8, 24, 12, 31, tzinfo=UTC))
    before_creation = Instant(datetime(2026, 8, 24, 11, 59, tzinfo=UTC))
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.APPROVED, actor=approver),
            gate_id="gate-1",
            decision=GateDecisionValue.APPROVED,
            actor=approver,
            decided_at=after_expiration,
            decision_ref="decision-1",
            request=request,
        )
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.APPROVED, actor=approver),
            gate_id="gate-1",
            decision=GateDecisionValue.APPROVED,
            actor=approver,
            decided_at=before_creation,
            decision_ref="decision-1",
            request=request,
        )


def test_gate_decision_selected_option_must_match_request_option() -> None:
    approver = _actor(ActorKind.USER, "user-1")
    request = _gate_request(required_actor=approver)
    with pytest.raises(ValueError):
        GateDecision(
            meta=_meta(GateStatus.APPROVED, actor=approver),
            gate_id="gate-1",
            decision=GateDecisionValue.APPROVED,
            actor=approver,
            decided_at=NOW,
            decision_ref="decision-1",
            request=request,
            selected_option={"id": "unknown"},
        )


def test_workflow_event_uses_utc_contract_meta_and_rejects_private_metrics() -> None:
    event = WorkflowEvent(
        meta=_meta(WorkflowStatus.RUNNING),
        event_id="event-1",
        event_type=WorkflowEventType.DELEGATED,
        summary="Step delegated to AG-02",
        refs=("delegation-1",),
        metrics={"attempt": 1},
    )
    assert event.meta.created_at.value.utcoffset() == timedelta(0)
    with pytest.raises(ValueError):
        WorkflowEvent(
            meta=_meta(WorkflowStatus.RUNNING),
            event_id="event-2",
            event_type=WorkflowEventType.REVIEWED,
            summary="Review completed",
            metrics={"private_reasoning_trace": "hidden"},
        )


@pytest.mark.parametrize(
    "unsafe_mapping",
    [
        {"exception": RuntimeError("raw")},
        {"database": {"sql": "select 1"}},
        {"credentials": {"api_key": "secret"}},
        {"providerPayload": {"raw": True}},
        {"analysis": {"private reasoning": "hidden"}},
    ],
)
def test_specialized_contract_mappings_fail_closed(
    unsafe_mapping: Mapping[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        EvidenceRequest(
            meta=_meta(InvocationStatus.PLANNED),
            search_goal="Find evidence",
            filters=unsafe_mapping,
        )
