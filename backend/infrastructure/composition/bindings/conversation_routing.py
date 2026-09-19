"""Two closed WF-4 stages driven by the existing canonical runtime."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import NoReturn

from backend.agent_runtime.application_routing import (
    BASELINE_USE_CASE_REGISTRY,
    UseCaseInboundBindings,
    UseCaseRouter,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentInvocation,
    AutonomyLevel,
    BudgetSpec,
    ContractMeta,
    DelegationEnvelope,
    InvocationStatus,
    PermissionScope,
    RuntimeMode,
    StepSpec,
    WorkflowStatus,
)
from backend.agent_runtime.gates import BASELINE_GATE_AUTHORITY_POLICY, GateEngine
from backend.agent_runtime.orchestration import (
    CompletionDisposition,
    CoordinationAction,
    OrchestrationCoordinator,
    PlanCompilationRequest,
    PlanCompiler,
    PlanStepBinding,
    WorkflowCompletionDecision,
    WorkflowRequirements,
    WorkflowSelector,
)
from backend.agent_runtime.orchestration.workflows import WorkflowResponsibility
from backend.agent_runtime.policy import ToolCallPolicy
from backend.agent_runtime.recovery.budget import (
    BudgetAccountingPolicy,
    BudgetCheckDisposition,
    BudgetState,
    BudgetUsageDelta,
    resolve_effective_budget_limits,
)
from backend.agent_runtime.runtime import (
    DeterministicScheduler,
    Plan,
    PlanExecutor,
    RunState,
    StepRuntimeStatus,
    initialize_run_state,
)
from backend.agent_runtime.runtime.routing import (
    AgentStepBindings,
    AgentStepRouter,
    ResolvedAgentInput,
    RoutingPreLaunchGuard,
    RoutingStepRunner,
)
from backend.agent_runtime.sandbox import SandboxPolicy
from backend.agent_runtime.tools import ToolExecutorBindings, ToolRouter
from backend.core_contracts.capability import CapabilityId
from backend.infrastructure.composition.bindings.conversation_agents import (
    ConversationAgentBindings,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


class UnboundConversationCapability:
    """Explicit refusal for gates, tools, filesystem and AG04; never an allow double."""
    def execute(self, **arguments: object) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def run(self, **arguments: object) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def receive(self, **arguments: object) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def resolve(self, **arguments: object) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def inspect(self, **arguments: object) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")


class ConversationRoutingResolver:
    def __init__(self, agents: ConversationAgentBindings, now: Instant, budget: BudgetSpec) -> None:
        self.agents, self.now, self.budget = agents, now, budget

    def resolve_use_case_input(self, **arguments: object) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def resolve_tool_input(self, **arguments: object) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def resolve_gate_input(self, **arguments: object) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def resolve_agent_input(self, *, plan: Plan, step: StepSpec, run_state: RunState) -> ResolvedAgentInput:
        target = step.executor.agent_id
        if target not in {AgentId.AG_02, AgentId.AG_03} or step.capability_id is None:
            raise ConversationRejected("GENERATION_NOT_AUTHORIZED")
        codes = ("CAP-E01", "CAP-E02", "CAP-E03") if target is AgentId.AG_02 else ("CAP-G01",)
        parent = PermissionScope(
            principal=ActorRef(ActorKind.AGENT, AgentId.AG_01.value),
            capability_ids=tuple(CapabilityId(code) for code in codes),
            resource_scope={"request_refs": (self.agents.request.request_id,),
                            "context_sha256": self.agents.request.context.sha256},
            operations=("read",) if target is AgentId.AG_02 else ("create",),
            valid_from=self.now, expires_at=self.budget.deadline, budget=self.budget, delegable=True,
        )
        child = replace(parent, principal=ActorRef(ActorKind.AGENT, target.value), delegable=False)
        delegation = DelegationEnvelope(
            delegation_id=f"delegation-{step.step_id}", source_step=step, target_agent=target,
            context_slice={"request_ref": self.agents.request.request_id,
                           "context_digest": self.agents.request.context.sha256},
            evidence_refs=(), constraints={"evidence_mandate": "R2-EVIDENCE-MANDATE-1.0"}
            if target is AgentId.AG_02 else {}, permission_scope=child,
        )
        invocation = AgentInvocation(
            meta=ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, plan.run_id, step.step_id, None,
                              run_state.correlation_id, self.now, parent.principal,
                              InvocationStatus.PLANNED),
            invocation_id=f"invocation-{step.step_id}-1", source_step=step, delegation=delegation,
            agent_id=target, attempt=1, autonomy_level=AutonomyLevel.AUT_L2,
            runtime_mode=RuntimeMode.MODE_ORCHESTRATED,
        )
        return ResolvedAgentInput(invocation=invocation, permission_scope_ref="r2-scope",
                                  permission_scope=parent)


class ConversationCompletion:
    def __init__(self, agents: ConversationAgentBindings) -> None:
        self.agents = agents

    def evaluate(self, *, plan: Plan, run_state: RunState) -> WorkflowCompletionDecision:
        prepared = self.agents.prepare_only and self.agents.prepared_projection is not None
        complete = (len(plan.steps) == 2 and self.agents.evidence_set is not None
                    and (prepared or self.agents.candidate is not None) and all(
                        state.status is StepRuntimeStatus.SUCCEEDED
                        for state in run_state.step_states.values()))
        return WorkflowCompletionDecision(
            CompletionDisposition.SUCCEEDED if complete else CompletionDisposition.STOP_REQUIRED,
            ("R5_PROJECTION_PREPARED" if prepared else "R2_CANDIDATE_MATERIALIZED") if complete else "R2_INCOMPLETE",
        )


def execute_conversation_plan(
    agents: ConversationAgentBindings, *, clock: Callable[[], Instant], reserved_cost: Decimal,
) -> None:
    now = clock()
    budget = BudgetSpec(max_tokens=36864, max_cost=reserved_cost, max_steps=2,
                        max_runtime_seconds=120, deadline=Instant(now.value + timedelta(seconds=120)),
                        max_retries=0, max_tool_calls=0)
    selection = WorkflowSelector().select(WorkflowRequirements(
        external_evidence_required=True, production_required=True,
    ))
    run_id = "r2-" + agents.request.generation_id[4:]
    plan = PlanCompiler().compile(PlanCompilationRequest(
        selection=selection, plan_id=run_id + "-plan", run_id=run_id, plan_version=1,
        objective="Prepare without dispatch" if agents.prepare_only else "Create one contextualized candidate",
        success_criteria={"projection_present" if agents.prepare_only else "candidate_present": True},
        stop_conditions={"failure": "stop", "retry": False}, budget_envelope=budget,
        bindings=(
            PlanStepBinding(0, WorkflowResponsibility.EVIDENCE, "r2-evidence", "Gather admitted evidence",
                            capability_id=CapabilityId("CAP-E01"), permission_scope_ref="r2-scope",
                            budget=budget, output_contract={"type": "EvidenceSet",
                                "evidence_mandate": "R2-EVIDENCE-MANDATE-1.0"}),
            PlanStepBinding(0, WorkflowResponsibility.GENERATE_TRANSFORM, "r2-generation",
                            "Prepare only" if agents.prepare_only else "Generate one unvalidated candidate", capability_id=CapabilityId("CAP-G01"),
                            permission_scope_ref="r2-scope", budget=budget,
                            output_contract={"type": "PreparedGenerationCall" if agents.prepare_only else "ProductionCandidate"}),
        ),
    ))
    resolver = ConversationRoutingResolver(agents, now, budget)
    unbound = UnboundConversationCapability()
    policy = agents.policy
    router = AgentStepRouter(policy, AgentStepBindings(agents, agents, unbound))
    gate = GateEngine(BASELINE_GATE_AUTHORITY_POLICY, unbound)
    tools = ToolRouter(ToolCallPolicy(capability_policy=policy), SandboxPolicy(), unbound,
                       ToolExecutorBindings(()))
    guard = RoutingPreLaunchGuard(resolver, gate, tools.tool_call_policy, router, ())
    runner = RoutingStepRunner(
        resolver=resolver, agent_router=router,
        use_case_router=UseCaseRouter(policy, BASELINE_USE_CASE_REGISTRY, UseCaseInboundBindings(())),
        tool_router=tools, gate_engine=gate, runtime_control_runner=unbound,
    )
    executor = PlanExecutor(DeterministicScheduler(), guard, runner)
    coordinator = OrchestrationCoordinator(ConversationCompletion(agents))
    state = initialize_run_state(plan, CorrelationId(run_id))
    limits = replace(resolve_effective_budget_limits(plan_budget=budget, scope_budget=budget),
                     max_retries_per_step=0)
    accounting = BudgetAccountingPolicy()
    consumption = BudgetState(run_id, 1, limits, now, now)
    agents.trace.extend(("WorkflowSelector", "PlanCompiler"))
    # Exactly two scheduler cycles, no retry, replan, alternate workflow or third stage.
    for expected_step in ("r2-evidence", "r2-generation"):
        tick = clock()
        prospective = accounting.apply_delta(state=consumption, delta=BudgetUsageDelta(steps_started=1),
                                              now=tick)
        if accounting.evaluate(state=prospective, now=tick).disposition is not BudgetCheckDisposition.WITHIN_LIMIT:
            raise ConversationRejected("BUDGET_UNAVAILABLE")
        agents.trace.extend(("PlanExecutor", "RoutingPreLaunchGuard", "RoutingStepRunner"))
        cycle = executor.execute_cycle(plan=plan, run_state=state, now=tick)
        decision = coordinator.coordinate(plan=plan, cycle=cycle, now=clock())
        agents.trace.append("OrchestrationCoordinator")
        if (cycle.launched_step_ids != (expected_step,)
                or cycle.completed_step_ids != (expected_step,)
                or decision.action not in {CoordinationAction.CONTINUE, CoordinationAction.COMPLETE}):
            raise ConversationRejected("GENERATION_OUTPUT_INVALID" if agents.operations["CAP-G01"]
                                       else "INSUFFICIENT_EVIDENCE")
        state, consumption = decision.run_state, prospective
    complete = agents.prepared_projection is not None if agents.prepare_only else agents.candidate is not None
    if state.status is not WorkflowStatus.SUCCEEDED or not complete:
        raise ConversationRejected("GENERATION_OUTPUT_INVALID")
