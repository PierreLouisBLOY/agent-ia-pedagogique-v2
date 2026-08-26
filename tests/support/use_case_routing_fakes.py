from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from backend.agent_runtime.application_routing import (
    ApplicationInboundPort,
    UseCaseInboundBinding,
    UseCaseInboundBindings,
    UseCaseRouter,
    UseCaseRoutingContext,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    ExecutorKind,
    ExecutorRef,
    InvocationStatus,
    PermissionScope,
    StepKind,
    StepSpec,
    UseCaseRequest,
    UseCaseResult,
)
from backend.agent_runtime.policy import (
    CapabilityAuthorizationPolicy,
    CapabilityPolicyDecision,
    PolicyFacts,
    ScopeCheck,
)
from backend.core_contracts.capability import CapabilityId
from backend.core_contracts.invocation import UseCaseContext
from backend.core_contracts.outcome import ApplicationOutcome, OutcomeStatus
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 16, 0, tzinfo=UTC))
BEFORE = Instant(NOW.value - timedelta(hours=1))
AFTER = Instant(NOW.value + timedelta(hours=1))
DEFAULT_POLICY_FACTS = PolicyFacts()

USE_CASE_CAPABILITIES = {
    "application.read_canonical_resource": "CAP-R01",
    "application.read_production": "CAP-R02",
    "application.read_metadata_status": "CAP-R03",
    "application.run_deterministic_validation": "CAP-A01",
    "application.request_promotion": "CAP-A02",
    "application.export_artifact": "CAP-A03",
}


class RecordingApplicationInbound(ApplicationInboundPort):
    def __init__(self, result: object, *, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[UseCaseRequest] = []

    def invoke(self, *, request: UseCaseRequest) -> UseCaseResult[object, object]:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return cast(UseCaseResult[object, object], self.result)


class FixedDecisionPolicy(CapabilityAuthorizationPolicy):
    def __init__(self, decision: CapabilityPolicyDecision) -> None:
        super().__init__()
        object.__setattr__(self, "_fixed_decision", decision)

    def evaluate(
        self,
        *,
        agent_id: AgentId,
        scope: PermissionScope,
        check: ScopeCheck,
        facts: PolicyFacts = DEFAULT_POLICY_FACTS,
    ) -> CapabilityPolicyDecision:
        del agent_id, scope, check, facts
        return self._fixed_decision  # type: ignore[attr-defined,no-any-return]


def make_request(
    use_case_id: str = "application.read_canonical_resource",
    *,
    capability_code: str | None = None,
    step_kind: StepKind = StepKind.USE_CASE,
    executor_kind: ExecutorKind = ExecutorKind.APPLICATION,
    idempotency_key: str | None = None,
    payload: dict[str, object] | None = None,
    requested_effect: dict[str, object] | None = None,
    policy_facts: PolicyFacts | None = None,
    actor: ActorRef | None = None,
) -> tuple[UseCaseRequest, UseCaseRoutingContext]:
    code = capability_code or USE_CASE_CAPABILITIES[use_case_id]
    capability_id = CapabilityId(code)
    principal = actor or ActorRef(ActorKind.AGENT, AgentId.AG_01.value)
    step = StepSpec(
        step_id="step-use-case",
        kind=step_kind,
        capability_id=capability_id,
        executor=ExecutorRef(executor_kind),
        objective="Invoke exact Application use case",
        permission_scope_ref="permission-scope-1",
        output_contract={"contract_id": "C-13"},
    )
    request = UseCaseRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-use-case",
            step.step_id,
            None,
            CorrelationId("corr-use-case"),
            NOW,
            principal,
            InvocationStatus.PLANNED,
        ),
        use_case_id=use_case_id,
        payload={"resource_ref": "resource-1"} if payload is None else payload,
        actor_context=UseCaseContext(correlation_id=CorrelationId("corr-use-case")),
        idempotency_key=idempotency_key,
        requested_effect={} if requested_effect is None else requested_effect,
    )
    operation = "read" if code.startswith("CAP-R") else "request"
    scope = PermissionScope(
        principal=principal,
        capability_ids=(capability_id,),
        resource_scope={"resource_refs": ("resource-1",)},
        operations=(operation,),
        valid_from=BEFORE,
        expires_at=AFTER,
    )
    context = UseCaseRoutingContext(
        step=step,
        permission_scope_ref="permission-scope-1",
        permission_scope=scope,
        policy_facts=policy_facts or PolicyFacts(),
    )
    return request, context


def make_result(
    request: UseCaseRequest,
    *,
    use_case_id: str | None = None,
    run_id: str | None = None,
    step_id: str | None = None,
    correlation_id: CorrelationId | None = None,
    status: OutcomeStatus = OutcomeStatus.SUCCESS,
    outcome: ApplicationOutcome[object, object] | None = None,
) -> UseCaseResult[object, object]:
    correlation = correlation_id or request.meta.correlation_id
    configured_outcome = outcome or ApplicationOutcome[object, object](
        outcome_status=status,
        success=status in {OutcomeStatus.SUCCESS, OutcomeStatus.SUCCESS_WITH_WARNING},
        correlation_id=correlation,
        data={"handled": True},
        validation_result=(
            {"valid": True}
            if request.use_case_id == "application.run_deterministic_validation"
            else None
        ),
    )
    return UseCaseResult(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            run_id or request.meta.run_id,
            step_id or request.meta.step_id,
            None,
            correlation,
            NOW,
            request.meta.actor,
            status,
        ),
        use_case_id=use_case_id or request.use_case_id,
        outcome=configured_outcome,
        domain_events=({"event_type": "application.completed"},),
    )


def make_router(
    request: UseCaseRequest,
    *,
    result: object | None = None,
    bind: bool = True,
    policy: CapabilityAuthorizationPolicy | None = None,
    inbound_error: Exception | None = None,
) -> tuple[UseCaseRouter, RecordingApplicationInbound]:
    inbound = RecordingApplicationInbound(
        make_result(request) if result is None else result,
        error=inbound_error,
    )
    bindings = UseCaseInboundBindings(
        (UseCaseInboundBinding(request.use_case_id, inbound),) if bind else ()
    )
    from backend.agent_runtime.application_routing import BASELINE_USE_CASE_REGISTRY

    return (
        UseCaseRouter(
            policy or CapabilityAuthorizationPolicy(),
            BASELINE_USE_CASE_REGISTRY,
            bindings,
        ),
        inbound,
    )
