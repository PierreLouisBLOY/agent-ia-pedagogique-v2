from __future__ import annotations

from dataclasses import replace

import pytest

from backend.agent_runtime.application_routing import (
    UseCaseRoutingError,
    UseCaseRoutingErrorCode,
)
from backend.agent_runtime.contracts import ActorKind, ActorRef, AgentId, ExecutorKind, StepKind
from backend.agent_runtime.policy import (
    AuthorityKind,
    CapabilityPolicyDecision,
    PolicyDecisionCode,
    PolicyDisposition,
    PolicyFacts,
    ScopeEvaluation,
    ScopeEvaluationCode,
)
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.core_contracts.capability import CapabilityId
from tests.support.use_case_routing_fakes import (
    NOW,
    FixedDecisionPolicy,
    make_request,
    make_router,
)


def _route(router: object, request: object, context: object) -> object:
    return router.route(  # type: ignore[attr-defined]
        agent_id=AgentId.AG_01,
        request=request,
        context=context,
        evaluated_at=NOW,
    )


def _fixed_decision(disposition: PolicyDisposition) -> CapabilityPolicyDecision:
    codes = {
        PolicyDisposition.DENY: PolicyDecisionCode.MATRIX_DENY,
        PolicyDisposition.ALLOW: PolicyDecisionCode.ALLOW,
        PolicyDisposition.DELEGATE: PolicyDecisionCode.DELEGATE_AGENT,
        PolicyDisposition.REQUEST_GATE: PolicyDecisionCode.GATE_REQUIRED,
        PolicyDisposition.CONDITION_REQUIRED: PolicyDecisionCode.CONDITION_REQUIRED,
    }
    return CapabilityPolicyDecision(
        disposition=disposition,
        code=codes[disposition],
        capability_id=CapabilityId("CAP-R01"),
        agent_id=AgentId.AG_01,
        route=CapabilityExecutionRoute.APPLICATION,
        authority=AuthorityKind.APPLICATION,
        scope_evaluation=(
            None
            if disposition is PolicyDisposition.DENY
            else ScopeEvaluation(True, ScopeEvaluationCode.ALLOW)
        ),
        target_agent=(AgentId.AG_02 if disposition is PolicyDisposition.DELEGATE else None),
    )


def test_read_request_routes_once_and_returns_reconstructed_result() -> None:
    request, context = make_request()
    router, inbound = make_router(request)

    result = _route(router, request, context)

    assert len(inbound.calls) == 1
    assert inbound.calls[0] is request
    assert result.use_case_id == request.use_case_id
    assert result.meta.correlation_id == request.meta.correlation_id


@pytest.mark.parametrize(
    ("request_changes", "context_changes", "code"),
    [
        ({"use_case_id": "application.unknown"}, {}, UseCaseRoutingErrorCode.UNKNOWN_USE_CASE),
        ({}, {"step_kind": StepKind.AGENT}, UseCaseRoutingErrorCode.STEP_KIND_MISMATCH),
        (
            {},
            {"executor_kind": ExecutorKind.UTILITY},
            UseCaseRoutingErrorCode.EXECUTOR_MISMATCH,
        ),
        (
            {},
            {"capability_code": "CAP-R02"},
            UseCaseRoutingErrorCode.CAPABILITY_USE_CASE_MISMATCH,
        ),
        (
            {},
            {"capability_code": "CAP-T01"},
            UseCaseRoutingErrorCode.NON_APPLICATION_CAPABILITY,
        ),
    ],
)
def test_invalid_identity_or_step_never_calls_inbound(
    request_changes: dict[str, object],
    context_changes: dict[str, object],
    code: UseCaseRoutingErrorCode,
) -> None:
    use_case_id = str(request_changes.get("use_case_id", "application.read_canonical_resource"))
    request, _ = make_request(
        use_case_id,
        capability_code="CAP-R01" if use_case_id == "application.unknown" else None,
    )
    _, context = make_request(**context_changes)  # type: ignore[arg-type]
    router, inbound = make_router(request)

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)

    assert raised.value.code is code
    assert inbound.calls == []


def test_missing_binding_fails_after_policy_without_call() -> None:
    request, context = make_request()
    router, inbound = make_router(request, bind=False)

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)

    assert raised.value.code is UseCaseRoutingErrorCode.USE_CASE_NOT_BOUND
    assert inbound.calls == []


def test_scope_denial_and_scope_reference_mismatch_never_call_inbound() -> None:
    request, context = make_request()
    denied_context = replace(
        context,
        permission_scope=replace(context.permission_scope, operations=()),
    )
    mismatched_ref_context = replace(context, permission_scope_ref="other-scope")

    for rejected_context in (denied_context, mismatched_ref_context):
        router, inbound = make_router(request)
        with pytest.raises(UseCaseRoutingError):
            _route(router, request, rejected_context)
        assert inbound.calls == []


@pytest.mark.parametrize(
    "disposition",
    [
        PolicyDisposition.DENY,
        PolicyDisposition.ALLOW,
        PolicyDisposition.DELEGATE,
        PolicyDisposition.REQUEST_GATE,
        PolicyDisposition.CONDITION_REQUIRED,
    ],
)
def test_every_non_request_policy_disposition_is_non_routable(
    disposition: PolicyDisposition,
) -> None:
    request, context = make_request()
    router, inbound = make_router(
        request,
        policy=FixedDecisionPolicy(_fixed_decision(disposition)),
    )

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)

    assert raised.value.code is UseCaseRoutingErrorCode.REQUEST_NOT_ROUTABLE
    assert inbound.calls == []


def test_final_conditional_request_disposition_is_routable() -> None:
    request, context = make_request()
    decision = CapabilityPolicyDecision(
        disposition=PolicyDisposition.REQUEST,
        code=PolicyDecisionCode.CONDITIONAL_REQUEST,
        capability_id=CapabilityId("CAP-R01"),
        agent_id=AgentId.AG_01,
        route=CapabilityExecutionRoute.APPLICATION,
        authority=AuthorityKind.APPLICATION,
        scope_evaluation=ScopeEvaluation(True, ScopeEvaluationCode.ALLOW),
    )
    router, inbound = make_router(request, policy=FixedDecisionPolicy(decision))

    _route(router, request, context)

    assert len(inbound.calls) == 1


def test_a02_requires_trusted_gate_fact_and_never_creates_it() -> None:
    request, context = make_request(
        "application.request_promotion",
        idempotency_key="promotion-1",
    )
    router, inbound = make_router(request)

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)
    assert raised.value.code is UseCaseRoutingErrorCode.REQUEST_NOT_ROUTABLE
    assert inbound.calls == []

    trusted_context = replace(
        context,
        policy_facts=PolicyFacts(matrix_gate_satisfied=True),
    )
    result = _route(router, request, trusted_context)
    assert result.outcome.success
    assert len(inbound.calls) == 1


def test_mutating_use_cases_require_idempotency_key() -> None:
    request, context = make_request("application.export_artifact")
    router, inbound = make_router(request)

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)

    assert raised.value.code is UseCaseRoutingErrorCode.IDEMPOTENCY_REQUIRED
    assert inbound.calls == []


@pytest.mark.parametrize(
    ("payload", "requested_effect"),
    [
        ({"nested": {"capabilityId": "CAP-A02"}}, {}),
        ({}, {"items": ({"gate_approved": True},)}),
        ({"handlerPath": "backend.hidden"}, {}),
    ],
)
def test_authority_metadata_smuggling_never_calls_inbound(
    payload: dict[str, object],
    requested_effect: dict[str, object],
) -> None:
    request, context = make_request(payload=payload, requested_effect=requested_effect)
    router, inbound = make_router(request)

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)

    assert raised.value.code is UseCaseRoutingErrorCode.AUTHORITY_METADATA_FORBIDDEN
    assert inbound.calls == []


def test_business_status_and_validation_keys_are_not_overblocked() -> None:
    request, context = make_request(
        payload={"status": "draft", "validation": {"expected": "strict"}}
    )
    router, inbound = make_router(request)

    _route(router, request, context)

    assert len(inbound.calls) == 1


def test_invalid_actor_and_scope_binding_never_call_inbound() -> None:
    request, context = make_request(
        actor=ActorRef(ActorKind.USER, "user-1"),
    )
    router, inbound = make_router(request)

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)

    assert raised.value.code is UseCaseRoutingErrorCode.INVALID_ROUTING_CONTEXT
    assert inbound.calls == []


def test_inbound_exception_is_safe_and_not_retried() -> None:
    request, context = make_request()
    router, inbound = make_router(
        request,
        inbound_error=RuntimeError("sensitive persistence detail"),
    )

    with pytest.raises(UseCaseRoutingError) as raised:
        _route(router, request, context)

    assert raised.value.code is UseCaseRoutingErrorCode.INBOUND_FAILED
    assert "sensitive" not in str(raised.value)
    assert len(inbound.calls) == 1
