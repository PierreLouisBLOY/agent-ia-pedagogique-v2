from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts import AgentId, ExecutorKind, StepKind, StepSpec
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
from backend.agent_runtime.runtime.state import RunState
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
        step: StepSpec,
        resolved: ResolvedAgentInput,
        evaluated_at: Instant,
    ) -> None:
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
        self.authorize(step=step, resolved=resolved, evaluated_at=now)
        port = self.bindings.get(step.executor.kind)
        result = port.execute(
            plan=plan,
            step=step,
            run_state=run_state,
            attempt=attempt,
            now=now,
        )
        if type(result) is not StepExecutionResult:
            raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_BOUNDARY_RESULT)
        return result
