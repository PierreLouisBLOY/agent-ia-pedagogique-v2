from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.agent_runtime.contracts import (
    ActorKind,
    ActorRef,
    AgentId,
    AgentInvocation,
    AgentResult,
    AgentResultStatus,
    AutonomyLevel,
    BudgetSpec,
    ContractMeta,
    DelegationEnvelope,
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    ExecutorKind,
    ExecutorRef,
    FailurePolicy,
    InvocationStatus,
    PermissionScope,
    RecommendedAction,
    RuntimeMode,
    StepKind,
    StepSpec,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


def _actor() -> ActorRef:
    return ActorRef(kind=ActorKind.AGENT, actor_id="agent-runtime")


def _meta(status: InvocationStatus | AgentResultStatus) -> ContractMeta[object]:
    return ContractMeta(
        schema_version="12.3-C1",
        run_id="run-1",
        step_id="step-1",
        parent_step_id=None,
        correlation_id=CorrelationId("corr-1"),
        created_at=Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC)),
        actor=_actor(),
        status=status,
        trace_flags={"sampled": True},
    )


def _permission_scope() -> PermissionScope:
    return PermissionScope(
        principal=_actor(),
        capability_ids=(CapabilityId("course.generate"),),
        operations=("invoke",),
        resource_scope={"course": "course-1"},
        constraints={"max_depth": 1},
    )


def _agent_step(agent_id: AgentId = AgentId.AG_02) -> StepSpec:
    executor_by_agent = {
        AgentId.AG_02: ExecutorKind.AG_02,
        AgentId.AG_03: ExecutorKind.AG_03,
        AgentId.AG_04: ExecutorKind.AG_04,
    }
    return StepSpec(
        step_id="step-1",
        kind=StepKind.AGENT,
        capability_id=CapabilityId("course.generate"),
        executor=ExecutorRef(executor_by_agent[agent_id]),
        objective="Generate a course outline",
        input_refs=("course-input",),
        depends_on=(),
        permission_scope_ref="permission-1",
        budget=BudgetSpec(max_tokens=100),
        success_criteria={"quality": "accepted"},
        failure_policy=FailurePolicy.RETRY,
        output_contract={"type": "outline"},
    )


def _delegation(agent_id: AgentId = AgentId.AG_02) -> DelegationEnvelope:
    return DelegationEnvelope(
        delegation_id="delegation-1",
        source_step=_agent_step(agent_id),
        target_agent=agent_id,
        context_slice={"locale": "fr-FR"},
        evidence_refs=("evidence-1",),
        constraints={"max_depth": 1},
        permission_scope=_permission_scope(),
        trace_context={"trace": {"sampled": True}},
    )


def _error() -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="AG_VALIDATION",
        category=ErrorCategory.VALIDATION,
        source=ErrorSource.AGENT,
        retryable=False,
        severity=ErrorSeverity.ERROR,
        message="Invalid agent input",
        step_id="step-1",
        attempt=1,
        effect_state=EffectState.NONE,
        recommended_action=RecommendedAction.STOP,
    )


def test_agent_runtime_enums_have_exact_values() -> None:
    assert [item.value for item in ActorKind] == [
        "USER",
        "AGENT",
        "APPLICATION",
        "TOOL",
        "SYSTEM",
        "PROVIDER",
    ]
    assert [item.value for item in AgentId] == ["AG-01", "AG-02", "AG-03", "AG-04"]
    assert [item.value for item in AutonomyLevel] == [
        "AUT-L0",
        "AUT-L1",
        "AUT-L2",
        "AUT-L3",
        "AUT-L4",
        "AUT-L5",
    ]
    assert [item.value for item in RuntimeMode] == [
        "MODE-DIRECT",
        "MODE-ASSISTED",
        "MODE-ORCHESTRATED",
        "MODE-HIGH_ASSURANCE",
    ]
    assert [item.value for item in StepKind] == [
        "agent",
        "use_case",
        "tool",
        "gate",
        "join",
        "decision",
    ]
    assert [item.value for item in FailurePolicy] == [
        "retry",
        "replan",
        "escalate",
        "stop",
    ]
    assert [item.value for item in ExecutorKind] == [
        "AG-02",
        "AG-03",
        "AG-04",
        "APPLICATION",
        "UTILITY",
    ]
    assert [item.value for item in InvocationStatus] == [
        "planned",
        "running",
        "succeeded",
        "partial",
        "failed",
        "cancelled",
        "escalated",
    ]
    assert [item.value for item in AgentResultStatus] == [
        "succeeded",
        "partial",
        "failed",
        "cancelled",
        "escalated",
    ]


def test_actor_ref_and_ids_require_non_empty_values() -> None:
    with pytest.raises(ValueError):
        ActorRef(kind=ActorKind.USER, actor_id=" ")
    with pytest.raises(ValueError):
        StepSpec(
            step_id="",
            kind=StepKind.TOOL,
            capability_id=None,
            executor=ExecutorRef(ExecutorKind.UTILITY),
            objective="Do work",
            output_contract={"type": "none"},
        )


def test_contract_meta_requires_utc_created_at() -> None:
    with pytest.raises(ValueError):
        ContractMeta(
            schema_version="12.3-C1",
            run_id="run-1",
            step_id="step-1",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-1"),
            created_at=Instant(
                datetime(2026, 8, 24, 14, 0, tzinfo=timezone(timedelta(hours=2)))
            ),
            actor=_actor(),
            status=InvocationStatus.PLANNED,
        )


def test_contract_meta_trace_flags_are_immutable_and_private_keys_rejected() -> None:
    meta = ContractMeta(
        schema_version="12.3-C1",
        run_id="run-1",
        step_id="step-1",
        parent_step_id=None,
        correlation_id=CorrelationId("corr-1"),
        created_at=Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC)),
        actor=_actor(),
        status=InvocationStatus.PLANNED,
        trace_flags={"nested": {"token_count": 4}},
    )

    nested = meta.trace_flags["nested"]
    assert isinstance(nested, Mapping)
    with pytest.raises(TypeError):
        nested["token_count"] = 5  # type: ignore[index]
    with pytest.raises(ValueError):
        ContractMeta(
            schema_version="12.3-C1",
            run_id="run-1",
            step_id="step-1",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-1"),
            created_at=Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC)),
            actor=_actor(),
            status=InvocationStatus.PLANNED,
            trace_flags={"system_prompt": "private"},
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("max_tokens", -1),
        ("max_runtime_seconds", -1),
        ("max_retries", -1),
        ("max_steps", -1),
        ("max_tool_calls", -1),
    ],
)
def test_budget_spec_rejects_negative_integer_bounds(
    field_name: str, value: int
) -> None:
    with pytest.raises(ValueError):
        BudgetSpec(**{field_name: value})


def test_budget_spec_uses_decimal_for_non_negative_costs() -> None:
    assert BudgetSpec(max_cost=Decimal("0.12")).max_cost == Decimal("0.12")
    with pytest.raises(ValueError):
        BudgetSpec(max_cost=Decimal("-0.01"))


def test_permission_scope_defaults_to_non_delegable_and_freezes_data() -> None:
    scope = PermissionScope(
        principal=_actor(),
        constraints={"limits": {"token_budget": 100}},
        deny_rules=({"operation": "delete"},),
    )

    assert scope.delegable is False
    limits = scope.constraints["limits"]
    assert isinstance(limits, Mapping)
    with pytest.raises(TypeError):
        limits["token_budget"] = 50  # type: ignore[index]


def test_permission_scope_requires_coherent_expiration() -> None:
    valid_from = Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))
    expires_at = Instant(datetime(2026, 8, 24, 11, 59, tzinfo=UTC))

    with pytest.raises(ValueError):
        PermissionScope(
            principal=_actor(),
            valid_from=valid_from,
            expires_at=expires_at,
        )


def test_step_spec_is_immutable_and_cannot_depend_on_itself() -> None:
    step = _agent_step()

    with pytest.raises(FrozenInstanceError):
        step.objective = "Change"  # type: ignore[misc]
    with pytest.raises(ValueError):
        StepSpec(
            step_id="step-1",
            kind=StepKind.TOOL,
            capability_id=None,
            executor=ExecutorRef(ExecutorKind.UTILITY),
            objective="Do work",
            depends_on=("step-1",),
            output_contract={"type": "none"},
        )


def test_delegation_envelope_refuses_ag_01() -> None:
    with pytest.raises(ValueError):
        DelegationEnvelope(
            delegation_id="delegation-1",
            source_step=_agent_step(),
            target_agent=AgentId.AG_01,
            context_slice={},
            evidence_refs=(),
            constraints={},
            permission_scope=_permission_scope(),
        )


def test_delegation_envelope_requires_agent_step_and_coherent_executor() -> None:
    non_agent_step = StepSpec(
        step_id="step-1",
        kind=StepKind.TOOL,
        capability_id=CapabilityId("tool.run"),
        executor=ExecutorRef(ExecutorKind.UTILITY),
        objective="Run a tool",
        output_contract={"type": "tool-result"},
    )
    with pytest.raises(ValueError):
        DelegationEnvelope(
            delegation_id="delegation-1",
            source_step=non_agent_step,
            target_agent=AgentId.AG_02,
            context_slice={},
            evidence_refs=(),
            constraints={},
            permission_scope=_permission_scope(),
        )
    with pytest.raises(ValueError):
        DelegationEnvelope(
            delegation_id="delegation-1",
            source_step=_agent_step(AgentId.AG_02),
            target_agent=AgentId.AG_03,
            context_slice={},
            evidence_refs=(),
            constraints={},
            permission_scope=_permission_scope(),
        )


def test_agent_invocation_composes_same_step_and_delegation() -> None:
    delegation = _delegation()
    invocation = AgentInvocation(
        meta=_meta(InvocationStatus.PLANNED),
        invocation_id="invocation-1",
        source_step=delegation.source_step,
        delegation=delegation,
        agent_id=AgentId.AG_02,
        attempt=1,
        autonomy_level=AutonomyLevel.AUT_L2,
        runtime_mode=RuntimeMode.MODE_ORCHESTRATED,
    )

    assert invocation.source_step is delegation.source_step
    with pytest.raises(ValueError):
        AgentInvocation(
            meta=_meta(InvocationStatus.PLANNED),
            invocation_id="invocation-2",
            source_step=_agent_step(AgentId.AG_03),
            delegation=delegation,
            agent_id=AgentId.AG_02,
            attempt=1,
            autonomy_level=AutonomyLevel.AUT_L2,
            runtime_mode=RuntimeMode.MODE_ORCHESTRATED,
        )


def test_agent_invocation_attempt_must_be_positive() -> None:
    with pytest.raises(ValueError):
        AgentInvocation(
            meta=_meta(InvocationStatus.PLANNED),
            invocation_id="invocation-1",
            source_step=_agent_step(),
            delegation=None,
            agent_id=AgentId.AG_02,
            attempt=0,
            autonomy_level=AutonomyLevel.AUT_L1,
            runtime_mode=RuntimeMode.MODE_DIRECT,
        )


def test_agent_result_failure_and_stop_reason_rules() -> None:
    with pytest.raises(ValueError):
        AgentResult[object](
            meta=_meta(AgentResultStatus.FAILED),
            invocation_id="invocation-1",
        )
    with pytest.raises(ValueError):
        AgentResult[object](
            meta=_meta(AgentResultStatus.CANCELLED),
            invocation_id="invocation-1",
        )
    with pytest.raises(ValueError):
        AgentResult[object](
            meta=_meta(AgentResultStatus.ESCALATED),
            invocation_id="invocation-1",
        )

    assert (
        AgentResult[object](
            meta=_meta(AgentResultStatus.FAILED),
            invocation_id="invocation-1",
            error=_error(),
        ).error
        is not None
    )


def test_error_envelope_enums_have_exact_values_and_unknown_effect_is_allowed() -> None:
    assert [item.value for item in ErrorCategory] == [
        "validation",
        "domain",
        "permission",
        "gate",
        "transient",
        "provider",
        "tool",
        "budget",
        "conflict",
        "quality",
        "cancelled",
        "unknown",
    ]
    assert [item.value for item in ErrorSeverity] == [
        "info",
        "warning",
        "error",
        "critical",
    ]
    assert [item.value for item in ErrorSource] == [
        "agent",
        "application",
        "tool",
        "provider",
    ]
    assert [item.value for item in EffectState] == [
        "none",
        "unknown",
        "committed",
        "partial",
    ]
    assert [item.value for item in RecommendedAction] == [
        "retry",
        "replan",
        "escalate",
        "stop",
        "inspect",
    ]
    error = ErrorEnvelope(
        error_code="UNKNOWN_EFFECT",
        category=ErrorCategory.UNKNOWN,
        source=ErrorSource.APPLICATION,
        retryable=True,
        severity=ErrorSeverity.WARNING,
        message="Effect unknown",
        step_id="step-1",
        attempt=1,
        effect_state=EffectState.UNKNOWN,
        recommended_action=RecommendedAction.INSPECT,
    )

    assert error.effect_state is EffectState.UNKNOWN


def test_error_envelope_rejects_raw_exceptions_and_private_agent_data() -> None:
    with pytest.raises(TypeError):
        ErrorEnvelope(
            error_code="RAW",
            category=ErrorCategory.TOOL,
            source=ErrorSource.TOOL,
            retryable=False,
            severity=ErrorSeverity.ERROR,
            message="Raw exception",
            step_id="step-1",
            attempt=1,
            effect_state=EffectState.UNKNOWN,
            details={"exception": RuntimeError("raw")},
        )
    with pytest.raises(ValueError):
        ErrorEnvelope(
            error_code="PRIVATE",
            category=ErrorCategory.UNKNOWN,
            source=ErrorSource.AGENT,
            retryable=False,
            severity=ErrorSeverity.ERROR,
            message="Private data",
            step_id="step-1",
            attempt=1,
            effect_state=EffectState.NONE,
            details={"private_reasoning": "hidden"},
        )


def test_provider_neutral_token_metrics_are_accepted_and_frozen() -> None:
    result = AgentResult[dict[str, object]](
        meta=_meta(AgentResultStatus.SUCCEEDED),
        invocation_id="invocation-1",
        payload={"ok": True},
        metrics={
            "token_count": 30,
            "input_tokens": 10,
            "output_tokens": 20,
            "token_budget": 100,
            "search_query": "programme maths",
            "query_kind": "semantic",
        },
        warnings=({"code": "LOW_CONFIDENCE", "details": {"token_count": 2}},),
    )

    assert result.metrics["token_count"] == 30
    with pytest.raises(TypeError):
        result.metrics["token_count"] = 31  # type: ignore[index]


def test_agent_result_rejects_free_text_warning_payloads() -> None:
    with pytest.raises(TypeError):
        AgentResult[object](
            meta=_meta(AgentResultStatus.SUCCEEDED),
            invocation_id="invocation-1",
            warnings=("plain warning",),  # type: ignore[arg-type]
        )
