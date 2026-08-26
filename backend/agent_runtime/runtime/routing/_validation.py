from __future__ import annotations

from backend.agent_runtime.contracts import (
    ExecutorKind,
    GateRequest,
    StepKind,
    StepSpec,
    ToolCallRequest,
    UseCaseRequest,
)
from backend.agent_runtime.policy import CapabilityAuthorizationPolicy
from backend.agent_runtime.registry import CapabilityExecutionRoute, UnknownCapabilityError
from backend.agent_runtime.runtime.planning import Plan
from backend.agent_runtime.runtime.routing.model import (
    ResolvedGateInput,
    RuntimeRoutingError,
    RuntimeRoutingErrorCode,
)
from backend.agent_runtime.runtime.state import RunState

_EXECUTOR_BY_KIND = {
    StepKind.USE_CASE: ExecutorKind.APPLICATION,
    StepKind.TOOL: ExecutorKind.UTILITY,
    StepKind.GATE: ExecutorKind.RUNTIME,
    StepKind.JOIN: ExecutorKind.RUNTIME,
    StepKind.DECISION: ExecutorKind.RUNTIME,
}
_ROUTE_BY_KIND = {
    StepKind.USE_CASE: CapabilityExecutionRoute.APPLICATION,
    StepKind.TOOL: CapabilityExecutionRoute.UTILITY,
    StepKind.AGENT: CapabilityExecutionRoute.AGENT,
    StepKind.GATE: CapabilityExecutionRoute.RUNTIME,
    StepKind.JOIN: CapabilityExecutionRoute.RUNTIME,
    StepKind.DECISION: CapabilityExecutionRoute.RUNTIME,
}


def validate_runtime_context(
    *,
    plan: Plan,
    step: StepSpec,
    run_state: RunState,
    capability_policy: CapabilityAuthorizationPolicy,
) -> None:
    if type(plan) is not Plan or type(step) is not StepSpec or type(run_state) is not RunState:
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_RUNTIME_CONTEXT)
    if (
        run_state.run_id != plan.run_id
        or run_state.plan_id != plan.plan_id
        or run_state.plan_version != plan.plan_version
        or run_state.workflow_kind != plan.workflow_kind
        or step.step_id not in run_state.step_states
        or sum(candidate == step for candidate in plan.steps) != 1
    ):
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_RUNTIME_CONTEXT)
    expected_executor = _EXECUTOR_BY_KIND.get(step.kind)
    if expected_executor is not None and step.executor.kind is not expected_executor:
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_STEP_SHAPE)
    if step.kind is StepKind.AGENT and step.executor.agent_id is None:
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_STEP_SHAPE)
    if step.kind in {StepKind.AGENT, StepKind.USE_CASE, StepKind.TOOL} and (
        step.permission_scope_ref is None
    ):
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_STEP_SHAPE)
    capability_id = step.capability_id
    if capability_id is None:
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.INVALID_STEP_SHAPE)
    try:
        capability = capability_policy.capability_registry.get(capability_id)
    except UnknownCapabilityError:
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.CAPABILITY_MISMATCH) from None
    if capability.execution_route is not _ROUTE_BY_KIND[step.kind]:
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.CAPABILITY_MISMATCH)


def validate_request_identity(
    *,
    plan: Plan,
    step: StepSpec,
    run_state: RunState,
    request: UseCaseRequest | ToolCallRequest | GateRequest,
) -> None:
    try:
        meta = request.meta
        if (
            meta.run_id != plan.run_id
            or meta.step_id != step.step_id
            or meta.correlation_id != run_state.correlation_id
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise RuntimeRoutingError(
            RuntimeRoutingErrorCode.REQUEST_IDENTITY_MISMATCH
        ) from None


def validate_gate_binding(
    *,
    plan: Plan,
    step: StepSpec,
    run_state: RunState,
    resolved: ResolvedGateInput,
) -> None:
    if type(resolved) is not ResolvedGateInput or resolved.gate_ref not in plan.gate_refs:
        raise RuntimeRoutingError(RuntimeRoutingErrorCode.GATE_REF_MISMATCH)
    validate_request_identity(
        plan=plan,
        step=step,
        run_state=run_state,
        request=resolved.request,
    )
