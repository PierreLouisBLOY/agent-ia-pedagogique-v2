from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts import StepKind, StepSpec
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
    RuntimeRoutingError,
    RuntimeRoutingErrorCode,
)
from backend.agent_runtime.runtime.routing.ports import RuntimeRoutingResolverPort
from backend.agent_runtime.runtime.state import RunState
from backend.shared_kernel.time import Instant

_CAP_A02 = "CAP-A02"


@dataclass(frozen=True, slots=True)
class RoutingPreLaunchGuard:
    resolver: RuntimeRoutingResolverPort
    gate_engine: GateEngine
    tool_call_policy: ToolCallPolicy
    agent_router: AgentStepRouter
    declared_sandbox_profile_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.resolver, RuntimeRoutingResolverPort):
            raise TypeError("resolver must implement RuntimeRoutingResolverPort")
        if not isinstance(self.gate_engine, GateEngine):
            raise TypeError("gate_engine must be a GateEngine")
        if not isinstance(self.tool_call_policy, ToolCallPolicy):
            raise TypeError("tool_call_policy must be a ToolCallPolicy")
        if not isinstance(self.agent_router, AgentStepRouter):
            raise TypeError("agent_router must be an AgentStepRouter")
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
                return self._check_gate(plan, step, run_state, now)
            if step.kind is StepKind.TOOL:
                return self._check_tool(plan, step, run_state, now)
            if step.kind is StepKind.AGENT:
                resolved = self.resolver.resolve_agent_input(
                    plan=plan, step=step, run_state=run_state
                )
                if type(resolved) is not ResolvedAgentInput:
                    raise TypeError("invalid agent resolution")
                self.agent_router.authorize(
                    step=step,
                    resolved=resolved,
                    evaluated_at=now,
                )
            return PreLaunchDecision(PreLaunchDisposition.ALLOW)
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
        if decision.disposition is ToolCallDisposition.ALLOW:
            return PreLaunchDecision(PreLaunchDisposition.ALLOW)
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
