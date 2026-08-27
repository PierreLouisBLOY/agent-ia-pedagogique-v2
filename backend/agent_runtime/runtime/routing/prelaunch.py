from __future__ import annotations

from dataclasses import dataclass, field

from backend.agent_runtime.application_routing import assess_use_case_request_security
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    SecurityBoundary,
    StepKind,
    StepSpec,
    StructuredContentSecurityAssessment,
)
from backend.agent_runtime.gates import GateEngine, GateResolutionDisposition
from backend.agent_runtime.policy import PolicyDisposition, ToolCallDisposition, ToolCallPolicy
from backend.agent_runtime.runtime.execution import (
    PreLaunchDecision,
    PreLaunchDisposition,
)
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.routing._validation import (
    validate_gate_binding,
    validate_request_identity,
    validate_runtime_context,
)
from backend.agent_runtime.runtime.routing.agent_router import AgentStepRouter
from backend.agent_runtime.runtime.routing.model import (
    ResolvedAgentInput,
    ResolvedToolInput,
    ResolvedUseCaseInput,
    RuntimeRoutingError,
    RuntimeRoutingErrorCode,
)
from backend.agent_runtime.runtime.routing.ports import RuntimeRoutingResolverPort
from backend.agent_runtime.runtime.state import RunState
from backend.agent_runtime.security import (
    AgentHandoffSecurityError,
    SensitiveValueRejected,
    StructuredDataLimitError,
    security_event_from_agent_handoff_error,
    security_event_from_sensitive_value_rejection,
    security_event_from_structured_assessment,
    security_event_from_structured_limit_error,
)
from backend.agent_runtime.security.runtime_composition import (
    RuntimeSecurityAssessment,
    SecurityRuntimeGuard,
)
from backend.agent_runtime.tools import assess_tool_arguments_security
from backend.shared_kernel.time import Instant

_CAP_A02 = "CAP-A02"


@dataclass(frozen=True, slots=True)
class RoutingPreLaunchGuard:
    resolver: RuntimeRoutingResolverPort
    gate_engine: GateEngine
    tool_call_policy: ToolCallPolicy
    agent_router: AgentStepRouter
    declared_sandbox_profile_ids: tuple[str, ...]
    security_guard: SecurityRuntimeGuard = field(default_factory=SecurityRuntimeGuard)

    def __post_init__(self) -> None:
        if not isinstance(self.resolver, RuntimeRoutingResolverPort):
            raise TypeError("resolver must implement RuntimeRoutingResolverPort")
        if not isinstance(self.gate_engine, GateEngine):
            raise TypeError("gate_engine must be a GateEngine")
        if not isinstance(self.tool_call_policy, ToolCallPolicy):
            raise TypeError("tool_call_policy must be a ToolCallPolicy")
        if not isinstance(self.agent_router, AgentStepRouter):
            raise TypeError("agent_router must be an AgentStepRouter")
        if not isinstance(self.security_guard, SecurityRuntimeGuard):
            raise TypeError("security_guard must be a SecurityRuntimeGuard")
        if not isinstance(self.declared_sandbox_profile_ids, tuple) or any(
            not isinstance(value, str) or not value
            for value in self.declared_sandbox_profile_ids
        ):
            raise TypeError("declared_sandbox_profile_ids must be non-empty strings")

    def check(
        self,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision:
        try:
            validate_runtime_context(
                plan=plan,
                step=step,
                run_state=run_state,
                capability_policy=self.agent_router.capability_policy,
            )
            if step.kind is StepKind.GATE or (
                step.kind is StepKind.USE_CASE
                and step.capability_id is not None
                and step.capability_id.value == _CAP_A02
            ):
                decision = self._check_gate(plan, step, run_state, now)
                if (
                    step.kind is StepKind.USE_CASE
                    and decision.disposition is PreLaunchDisposition.ALLOW
                ):
                    return self._check_use_case_security(plan, step, run_state, now)
                return decision
            if step.kind is StepKind.TOOL:
                return self._check_tool(plan, step, run_state, now)
            if step.kind is StepKind.USE_CASE:
                return self._check_use_case_security(plan, step, run_state, now)
            if step.kind is StepKind.AGENT:
                resolved = self.resolver.resolve_agent_input(
                    plan=plan, step=step, run_state=run_state
                )
                if type(resolved) is not ResolvedAgentInput:
                    raise TypeError("invalid agent resolution")
                assessment = self.agent_router.authorize(
                    plan=plan,
                    step=step,
                    run_state=run_state,
                    resolved=resolved,
                    evaluated_at=now,
                )
                return self._security_decision(
                    assessment,
                    plan=plan,
                    step=step,
                    run_state=run_state,
                    now=now,
                )
            return PreLaunchDecision(PreLaunchDisposition.ALLOW)
        except AgentHandoffSecurityError as error:
            security_assessment = self.security_guard.handoff_rejected()
            event = security_event_from_agent_handoff_error(
                error,
                schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                event_id=_security_event_id(step, "handoff"),
                occurred_at=now,
                run_id=plan.run_id,
                correlation_id=run_state.correlation_id,
                step_id=step.step_id,
            )
            return PreLaunchDecision(
                PreLaunchDisposition.DENY,
                security_assessment.reason_codes[0].value,
                security_assessment,
                (event,),
            )
        except (SensitiveValueRejected, StructuredDataLimitError) as error:
            security_assessment = self.security_guard.from_error(error)
            if isinstance(error, SensitiveValueRejected):
                security_event = (
                security_event_from_sensitive_value_rejection(
                    error,
                    schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                    event_id=_security_event_id(step, "sensitive"),
                    occurred_at=now,
                    run_id=plan.run_id,
                    correlation_id=run_state.correlation_id,
                    boundary=_boundary(step),
                    step_id=step.step_id,
                )
                )
            else:
                security_event = security_event_from_structured_limit_error(
                    error,
                    schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
                    event_id=_security_event_id(step, "limit"),
                    occurred_at=now,
                    run_id=plan.run_id,
                    correlation_id=run_state.correlation_id,
                    boundary=_boundary(step),
                    step_id=step.step_id,
                )
            return PreLaunchDecision(
                PreLaunchDisposition.DENY,
                security_assessment.reason_codes[0].value,
                security_assessment,
                (security_event,),
            )
        except Exception:
            return PreLaunchDecision(
                PreLaunchDisposition.DENY,
                "RUNTIME_ROUTING_DENIED",
            )

    def _check_gate(
        self, plan: Plan, step: StepSpec, run_state: RunState, now: Instant
    ) -> PreLaunchDecision:
        resolved = self.resolver.resolve_gate_input(
            plan=plan, step=step, run_state=run_state
        )
        validate_gate_binding(
            plan=plan, step=step, run_state=run_state, resolved=resolved
        )
        try:
            resolution = self.gate_engine.evaluate(request=resolved.request, now=now)
        except Exception:
            return PreLaunchDecision(
                PreLaunchDisposition.DENY,
                "GATE_EVALUATION_FAILED",
            )
        if resolution.disposition in {
            GateResolutionDisposition.WAITING,
            GateResolutionDisposition.DEFERRED,
        }:
            return PreLaunchDecision(
                PreLaunchDisposition.WAITING_GATE,
                f"GATE_{resolution.disposition.value}",
            )
        if resolution.disposition in {
            GateResolutionDisposition.REJECTED,
            GateResolutionDisposition.EXPIRED,
        }:
            return PreLaunchDecision(
                PreLaunchDisposition.DENY,
                f"GATE_{resolution.disposition.value}",
            )
        if resolution.disposition is GateResolutionDisposition.APPROVED:
            return PreLaunchDecision(PreLaunchDisposition.ALLOW)
        return PreLaunchDecision(PreLaunchDisposition.DENY, "GATE_INVALID_STATE")

    def _check_tool(
        self, plan: Plan, step: StepSpec, run_state: RunState, now: Instant
    ) -> PreLaunchDecision:
        resolved = self.resolver.resolve_tool_input(
            plan=plan, step=step, run_state=run_state
        )
        if type(resolved) is not ResolvedToolInput:
            raise TypeError("invalid tool resolution")
        if resolved.permission_scope_ref != step.permission_scope_ref:
            raise RuntimeRoutingError(
                RuntimeRoutingErrorCode.PERMISSION_SCOPE_MISMATCH
            )
        validate_request_identity(
            plan=plan, step=step, run_state=run_state, request=resolved.request
        )
        if resolved.request.capability_id != step.capability_id:
            raise ValueError("capability mismatch")
        if resolved.context.root_ref.run_id != plan.run_id:
            raise ValueError("sandbox root mismatch")
        decision = self.tool_call_policy.evaluate(
            agent_id=plan.created_by,
            request=resolved.request,
            evaluated_at=now,
            facts=resolved.policy_facts,
            declared_sandbox_profile_ids=self.declared_sandbox_profile_ids,
            satisfied_gate_requirements=resolved.satisfied_gate_requirements,
            scope_revoked=resolved.scope_revoked,
        )
        source_assessment = assess_tool_arguments_security(resolved.request)
        security_assessment = self.security_guard.compose((source_assessment,))
        if not security_assessment.launchable:
            return self._runtime_security_decision(
                security_assessment,
                source_assessment=source_assessment,
                plan=plan,
                step=step,
                run_state=run_state,
                now=now,
            )
        if decision.disposition is ToolCallDisposition.ALLOW:
            return PreLaunchDecision(
                PreLaunchDisposition.ALLOW,
                security_assessment=security_assessment,
            )
        if (
            decision.capability_decision is not None
            and decision.capability_decision.disposition
            is PolicyDisposition.CONDITION_REQUIRED
        ):
            return PreLaunchDecision(
                PreLaunchDisposition.CONDITION_REQUIRED,
                "TOOL_CONDITION_REQUIRED",
            )
        return PreLaunchDecision(PreLaunchDisposition.DENY, "TOOL_NOT_ALLOWED")

    def _check_use_case_security(
        self, plan: Plan, step: StepSpec, run_state: RunState, now: Instant
    ) -> PreLaunchDecision:
        resolved = self.resolver.resolve_use_case_input(
            plan=plan, step=step, run_state=run_state
        )
        if type(resolved) is not ResolvedUseCaseInput:
            raise TypeError("invalid use-case resolution")
        if resolved.permission_scope_ref != step.permission_scope_ref:
            raise RuntimeRoutingError(
                RuntimeRoutingErrorCode.PERMISSION_SCOPE_MISMATCH
            )
        validate_request_identity(
            plan=plan, step=step, run_state=run_state, request=resolved.request
        )
        source_assessments = assess_use_case_request_security(resolved.request)
        assessment = self.security_guard.compose(source_assessments)
        return self._runtime_security_decision(
            assessment,
            source_assessment=next(
                (
                    item
                    for item in source_assessments
                    if item.structural_locations
                    or item.disposition.value
                    not in {"PASS_AS_DATA", "ISOLATE_AS_DATA"}
                ),
                source_assessments[0],
            ),
            plan=plan,
            step=step,
            run_state=run_state,
            now=now,
        )

    def _security_decision(
        self,
        source_assessment: StructuredContentSecurityAssessment,
        *,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision:
        return self._runtime_security_decision(
            self.security_guard.compose((source_assessment,)),
            source_assessment=source_assessment,
            plan=plan,
            step=step,
            run_state=run_state,
            now=now,
        )

    def _runtime_security_decision(
        self,
        assessment: RuntimeSecurityAssessment,
        *,
        source_assessment: StructuredContentSecurityAssessment,
        plan: Plan,
        step: StepSpec,
        run_state: RunState,
        now: Instant,
    ) -> PreLaunchDecision:
        if assessment.launchable:
            return PreLaunchDecision(
                PreLaunchDisposition.ALLOW,
                security_assessment=assessment,
            )
        event = security_event_from_structured_assessment(
            source_assessment,
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            event_id=_security_event_id(step, "content"),
            occurred_at=now,
            run_id=plan.run_id,
            correlation_id=run_state.correlation_id,
            step_id=step.step_id,
        )
        return PreLaunchDecision(
            PreLaunchDisposition.DENY,
            assessment.reason_codes[0].value,
            assessment,
            () if event is None else (event,),
        )


def _security_event_id(step: StepSpec, suffix: str) -> str:
    return f"security-prelaunch:{suffix}:{step.step_id[:72]}"


def _boundary(step: StepSpec) -> SecurityBoundary:
    if step.kind is StepKind.TOOL:
        return SecurityBoundary.TOOL
    if step.kind is StepKind.USE_CASE:
        return SecurityBoundary.APPLICATION
    if step.kind is StepKind.AGENT:
        return SecurityBoundary.AGENT
    return SecurityBoundary.RUNTIME
