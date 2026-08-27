from __future__ import annotations

from datetime import UTC, datetime

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentInvocation,
    AgentResult,
    AgentResultStatus,
    AutonomyLevel,
    ContractMeta,
    DelegationEnvelope,
    DelegationResult,
    ExecutorKind,
    ExecutorRef,
    InvocationStatus,
    PermissionScope,
    RuntimeMode,
    StepKind,
    StepSpec,
)
from backend.agent_runtime.security import AgentHandoffSecurityPolicy
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 9, 0, tzinfo=UTC))

_CAPABILITY = {
    AgentId.AG_02: CapabilityId("CAP-E01"),
    AgentId.AG_03: CapabilityId("CAP-G01"),
    AgentId.AG_04: CapabilityId("CAP-V01"),
}
_EXECUTOR = {
    AgentId.AG_02: ExecutorKind.AG_02,
    AgentId.AG_03: ExecutorKind.AG_03,
    AgentId.AG_04: ExecutorKind.AG_04,
}


def meta[TStatus](
    status: TStatus,
    actor: AgentId,
    *,
    run_id: str = "run-e",
    step_id: str = "step-e",
    correlation_id: str = "corr-e",
) -> ContractMeta[TStatus]:
    return ContractMeta(
        AGENT_CONTRACT_SCHEMA_V1_0,
        run_id,
        step_id,
        None,
        CorrelationId(correlation_id),
        NOW,
        ActorRef(ActorKind.AGENT, actor.value),
        status,
    )


def scope(
    agent: AgentId,
    *,
    capability: CapabilityId | None = None,
    resources: tuple[str, ...] = ("course-1",),
    delegable: bool = False,
) -> PermissionScope:
    return PermissionScope(
        principal=ActorRef(ActorKind.AGENT, agent.value),
        capability_ids=(capability or _CAPABILITY[agent],),
        resource_scope={"course_ids": resources},
        operations=("transform",),
        delegable=delegable,
    )


def parent_scope(
    target: AgentId = AgentId.AG_03,
    *,
    resources: tuple[str, ...] = ("course-1",),
) -> PermissionScope:
    return scope(
        AgentId.AG_01,
        capability=_CAPABILITY[target],
        resources=resources,
        delegable=True,
    )


def step(
    target: AgentId = AgentId.AG_03,
    *,
    capability: CapabilityId | None = None,
    step_id: str = "step-e",
) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        kind=StepKind.AGENT,
        capability_id=capability or _CAPABILITY[target],
        executor=ExecutorRef(_EXECUTOR[target]),
        objective="Execute one specialist operation",
        output_contract={"type": "agent_result"},
    )


def delegation(
    target: AgentId = AgentId.AG_03,
    *,
    context: dict[str, object] | None = None,
    evidence_refs: tuple[str, ...] = ("evidence-1",),
    step_id: str = "step-e",
) -> DelegationEnvelope:
    source_step = step(target, step_id=step_id)
    return DelegationEnvelope(
        delegation_id="delegation-e",
        source_step=source_step,
        target_agent=target,
        context_slice=context or {"lesson": "fractions"},
        evidence_refs=evidence_refs,
        constraints={"preserve": ("objectives",)},
        permission_scope=scope(target, resources=("course-1",)),
    )


def invocation(
    delegated: DelegationEnvelope | None = None,
    *,
    invocation_id: str = "invocation-e",
) -> AgentInvocation:
    delegated = delegated or delegation()
    return AgentInvocation(
        meta=meta(InvocationStatus.PLANNED, AgentId.AG_01),
        invocation_id=invocation_id,
        source_step=delegated.source_step,
        delegation=delegated,
        agent_id=delegated.target_agent,
        attempt=1,
        autonomy_level=AutonomyLevel.AUT_L2,
        runtime_mode=RuntimeMode.MODE_ORCHESTRATED,
    )


def result(
    delegated: DelegationEnvelope | None = None,
    *,
    payload: object = None,
    warnings: tuple[dict[str, object], ...] = (),
    evidence_refs: tuple[str, ...] = (),
    artifact_refs: tuple[str, ...] = (),
    run_id: str = "run-e",
    step_id: str = "step-e",
    correlation_id: str = "corr-e",
    invocation_id: str = "invocation-e",
) -> DelegationResult[object]:
    delegated = delegated or delegation()
    agent_result = AgentResult[object](
        meta=meta(
            AgentResultStatus.SUCCEEDED,
            delegated.target_agent,
            run_id=run_id,
            step_id=step_id,
            correlation_id=correlation_id,
        ),
        invocation_id=invocation_id,
        payload={"candidate": "ready"} if payload is None else payload,
        warnings=warnings,
        evidence_refs=evidence_refs,
        artifact_refs=artifact_refs,
    )
    return DelegationResult(
        delegation_id=delegated.delegation_id,
        source_agent=delegated.target_agent,
        agent_result=agent_result,
        delegation=delegated,
    )


def secure_handoff(
    delegated: DelegationEnvelope | None = None,
    produced: DelegationResult[object] | None = None,
    parent: PermissionScope | None = None,
):
    delegated = delegated or delegation()
    return AgentHandoffSecurityPolicy().secure(
        delegator=AgentId.AG_01,
        parent_scope=parent or parent_scope(delegated.target_agent),
        invocation=invocation(delegated),
        result=produced or result(delegated),
        evaluated_at=NOW,
    )
