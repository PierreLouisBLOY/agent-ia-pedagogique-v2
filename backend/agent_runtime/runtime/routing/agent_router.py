from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    AgentId,
    AgentResultStatus,
    DelegationResult,
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    ExecutorKind,
    RecommendedAction,
    StepKind,
    StepSpec,
)
from backend.agent_runtime.contracts.security import (
    SecurityBoundary,
    StructuredContentSecurityAssessment,
)
from backend.agent_runtime.policy import (
    CapabilityAuthorizationPolicy,
    PermissionOperation,
    PolicyDisposition,
    ScopeCheck,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute, UnknownCapabilityError
from backend.agent_runtime.runtime.execution import StepExecutionResult
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.routing.model import (
    ResolvedAgentInput,
    RuntimeRoutingError,
    RuntimeRoutingErrorCode,
)
from backend.agent_runtime.runtime.routing.ports import AgentStepExecutionPort
from backend.agent_runtime.runtime.state import RunState, StepRuntimeStatus
from backend.agent_runtime.security import (
    AgentHandoffSecurityError,
    AgentHandoffSecurityPolicy,
    SensitiveValueRejected,
    StructuredDataLimitError,
    security_event_from_agent_content_assessment,
    security_event_from_agent_handoff_error,
    security_event_from_sensitive_value_rejection,
    security_event_from_structured_limit_error,
)
from backend.agent_runtime.security.runtime_composition import (
    RuntimeSecurityFailureStage,
    RuntimeSecurityViolation,
    SecurityRuntimeGuard,
)
from backend.shared_kernel.time import Instant

_OPERATION_BY_CAPABILITY = {
    "CAP-E01": PermissionOperation.READ,
    "CAP-E02": PermissionOperation.READ,
    "CAP-E03": PermissionOperation.READ,
    "CAP-G01": PermissionOperation.CREATE,
    "CAP-G02": PermissionOperation.TRANSFORM,
    "CAP-G03": PermissionOperation.TRANSFORM,
    "CAP-V01": PermissionOperation.REVIEW,
    "CAP-V02": PermissionOperation.REVIEW,
}


@dataclass(frozen=True, slots=True)
class AgentStepBindings:
    ag_02: AgentStepExecutionPort
    ag_03: AgentStepExecutionPort
    ag_04: AgentStepExecutionPort

    def __post_init__(self) -> None:
        for port in (self.ag_02, self.ag_03, self.ag_04):
            if not isinstance(port, AgentStepExecutionPort):
                raise TypeError("agent bindings must implement AgentStepExecutionPort")

    def get(self, executor: ExecutorKind) -> AgentStepExecutionPort:
        if executor is ExecutorKind.AG_02:
            return self.ag_02
        if executor is ExecutorKind.AG_03:
            return self.ag_03
        if executor is ExecutorKind.AG_04:
            return self.ag_04
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.AGENT_NOT_BOUND)


@dataclass(frozen=True, slots=True)
class AgentStepRouter:
    capability_policy: CapabilityAuthorizationPolicy
    bindings: AgentStepBindings

    def __post_init__(self) -> None:
        if not isinstance(self.capability_policy, CapabilityAuthorizationPolicy):
            raise TypeError("capability_policy must be a CapabilityAuthorizationPolicy")
        if not isinstance(self.bindings, AgentStepBindings):
            raise TypeError("bindings must be AgentStepBindings")

    def authorize(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        resolved: ResolvedAgentInput,
        evaluated_at: Instant,
    ) -> StructuredContentSecurityAssessment:
        invocation = resolved.invocation
        if (
            invocation.source_step != step
            or invocation.agent_id is not step.executor.agent_id
            or invocation.meta.run_id != plan.run_id
            or invocation.meta.step_id != step.step_id
            or invocation.meta.correlation_id != run_state.correlation_id
        ):
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_RUNTIME_CONTEXT)
        if step.kind is not StepKind.AGENT or step.executor.agent_id is None:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_STEP_SHAPE)
        capability_id = step.capability_id
        if capability_id is None or step.permission_scope_ref is None:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_STEP_SHAPE)
        if resolved.permission_scope_ref != step.permission_scope_ref:
            raise RuntimeRoutingError(
                RuntimeRoutingErrorCode.PERMISSION_SCOPE_MISMATCH
            )
        operation = _OPERATION_BY_CAPABILITY.get(capability_id.value)
        if operation is None:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.CAPABILITY_MISMATCH)
        try:
            descriptor = self.capability_policy.capability_registry.get(capability_id)
        except UnknownCapabilityError:
            raise RuntimeRoutingError(
                RuntimeRoutingErrorCode.CAPABILITY_MISMATCH
            ) from None
        target = step.executor.agent_id
        if (
            descriptor.execution_route is not CapabilityExecutionRoute.AGENT
            or descriptor.owner_agent is not target
        ):
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.CAPABILITY_MISMATCH)
        scope = resolved.permission_scope
        check = ScopeCheck(
            principal=scope.principal,
            capability_id=capability_id,
            operation=operation,
            resource_scope=scope.resource_scope,
            constraints=scope.constraints,
            requested_budget=step.budget,
            satisfied_gate_requirements=resolved.satisfied_gate_requirements,
            evaluated_at=evaluated_at,
            revoked=resolved.scope_revoked,
        )
        try:
            decision = self.capability_policy.evaluate(
                agent_id=AgentId.AG_01,
                scope=scope,
                check=check,
                facts=resolved.policy_facts,
            )
        except Exception:
            raise RuntimeRoutingError(
                RuntimeRoutingErrorCode.AGENT_NOT_AUTHORIZED
            ) from None
        if (
            decision.disposition is not PolicyDisposition.DELEGATE
            or decision.target_agent is not target
            or decision.route is not CapabilityExecutionRoute.AGENT
        ):
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.AGENT_NOT_AUTHORIZED)
        return AgentHandoffSecurityPolicy(self.capability_policy).secure_invocation(
            delegator=AgentId.AG_01,
            parent_scope=scope,
            invocation=invocation,
            evaluated_at=evaluated_at,
            parent_revoked=resolved.scope_revoked,
        )

    def route(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        resolved: ResolvedAgentInput,
        attempt: int,
        now: Instant,
    ) -> StepExecutionResult:
        self.authorize(
            plan=plan,
            step=step,
            run_state=run_state,
            resolved=resolved,
            evaluated_at=now,
        )
        if resolved.invocation.attempt != attempt:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_RUNTIME_CONTEXT)
        port = self.bindings.get(step.executor.kind)
        result = port.execute(
            plan=plan,
            step=step,
            run_state=run_state,
            invocation=resolved.invocation,
            attempt=attempt,
            now=now,
        )
        if not isinstance(result, DelegationResult):
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT)
        try:
            validated = AgentHandoffSecurityPolicy(self.capability_policy).secure(
                delegator=AgentId.AG_01,
                parent_scope=resolved.permission_scope,
                invocation=resolved.invocation,
                result=result,
                evaluated_at=now,
                parent_revoked=resolved.scope_revoked,
            )
        except AgentHandoffSecurityError as error:
            handoff_event = security_event_from_agent_handoff_error(
                error,
                schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                event_id=_security_event_id(step.step_id, attempt),
                occurred_at=now,
                run_id=plan.run_id,
                correlation_id=run_state.correlation_id,
                step_id=step.step_id,
            )
            raise RuntimeSecurityViolation(
                SecurityRuntimeGuard().handoff_rejected(),
                stage=RuntimeSecurityFailureStage.POST_EFFECT,
                event=handoff_event,
            ) from None
        except SensitiveValueRejected as error:
            sensitive_event = security_event_from_sensitive_value_rejection(
                error,
                schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                event_id=_security_event_id(step.step_id, attempt),
                occurred_at=now,
                run_id=plan.run_id,
                correlation_id=run_state.correlation_id,
                boundary=SecurityBoundary.AGENT,
                step_id=step.step_id,
            )
            raise RuntimeSecurityViolation(
                SecurityRuntimeGuard().from_error(error),
                stage=RuntimeSecurityFailureStage.POST_EFFECT,
                event=sensitive_event,
            ) from None
        except StructuredDataLimitError as error:
            limit_event = security_event_from_structured_limit_error(
                error,
                schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                event_id=_security_event_id(step.step_id, attempt),
                occurred_at=now,
                run_id=plan.run_id,
                correlation_id=run_state.correlation_id,
                boundary=SecurityBoundary.AGENT,
                step_id=step.step_id,
            )
            raise RuntimeSecurityViolation(
                SecurityRuntimeGuard().from_error(error),
                stage=RuntimeSecurityFailureStage.POST_EFFECT,
                event=limit_event,
            ) from None
        assessment = SecurityRuntimeGuard().compose(
            (validated.context_assessment, validated.output_assessment)
        )
        if not assessment.launchable:
            content_event = security_event_from_agent_content_assessment(
                validated.output_assessment,
                schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                event_id=_security_event_id(step.step_id, attempt),
                occurred_at=now,
                run_id=plan.run_id,
                correlation_id=run_state.correlation_id,
                step_id=step.step_id,
                hostile_propagation=True,
            )
            raise RuntimeSecurityViolation(
                assessment,
                stage=RuntimeSecurityFailureStage.POST_EFFECT,
                event=content_event,
            )
        return _step_result(result, attempt=attempt)


def _step_result(
    result: DelegationResult[object], *, attempt: int
) -> StepExecutionResult:
    agent_result = result.agent_result
    status = {
        AgentResultStatus.SUCCEEDED: StepRuntimeStatus.SUCCEEDED,
        AgentResultStatus.PARTIAL: StepRuntimeStatus.PARTIAL,
        AgentResultStatus.FAILED: StepRuntimeStatus.FAILED,
        AgentResultStatus.CANCELLED: StepRuntimeStatus.CANCELLED,
        AgentResultStatus.ESCALATED: StepRuntimeStatus.FAILED,
    }[agent_result.meta.status]
    error = agent_result.error
    if status is StepRuntimeStatus.FAILED and error is None:
        error = ErrorEnvelope(
            error_code="AGENT_EXECUTION_STOPPED",
            category=ErrorCategory.CANCELLED,
            source=ErrorSource.AGENT,
            retryable=False,
            severity=ErrorSeverity.ERROR,
            message="agent execution stopped",
            step_id=agent_result.meta.step_id,
            attempt=attempt,
            effect_state=EffectState.NONE,
            recommended_action=RecommendedAction.STOP,
        )
    return StepExecutionResult(
        status=status,
        result_refs=agent_result.artifact_refs,
        metrics=agent_result.metrics,
        error=error,
    )


def _security_event_id(step_id: str, attempt: int) -> str:
    return f"security-agent:{attempt}:{step_id[:80]}"
