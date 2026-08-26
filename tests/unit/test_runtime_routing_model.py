from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.agent_runtime.contracts import ExecutorKind, StepKind
from backend.agent_runtime.policy import PolicyFacts
from backend.agent_runtime.runtime.routing import (
    ResolvedAgentInput,
    ResolvedGateInput,
    ResolvedToolInput,
    ResolvedUseCaseInput,
)
from tests.support.runtime_routing_fakes import (
    make_gate_input,
    make_step,
    make_tool_input,
    make_use_case_input,
    permission_scope,
)


def test_typed_resolution_models_are_closed_and_immutable() -> None:
    use_case_step = make_step(StepKind.USE_CASE, "CAP-R01", ExecutorKind.APPLICATION)
    tool_step = make_step(StepKind.TOOL, "CAP-T02", ExecutorKind.UTILITY)
    gate_step = make_step(StepKind.GATE, "CAP-O05", ExecutorKind.RUNTIME)

    use_case = make_use_case_input(use_case_step)
    tool = make_tool_input(tool_step)
    gate = make_gate_input(gate_step)
    agent = ResolvedAgentInput(
        permission_scope_ref="scope-routing",
        permission_scope=permission_scope("CAP-E01"),
    )

    assert type(use_case) is ResolvedUseCaseInput
    assert type(tool) is ResolvedToolInput
    assert type(gate) is ResolvedGateInput
    assert type(agent.policy_facts) is PolicyFacts
    with pytest.raises(FrozenInstanceError):
        agent.scope_revoked = True  # type: ignore[misc]


def test_resolution_models_reject_generic_or_malformed_values() -> None:
    with pytest.raises(TypeError):
        ResolvedAgentInput(  # type: ignore[arg-type]
            permission_scope_ref="scope-routing",
            permission_scope={"capability": "CAP-E01"},
        )
    with pytest.raises(TypeError):
        ResolvedGateInput(gate_ref="gate-ref", request=object())  # type: ignore[arg-type]
