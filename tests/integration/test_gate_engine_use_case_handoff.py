from __future__ import annotations

from dataclasses import replace

import pytest

from backend.agent_runtime.application_routing import (
    UseCaseRoutingError,
    UseCaseRoutingErrorCode,
)
from backend.agent_runtime.contracts import AgentId, GateDecisionValue
from backend.agent_runtime.gates import (
    BASELINE_GATE_AUTHORITY_POLICY,
    GateEngine,
    GateResolutionDisposition,
)
from backend.shared_kernel.time import Instant
from tests.support.gate_fakes import (
    AFTER_EXPIRATION,
    NOW,
    RecordingGateDecisionSource,
    make_gate_decision,
    make_gate_request,
)
from tests.support.use_case_routing_fakes import make_request, make_router


@pytest.mark.parametrize(
    ("scenario", "decision_value", "consumed_at", "expected", "inbound_calls"),
    [
        ("waiting", None, NOW, GateResolutionDisposition.WAITING, 0),
        (
            "approved",
            GateDecisionValue.APPROVED,
            NOW,
            GateResolutionDisposition.APPROVED,
            1,
        ),
        (
            "rejected",
            GateDecisionValue.REJECTED,
            NOW,
            GateResolutionDisposition.REJECTED,
            0,
        ),
        (
            "deferred",
            GateDecisionValue.DEFERRED,
            NOW,
            GateResolutionDisposition.DEFERRED,
            0,
        ),
        (
            "expired",
            GateDecisionValue.APPROVED,
            AFTER_EXPIRATION,
            GateResolutionDisposition.EXPIRED,
            0,
        ),
    ],
)
def test_gate_resolution_is_the_only_bridge_to_a02_policy_re_evaluation(
    scenario: str,
    decision_value: GateDecisionValue | None,
    consumed_at: Instant,
    expected: GateResolutionDisposition,
    inbound_calls: int,
) -> None:
    gate_request = make_gate_request()
    decision = (
        make_gate_decision(gate_request, value=decision_value)
        if decision_value is not None
        else None
    )
    source = RecordingGateDecisionSource(decision)
    gate_engine = GateEngine(BASELINE_GATE_AUTHORITY_POLICY, source)
    resolution = gate_engine.evaluate(
        request=gate_request,
        now=consumed_at,
    )
    use_case_request, context = make_request(
        "application.request_promotion",
        idempotency_key=f"promotion-{scenario}",
    )
    routed_context = replace(context, policy_facts=resolution.to_policy_facts())
    router, inbound = make_router(use_case_request)

    assert resolution.disposition is expected
    if inbound_calls:
        result = router.route(
            agent_id=AgentId.AG_01,
            request=use_case_request,
            context=routed_context,
            evaluated_at=NOW,
        )
        assert result.use_case_id == "application.request_promotion"
    else:
        with pytest.raises(UseCaseRoutingError) as raised:
            router.route(
                agent_id=AgentId.AG_01,
                request=use_case_request,
                context=routed_context,
                evaluated_at=NOW,
            )
        assert raised.value.code is UseCaseRoutingErrorCode.REQUEST_NOT_ROUTABLE
    assert len(inbound.calls) == inbound_calls
    assert len(source.calls) == (0 if scenario == "expired" else 1)
