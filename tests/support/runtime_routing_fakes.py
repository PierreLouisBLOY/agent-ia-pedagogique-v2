from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from backend.agent_runtime.application_routing import (
    BASELINE_USE_CASE_REGISTRY,
    ApplicationInboundPort,
    UseCaseInboundBinding,
    UseCaseInboundBindings,
    UseCaseRouter,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResultStatus,
    ContractMeta,
    ExecutorKind,
    ExecutorRef,
    GateDecision,
    GateDecisionValue,
    GateRequest,
    GateStatus,
    InvocationStatus,
    PermissionScope,
    StepKind,
    StepSpec,
    ToolCallRequest,
    ToolCallResult,
    UseCaseRequest,
    UseCaseResult,
    WorkflowStatus,
)
from backend.agent_runtime.gates import (
    BASELINE_GATE_AUTHORITY_POLICY,
    GateDecisionSourcePort,
    GateEngine,
)
from backend.agent_runtime.policy import (
    CapabilityAuthorizationPolicy,
    ConditionalResolution,
    PermissionOperation,
    PolicyFacts,
    ToolCallPolicy,
)
from backend.agent_runtime.runtime import (
    Plan,
    RunState,
    StepExecutionResult,
    StepRuntimeStatus,
    StepState,
)
from backend.agent_runtime.runtime.routing import (
    AgentStepBindings,
    AgentStepRouter,
    ResolvedAgentInput,
    ResolvedGateInput,
    ResolvedToolInput,
    ResolvedUseCaseInput,
    RoutingPreLaunchGuard,
    RoutingStepRunner,
)
from backend.agent_runtime.sandbox import (
    ResolvedSandboxPath,
    SandboxOperation,
    SandboxPolicy,
    SandboxRelativePath,
    SandboxRootRef,
)
from backend.agent_runtime.tools import (
    SandboxOutputTarget,
    ToolExecutionOutcome,
    ToolExecutorBinding,
    ToolExecutorBindings,
    ToolRouter,
    ToolRoutingContext,
)
from backend.core_contracts.capability import CapabilityId
from backend.core_contracts.invocation import UseCaseContext
from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.support.tool_execution_fakes import (
    RecordingSandboxFilesystem,
    RecordingToolExecutor,
)

NOW = Instant(datetime(2026, 8, 26, 17, 0, tzinfo=UTC))
BEFORE = Instant(NOW.value - timedelta(hours=1))
AFTER = Instant(NOW.value + timedelta(hours=1))
CORRELATION = CorrelationId("corr-runtime-routing")
ACTOR = ActorRef(ActorKind.AGENT, AgentId.AG_01.value)


def permission_scope(capability_code: str) -> PermissionScope:
    operation = {
        "CAP-R01": PermissionOperation.READ,
        "CAP-A01": PermissionOperation.REQUEST,
        "CAP-A02": PermissionOperation.REQUEST,
        "CAP-E01": PermissionOperation.READ,
        "CAP-E02": PermissionOperation.READ,
        "CAP-E03": PermissionOperation.READ,
        "CAP-G01": PermissionOperation.CREATE,
        "CAP-G02": PermissionOperation.TRANSFORM,
        "CAP-G03": PermissionOperation.TRANSFORM,
        "CAP-V01": PermissionOperation.REVIEW,
        "CAP-V02": PermissionOperation.REVIEW,
        "CAP-T02": PermissionOperation.TRANSFORM,
        "CAP-T03": PermissionOperation.TRANSFORM,
    }[capability_code]
    return PermissionScope(
        principal=ACTOR,
        capability_ids=(CapabilityId(capability_code),),
        resource_scope={"resource_refs": ("resource-1",)},
        operations=(operation.value,),
        valid_from=BEFORE,
        expires_at=AFTER,
        delegable=True,
    )


def make_step(
    kind: StepKind,
    capability_code: str,
    executor: ExecutorKind,
    *,
    step_id: str = "step-routing",
    depends_on: tuple[str, ...] = (),
) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        kind=kind,
        capability_id=CapabilityId(capability_code),
        executor=ExecutorRef(executor),
        objective="Route through the exact runtime boundary",
        depends_on=depends_on,
        permission_scope_ref=(
            "scope-routing"
            if kind in {StepKind.AGENT, StepKind.USE_CASE, StepKind.TOOL}
            else None
        ),
        output_contract={"contract_id": "runtime-result"},
    )


def make_plan(
    *steps: StepSpec,
    workflow_kind: str = "WF-0",
    gate_refs: tuple[str, ...] = (),
) -> Plan:
    return Plan(
        plan_id="plan-routing",
        run_id="run-routing",
        plan_version=1,
        objective="Exercise runtime routing",
        success_criteria={"complete": True},
        workflow_kind=workflow_kind,
        steps=steps,
        gate_refs=gate_refs,
        stop_conditions={"failure": "stop"},
    )


def make_run_state(
    plan: Plan,
    *,
    ready_step_id: str | None = None,
    status: WorkflowStatus = WorkflowStatus.RUNNING,
) -> RunState:
    return RunState(
        run_id=plan.run_id,
        correlation_id=CORRELATION,
        workflow_kind=plan.workflow_kind,
        plan_id=plan.plan_id,
        plan_version=plan.plan_version,
        status=status,
        step_states={
            step.step_id: StepState(
                step_id=step.step_id,
                status=(
                    StepRuntimeStatus.READY
                    if step.step_id == ready_step_id
                    else StepRuntimeStatus.PENDING
                ),
            )
            for step in plan.steps
        },
        started_at=NOW if status is WorkflowStatus.RUNNING else None,
    )


def make_use_case_input(
    step: StepSpec,
    *,
    policy_facts: PolicyFacts | None = None,
) -> ResolvedUseCaseInput:
    capability_id = step.capability_id
    if capability_id is None:
        raise ValueError("test use-case step requires a capability")
    request = UseCaseRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-routing",
            step.step_id,
            None,
            CORRELATION,
            NOW,
            ACTOR,
            InvocationStatus.PLANNED,
        ),
        use_case_id={
            "CAP-R01": "application.read_canonical_resource",
            "CAP-A01": "application.run_deterministic_validation",
            "CAP-A02": "application.request_promotion",
        }[capability_id.value],
        payload={"resource_ref": "resource-1"},
        actor_context=UseCaseContext(correlation_id=CORRELATION),
        idempotency_key=(
            "idem-use-case"
            if capability_id.value.startswith("CAP-A")
            else None
        ),
    )
    scope = permission_scope(capability_id.value)
    return ResolvedUseCaseInput(
        request=request,
        permission_scope_ref="scope-routing",
        permission_scope=scope,
        policy_facts=policy_facts or PolicyFacts(),
    )


def make_gate_input(step: StepSpec, *, gate_ref: str = "gate-ref-1") -> ResolvedGateInput:
    request = GateRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-routing",
            step.step_id,
            None,
            CORRELATION,
            NOW,
            ACTOR,
            GateStatus.PENDING,
        ),
        gate_id="gate-runtime",
        gate_type="human_promotion_approval",
        reason="External approval required",
        options=({"id": "approve"}, {"id": "reject"}),
        required_actor=ActorRef(ActorKind.USER, "user-1"),
        context_summary={"subject_ref": "resource-1"},
        expires_at=AFTER,
    )
    return ResolvedGateInput(gate_ref=gate_ref, request=request)


def make_tool_input(step: StepSpec, *, facts: PolicyFacts | None = None) -> ResolvedToolInput:
    capability_id = step.capability_id
    if capability_id is None:
        raise ValueError("test tool step requires a capability")
    scope = permission_scope(capability_id.value)
    request = ToolCallRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-routing",
            step.step_id,
            None,
            CORRELATION,
            NOW,
            ACTOR,
            InvocationStatus.PLANNED,
        ),
        tool_id=(
            "tool.render_document"
            if capability_id.value == "CAP-T02"
            else "tool.convert_format"
        ),
        capability_id=capability_id,
        arguments={"source_ref": "artifact-input", "target_format": "pdf"},
        permission_scope=scope,
        timeout=60,
        idempotency_key="idem-tool",
    )
    context = ToolRoutingContext(
        root_ref=SandboxRootRef("run-routing", "root-routing"),
        input_paths=(SandboxRelativePath("input/source.txt"),),
        output_targets=(
            SandboxOutputTarget(
                relative_path=SandboxRelativePath("output/result.pdf"),
                operation=SandboxOperation.CREATE,
                declared_output_bytes=100,
                declared_mime_type="application/pdf",
            ),
        ),
    )
    return ResolvedToolInput(
        request=request,
        permission_scope_ref="scope-routing",
        context=context,
        policy_facts=facts or PolicyFacts(),
    )


class RecordingResolver:
    def __init__(self) -> None:
        self.use_case_input: object | None = None
        self.tool_input: object | None = None
        self.gate_input: object | None = None
        self.agent_input: object | None = None
        self.calls: list[str] = []

    def resolve_use_case_input(self, *, plan: Plan, step: StepSpec, run_state: RunState) -> ResolvedUseCaseInput:
        del plan, step, run_state
        self.calls.append("use_case")
        return cast(ResolvedUseCaseInput, self.use_case_input)

    def resolve_tool_input(self, *, plan: Plan, step: StepSpec, run_state: RunState) -> ResolvedToolInput:
        del plan, step, run_state
        self.calls.append("tool")
        return cast(ResolvedToolInput, self.tool_input)

    def resolve_gate_input(self, *, plan: Plan, step: StepSpec, run_state: RunState) -> ResolvedGateInput:
        del plan, step, run_state
        self.calls.append("gate")
        return cast(ResolvedGateInput, self.gate_input)

    def resolve_agent_input(self, *, plan: Plan, step: StepSpec, run_state: RunState) -> ResolvedAgentInput:
        del plan, step, run_state
        self.calls.append("agent")
        return cast(ResolvedAgentInput, self.agent_input)


class RecordingAgentPort:
    def __init__(self, result: StepExecutionResult | None = None, error: Exception | None = None) -> None:
        self.result = result or StepExecutionResult(StepRuntimeStatus.SUCCEEDED)
        self.error = error
        self.calls: list[str] = []

    def execute(self, *, plan: Plan, step: StepSpec, run_state: RunState, attempt: int, now: Instant) -> StepExecutionResult:
        del plan, run_state, attempt, now
        self.calls.append(step.step_id)
        if self.error is not None:
            raise self.error
        return self.result


class RecordingRuntimeControlRunner:
    def __init__(self, result: StepExecutionResult | None = None) -> None:
        self.result = result or StepExecutionResult(StepRuntimeStatus.SUCCEEDED)
        self.calls: list[StepKind] = []

    def run(self, *, plan: Plan, step: StepSpec, run_state: RunState, attempt: int, now: Instant) -> StepExecutionResult:
        del plan, run_state, attempt, now
        self.calls.append(step.kind)
        return self.result


class RecordingGateSource(GateDecisionSourcePort):
    def __init__(self, decisions: tuple[GateDecision | None, ...]) -> None:
        self.decisions = decisions
        self.calls = 0

    def receive(self, *, request: GateRequest) -> GateDecision | None:
        index = min(self.calls, len(self.decisions) - 1)
        self.calls += 1
        return self.decisions[index]


def gate_decision(request: GateRequest, value: GateDecisionValue = GateDecisionValue.APPROVED) -> GateDecision:
    status = {
        GateDecisionValue.APPROVED: GateStatus.APPROVED,
        GateDecisionValue.REJECTED: GateStatus.REJECTED,
        GateDecisionValue.DEFERRED: GateStatus.DEFERRED,
    }[value]
    return GateDecision(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            request.meta.run_id,
            request.meta.step_id,
            None,
            CORRELATION,
            NOW,
            request.required_actor,
            status,
        ),
        gate_id=request.gate_id,
        decision=value,
        actor=request.required_actor,
        decided_at=NOW,
        decision_ref="gate-decision-ref",
        request=request,
        selected_option={"id": "approve"},
    )


def make_gate_engine(source: RecordingGateSource) -> GateEngine:
    return GateEngine(BASELINE_GATE_AUTHORITY_POLICY, source)


class RecordingInbound(ApplicationInboundPort):
    def __init__(self, result: UseCaseResult[object, object]) -> None:
        self.result = result
        self.calls = 0

    def invoke(self, *, request: UseCaseRequest) -> UseCaseResult[object, object]:
        del request
        self.calls += 1
        return self.result


def make_use_case_router(
    resolved: ResolvedUseCaseInput,
    policy: CapabilityAuthorizationPolicy,
    *,
    status: OutcomeStatus = OutcomeStatus.SUCCESS,
    result_ref: str | None = "application-result-ref",
) -> tuple[UseCaseRouter, RecordingInbound]:
    request = resolved.request
    outcome = ApplicationOutcome[object, object](
        outcome_status=status,
        success=status in {OutcomeStatus.SUCCESS, OutcomeStatus.SUCCESS_WITH_WARNING},
        correlation_id=CORRELATION,
        data={"handled": True} if status is OutcomeStatus.SUCCESS else None,
    )
    result = UseCaseResult[object, object](
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            request.meta.run_id,
            request.meta.step_id,
            None,
            CORRELATION,
            NOW,
            ACTOR,
            status,
        ),
        use_case_id=request.use_case_id,
        outcome=outcome,
        result_ref=result_ref,
    )
    inbound = RecordingInbound(result)
    router = UseCaseRouter(
        policy,
        BASELINE_USE_CASE_REGISTRY,
        UseCaseInboundBindings((UseCaseInboundBinding(request.use_case_id, inbound),)),
    )
    return router, inbound


def make_tool_router(
    resolved: ResolvedToolInput,
    policy: CapabilityAuthorizationPolicy,
    *,
    executor_error: Exception | None = None,
) -> tuple[ToolRouter, RecordingToolExecutor]:
    request = resolved.request
    result = ToolCallResult(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            request.meta.run_id,
            request.meta.step_id,
            None,
            CORRELATION,
            NOW,
            ACTOR,
            AgentResultStatus.SUCCEEDED,
        ),
        tool_id=request.tool_id,
        output={"rendered": True},
        artifacts=("tool-artifact-ref",),
    )
    output_path = resolved.context.output_targets[0].relative_path
    executor = RecordingToolExecutor(
        ToolExecutionOutcome(result=result, produced_paths=(output_path,)),
        error=executor_error,
    )
    root = resolved.context.root_ref
    input_path = resolved.context.input_paths[0]
    filesystem = RecordingSandboxFilesystem(
        {
            input_path.value: (
                _resolved(root, input_path, exists=True, mime="text/plain", size=10),
            ),
            output_path.value: (
                _resolved(root, output_path, exists=False, mime=None, size=0),
                _resolved(root, output_path, exists=True, mime="application/pdf", size=100),
            ),
        }
    )
    router = ToolRouter(
        ToolCallPolicy(capability_policy=policy),
        SandboxPolicy(),
        filesystem,
        ToolExecutorBindings((ToolExecutorBinding(request.tool_id, executor),)),
    )
    return router, executor


def _resolved(
    root: SandboxRootRef,
    path: SandboxRelativePath,
    *,
    exists: bool,
    mime: str | None,
    size: int,
) -> ResolvedSandboxPath:
    return ResolvedSandboxPath(
        root_ref=root,
        relative_path=path,
        canonical_path_token=f"token-{path.value.replace('/', '-')}",
        exists=exists,
        is_file=exists,
        is_symlink=False,
        is_within_root=True,
        size_bytes=size,
        observed_extension=path.extension,
        observed_mime_type=mime,
        has_active_content=False,
        is_executable_content=False,
    )


@dataclass(slots=True)
class RuntimeHarness:
    resolver: RecordingResolver
    guard: RoutingPreLaunchGuard
    runner: RoutingStepRunner
    gate_source: RecordingGateSource
    agent_ports: tuple[RecordingAgentPort, RecordingAgentPort, RecordingAgentPort]
    inbound: RecordingInbound
    tool_executor: RecordingToolExecutor
    runtime_control: RecordingRuntimeControlRunner


def make_runtime_harness(
    step: StepSpec,
    *,
    gate_values: tuple[GateDecisionValue | None, ...] = (GateDecisionValue.APPROVED,),
    tool_facts: PolicyFacts | None = None,
    use_case_facts: PolicyFacts | None = None,
    agent_error: Exception | None = None,
    tool_executor_error: Exception | None = None,
) -> RuntimeHarness:
    policy = CapabilityAuthorizationPolicy()
    resolver = RecordingResolver()

    use_case_step = (
        step
        if step.kind is StepKind.USE_CASE
        else make_step(StepKind.USE_CASE, "CAP-R01", ExecutorKind.APPLICATION)
    )
    resolver.use_case_input = make_use_case_input(
        use_case_step, policy_facts=use_case_facts
    )
    tool_step = (
        step
        if step.kind is StepKind.TOOL
        else make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    )
    resolver.tool_input = make_tool_input(
        tool_step,
        facts=(
            tool_facts
            if tool_facts is not None
            else PolicyFacts(conditional_resolution=ConditionalResolution.ALLOW)
        ),
    )
    gate_step = (
        step
        if step.kind is StepKind.GATE
        or (
            step.kind is StepKind.USE_CASE
            and step.capability_id is not None
            and step.capability_id.value == "CAP-A02"
        )
        else make_step(StepKind.GATE, "CAP-O05", ExecutorKind.RUNTIME)
    )
    gate_input = make_gate_input(gate_step)
    resolver.gate_input = gate_input
    agent_step = (
        step
        if step.kind is StepKind.AGENT
        else make_step(StepKind.AGENT, "CAP-E01", ExecutorKind.AG_02)
    )
    if agent_step.capability_id is None:
        raise ValueError("test agent step requires a capability")
    resolver.agent_input = ResolvedAgentInput(
        permission_scope_ref="scope-routing",
        permission_scope=permission_scope(agent_step.capability_id.value),
    )

    decisions = tuple(
        None if value is None else gate_decision(gate_input.request, value)
        for value in gate_values
    )
    gate_source = RecordingGateSource(decisions)
    gate_engine = make_gate_engine(gate_source)
    ag_02 = RecordingAgentPort(error=agent_error)
    ag_03 = RecordingAgentPort(error=agent_error)
    ag_04 = RecordingAgentPort(error=agent_error)
    agent_router = AgentStepRouter(
        policy,
        AgentStepBindings(ag_02=ag_02, ag_03=ag_03, ag_04=ag_04),
    )
    use_case_router, inbound = make_use_case_router(
        cast(ResolvedUseCaseInput, resolver.use_case_input), policy
    )
    tool_router, tool_executor = make_tool_router(
        cast(ResolvedToolInput, resolver.tool_input),
        policy,
        executor_error=tool_executor_error,
    )
    runtime_control = RecordingRuntimeControlRunner()
    runner = RoutingStepRunner(
        resolver=resolver,
        agent_router=agent_router,
        use_case_router=use_case_router,
        tool_router=tool_router,
        gate_engine=gate_engine,
        runtime_control_runner=runtime_control,
    )
    guard = RoutingPreLaunchGuard(
        resolver=resolver,
        gate_engine=gate_engine,
        tool_call_policy=tool_router.tool_call_policy,
        agent_router=agent_router,
        declared_sandbox_profile_ids=tuple(
            profile.profile_id
            for profile in tool_router.sandbox_policy.profile_registry.all()
        ),
    )
    return RuntimeHarness(
        resolver=resolver,
        guard=guard,
        runner=runner,
        gate_source=gate_source,
        agent_ports=(ag_02, ag_03, ag_04),
        inbound=inbound,
        tool_executor=tool_executor,
        runtime_control=runtime_control,
    )
