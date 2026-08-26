from __future__ import annotations

from dataclasses import replace

import pytest

from backend.agent_runtime.contracts import ExecutorKind, StepKind
from backend.agent_runtime.policy import CapabilityAuthorizationPolicy
from backend.agent_runtime.runtime import StepRuntimeStatus
from backend.agent_runtime.runtime.routing import (
    AgentStepBindings,
    AgentStepRouter,
    ResolvedAgentInput,
    RuntimeRoutingError,
)
from tests.support.runtime_routing_fakes import (
    NOW,
    RecordingAgentPort,
    make_plan,
    make_run_state,
    make_step,
    permission_scope,
)


@pytest.mark.parametrize(
    ("capability", "executor", "port_index"),
    [
        ("CAP-E03", ExecutorKind.AG_02, 0),
        ("CAP-G01", ExecutorKind.AG_03, 1),
        ("CAP-V02", ExecutorKind.AG_04, 2),
    ],
)
def test_agent_route_requires_delegate_to_exact_owner(
    capability: str, executor: ExecutorKind, port_index: int
) -> None:
    ports = (RecordingAgentPort(), RecordingAgentPort(), RecordingAgentPort())
    router = AgentStepRouter(
        CapabilityAuthorizationPolicy(),
        AgentStepBindings(ag_02=ports[0], ag_03=ports[1], ag_04=ports[2]),
    )
    step = make_step(StepKind.AGENT, capability, executor)
    plan = make_plan(step)
    resolved = ResolvedAgentInput(
        permission_scope_ref="scope-routing",
        permission_scope=permission_scope(capability),
    )

    result = router.route(
        plan=plan,
        step=step,
        run_state=make_run_state(plan),
        resolved=resolved,
        attempt=1,
        now=NOW,
    )

    assert result.status is StepRuntimeStatus.SUCCEEDED
    assert ports[port_index].calls == [step.step_id]
    assert sum(len(port.calls) for port in ports) == 1


def test_wrong_agent_owner_fails_before_port_call() -> None:
    ports = (RecordingAgentPort(), RecordingAgentPort(), RecordingAgentPort())
    router = AgentStepRouter(
        CapabilityAuthorizationPolicy(),
        AgentStepBindings(ag_02=ports[0], ag_03=ports[1], ag_04=ports[2]),
    )
    step = make_step(StepKind.AGENT, "CAP-G01", ExecutorKind.AG_02)
    resolved = ResolvedAgentInput(
        permission_scope_ref="scope-routing",
        permission_scope=permission_scope("CAP-G01"),
    )

    with pytest.raises(RuntimeRoutingError):
        router.authorize(step=step, resolved=resolved, evaluated_at=NOW)

    assert all(port.calls == [] for port in ports)


def test_permission_scope_ref_mismatch_fails_closed() -> None:
    port = RecordingAgentPort()
    router = AgentStepRouter(
        CapabilityAuthorizationPolicy(),
        AgentStepBindings(ag_02=port, ag_03=port, ag_04=port),
    )
    step = make_step(StepKind.AGENT, "CAP-E01", ExecutorKind.AG_02)
    resolved = replace(
        ResolvedAgentInput(
            permission_scope_ref="scope-routing",
            permission_scope=permission_scope("CAP-E01"),
        ),
        permission_scope_ref="scope-forged",
    )

    with pytest.raises(RuntimeRoutingError):
        router.authorize(step=step, resolved=resolved, evaluated_at=NOW)

    assert port.calls == []
