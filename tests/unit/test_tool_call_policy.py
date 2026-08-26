from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    InvocationStatus,
    PermissionScope,
    ToolCallRequest,
)
from backend.agent_runtime.policy import (
    AuthorityKind,
    CapabilityAuthorizationPolicy,
    CapabilityPolicyDecision,
    ConditionalResolution,
    PermissionOperation,
    PolicyDecisionCode,
    PolicyDisposition,
    PolicyFacts,
    ScopeEvaluation,
    ScopeEvaluationCode,
    ToolCallDecision,
    ToolCallDecisionCode,
    ToolCallDisposition,
    ToolCallPolicy,
)
from backend.agent_runtime.registry import (
    ToolDescriptor,
    ToolEffectClass,
    ToolRegistry,
)
from backend.agent_runtime.registry.capabilities import CapabilityExecutionRoute
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
BEFORE = Instant(NOW.value - timedelta(hours=1))
AFTER = Instant(NOW.value + timedelta(hours=1))
SANDBOX_PROFILE = "sandbox.local_file_transform.v1"
CAP_T02 = CapabilityId("CAP-T02")


def _scope(
    agent_id: AgentId,
    capability_id: CapabilityId,
    **overrides: object,
) -> PermissionScope:
    values: dict[str, object] = {
        "principal": ActorRef(ActorKind.AGENT, agent_id.value),
        "capability_ids": (capability_id,),
        "resource_scope": {"artifact_refs": ("artifact-input",)},
        "operations": (PermissionOperation.TRANSFORM.value,),
        "constraints": {"formats": ("pdf",)},
        "valid_from": BEFORE,
        "expires_at": AFTER,
        "budget": None,
        "delegable": False,
        "gate_requirements": (),
        "deny_rules": (),
    }
    values.update(overrides)
    return PermissionScope(**values)  # type: ignore[arg-type]


def _request(
    *,
    tool_id: str = "tool.render_document",
    capability_id: CapabilityId = CAP_T02,
    agent_id: AgentId = AgentId.AG_01,
    scope: PermissionScope | None = None,
    arguments: dict[str, object] | None = None,
    timeout: int | float | None = 60,
    idempotency_key: str | None = "idem-render-1",
    meta_actor: ActorRef | None = None,
) -> ToolCallRequest:
    return ToolCallRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-tool-policy",
            "step-tool-policy",
            None,
            CorrelationId("corr-tool-policy"),
            NOW,
            meta_actor or ActorRef(ActorKind.AGENT, agent_id.value),
            InvocationStatus.PLANNED,
        ),
        tool_id=tool_id,
        capability_id=capability_id,
        arguments=arguments
        or {"source_ref": "artifact-input", "target_format": "pdf"},
        permission_scope=scope or _scope(agent_id, capability_id),
        timeout=timeout,
        idempotency_key=idempotency_key,
    )


def _evaluate(
    request: ToolCallRequest | None = None,
    *,
    agent_id: AgentId = AgentId.AG_01,
    facts: PolicyFacts | None = None,
    sandbox_profiles: tuple[str, ...] = (SANDBOX_PROFILE,),
    policy: ToolCallPolicy | None = None,
):
    return (policy or ToolCallPolicy()).evaluate(
        agent_id=agent_id,
        request=request or _request(agent_id=agent_id),
        evaluated_at=NOW,
        facts=facts or PolicyFacts(conditional_resolution=ConditionalResolution.ALLOW),
        declared_sandbox_profile_ids=sandbox_profiles,
    )


@pytest.mark.parametrize(
    ("tool_id", "capability_code"),
    (
        ("tool.render_document", "CAP-T02"),
        ("tool.convert_format", "CAP-T03"),
    ),
)
def test_conditional_t02_t03_allow_only_after_trusted_resolution(
    tool_id: str, capability_code: str
) -> None:
    request = _request(tool_id=tool_id, capability_id=CapabilityId(capability_code))

    decision = _evaluate(request)

    assert (
        decision.disposition,
        decision.code,
        decision.tool_id,
        decision.capability_id.value,
    ) == (
        ToolCallDisposition.ALLOW,
        ToolCallDecisionCode.ALLOW,
        tool_id,
        capability_code,
    )
    assert decision.capability_decision is not None
    assert decision.capability_decision.disposition is PolicyDisposition.ALLOW
    assert decision.effect_class is ToolEffectClass.LOCAL_FILE_TRANSFORM
    assert decision.sandbox_profile_id == SANDBOX_PROFILE
    assert decision.idempotency_required
    assert decision.effective_timeout == 60


def test_missing_timeout_uses_descriptor_ceiling_deterministically() -> None:
    assert _evaluate(_request(timeout=None)).effective_timeout == 120


def test_unknown_tool_and_unknown_capability_fail_closed() -> None:
    unknown_tool = _evaluate(_request(tool_id="tool.unknown"))
    unknown_capability = _evaluate(
        _request(capability_id=CapabilityId("CAP-T99"))
    )

    assert unknown_tool.code is ToolCallDecisionCode.UNKNOWN_TOOL
    assert unknown_capability.code is ToolCallDecisionCode.UNKNOWN_CAPABILITY
    assert unknown_tool.disposition is ToolCallDisposition.DENY
    assert unknown_capability.disposition is ToolCallDisposition.DENY


def test_non_utility_capability_and_tool_capability_mismatch_are_distinct() -> None:
    non_utility = _evaluate(_request(capability_id=CapabilityId("CAP-A01")))
    mismatch = _evaluate(_request(capability_id=CapabilityId("CAP-T03")))

    assert non_utility.code is ToolCallDecisionCode.NON_UTILITY_CAPABILITY
    assert mismatch.code is ToolCallDecisionCode.CAPABILITY_TOOL_MISMATCH


def test_matrix_and_scope_denials_are_non_executable_and_distinct() -> None:
    matrix_request = _request(agent_id=AgentId.AG_02)
    matrix_deny = _evaluate(
        matrix_request,
        agent_id=AgentId.AG_02,
        facts=PolicyFacts(),
    )
    capability_id = CapabilityId("CAP-T02")
    denied_scope = _scope(
        AgentId.AG_01,
        capability_id,
        deny_rules=({"capability_id": capability_id.value},),
    )
    scope_deny = _evaluate(_request(scope=denied_scope))

    assert matrix_deny.code is ToolCallDecisionCode.CAPABILITY_NOT_ALLOWED
    assert matrix_deny.capability_decision is not None
    assert matrix_deny.capability_decision.code is PolicyDecisionCode.MATRIX_DENY
    assert scope_deny.code is ToolCallDecisionCode.PERMISSION_SCOPE_MISMATCH
    assert scope_deny.capability_decision is not None
    assert scope_deny.capability_decision.code is PolicyDecisionCode.SCOPE_DENY


@pytest.mark.parametrize(
    "facts",
    (
        PolicyFacts(),
        PolicyFacts(conditional_resolution=ConditionalResolution.REQUEST),
    ),
)
def test_unresolved_condition_and_request_are_non_executable(
    facts: PolicyFacts,
) -> None:
    decision = _evaluate(facts=facts)

    assert decision.disposition is ToolCallDisposition.DENY
    assert decision.code is ToolCallDecisionCode.CAPABILITY_NOT_ALLOWED
    assert decision.capability_decision is not None
    assert decision.capability_decision.disposition in {
        PolicyDisposition.CONDITION_REQUIRED,
        PolicyDisposition.REQUEST,
    }


@pytest.mark.parametrize(
    ("disposition", "code", "target"),
    (
        (PolicyDisposition.REQUEST, PolicyDecisionCode.CONDITIONAL_REQUEST, None),
        (PolicyDisposition.DELEGATE, PolicyDecisionCode.DELEGATE_AGENT, AgentId.AG_03),
        (PolicyDisposition.REQUEST_GATE, PolicyDecisionCode.GATE_REQUIRED, None),
        (
            PolicyDisposition.CONDITION_REQUIRED,
            PolicyDecisionCode.CONDITION_REQUIRED,
            None,
        ),
    ),
)
def test_every_non_allow_capability_disposition_is_non_executable(
    monkeypatch: pytest.MonkeyPatch,
    disposition: PolicyDisposition,
    code: PolicyDecisionCode,
    target: AgentId | None,
) -> None:
    capability_decision = CapabilityPolicyDecision(
        disposition=disposition,
        code=code,
        capability_id=CapabilityId("CAP-T02"),
        agent_id=AgentId.AG_01,
        route=CapabilityExecutionRoute.UTILITY,
        authority=AuthorityKind.TECHNICAL_UTILITY,
        scope_evaluation=ScopeEvaluation(True, ScopeEvaluationCode.ALLOW),
        target_agent=target,
    )

    def _decision(*args: object, **kwargs: object) -> CapabilityPolicyDecision:
        del args, kwargs
        return capability_decision

    monkeypatch.setattr(CapabilityAuthorizationPolicy, "evaluate", _decision)

    decision = _evaluate()

    assert decision.disposition is ToolCallDisposition.DENY
    assert decision.code is ToolCallDecisionCode.CAPABILITY_NOT_ALLOWED


def test_policy_evaluates_the_exact_request_scope_without_rebuilding_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    original = CapabilityAuthorizationPolicy.evaluate
    observed: list[bool] = []

    def _recording_evaluate(
        self: CapabilityAuthorizationPolicy, **kwargs: object
    ) -> CapabilityPolicyDecision:
        observed.append(kwargs["scope"] is request.permission_scope)
        return original(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(CapabilityAuthorizationPolicy, "evaluate", _recording_evaluate)

    decision = _evaluate(request)

    assert decision.disposition is ToolCallDisposition.ALLOW
    assert observed == [True]


def test_idempotency_timeout_and_sandbox_constraints_fail_closed() -> None:
    missing_key = _evaluate(_request(idempotency_key=None))
    excessive_timeout = _evaluate(_request(timeout=121))
    missing_sandbox = _evaluate(sandbox_profiles=())
    wrong_sandbox = _evaluate(sandbox_profiles=("sandbox.other.v1",))

    assert missing_key.code is ToolCallDecisionCode.IDEMPOTENCY_REQUIRED
    assert excessive_timeout.code is ToolCallDecisionCode.TIMEOUT_EXCEEDS_CEILING
    assert missing_sandbox.code is ToolCallDecisionCode.SANDBOX_REQUIRED
    assert wrong_sandbox.code is ToolCallDecisionCode.SANDBOX_PROFILE_MISMATCH


@pytest.mark.parametrize("timeout", (float("nan"), float("inf")))
def test_non_finite_request_timeout_is_invalid(timeout: float) -> None:
    decision = _evaluate(_request(timeout=timeout))

    assert decision.code is ToolCallDecisionCode.INVALID_REQUEST
    assert decision.disposition is ToolCallDisposition.DENY


def test_external_mutation_is_forbidden_even_with_idempotency() -> None:
    descriptor = ToolDescriptor(
        tool_id="tool.external_mutation",
        canonical_name="external_mutation",
        capability_id=CapabilityId("CAP-T02"),
        input_contract_id="tool.external_mutation.input.v1",
        output_contract_id="tool.external_mutation.output.v1",
        effect_class=ToolEffectClass.EXTERNAL_MUTATION,
        sandbox_profile_id=None,
        idempotency_required=True,
        timeout_ceiling=30,
    )
    policy = ToolCallPolicy(tool_registry=ToolRegistry((descriptor,)))
    request = _request(tool_id=descriptor.tool_id, timeout=30)

    decision = _evaluate(request, policy=policy)

    assert decision.code is ToolCallDecisionCode.EXTERNAL_MUTATION_FORBIDDEN
    assert decision.disposition is ToolCallDisposition.DENY


@pytest.mark.parametrize(
    "forbidden_arguments",
    (
        {"tool_id": "tool.convert_format"},
        {"nested": {"capability_id": "CAP-T03"}},
        {"permission_scope": {"operations": ("transform",)}},
        {"gate_approved": True},
        {"handler_path": "package.module:call"},
        {"import_path": "package.module"},
        {"provider_credentials": {}},
        {"sandbox_profile_id": "sandbox.untrusted"},
        {"nested": {"capabilityOverride": "CAP-T03"}},
        {"providerCredentials": {}},
        {"sandboxProfileId": "sandbox.untrusted"},
    ),
)
def test_authority_smuggling_arguments_are_rejected(
    forbidden_arguments: dict[str, object],
) -> None:
    decision = _evaluate(_request(arguments=forbidden_arguments))

    assert decision.code is ToolCallDecisionCode.INVALID_REQUEST
    assert decision.disposition is ToolCallDisposition.DENY


def test_request_actor_must_match_the_evaluated_agent() -> None:
    decision = _evaluate(
        _request(meta_actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value))
    )

    assert decision.code is ToolCallDecisionCode.INVALID_REQUEST


def test_provider_api_key_is_rejected_by_the_existing_agent_safe_contract() -> None:
    with pytest.raises(ValueError, match="forbidden structured data key"):
        _request(arguments={"api_key": "redacted"})


def test_tool_call_decision_is_data_only_and_stores_no_execution_binding() -> None:
    decision = _evaluate()
    field_names = {item.name for item in fields(ToolCallDecision)}

    assert field_names.isdisjoint(
        {"handler", "callable", "provider", "executor", "adapter"}
    )
    assert decision.capability_decision is not None
