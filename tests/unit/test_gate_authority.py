from dataclasses import FrozenInstanceError

import pytest

from backend.agent_runtime.contracts import ActorKind, ActorRef, AgentId
from backend.agent_runtime.gates import (
    BASELINE_GATE_AUTHORITY_POLICY,
    GateAuthorityPolicy,
)


def test_baseline_gate_authority_allows_only_user() -> None:
    assert BASELINE_GATE_AUTHORITY_POLICY.allowed_actor_kinds == (ActorKind.USER,)
    assert BASELINE_GATE_AUTHORITY_POLICY.allows(ActorRef(ActorKind.USER, "user-1"))

    for kind in ActorKind:
        if kind is not ActorKind.USER:
            assert not BASELINE_GATE_AUTHORITY_POLICY.allows(
                ActorRef(kind, f"{kind.value.casefold()}-1")
            )


@pytest.mark.parametrize("agent_id", tuple(AgentId))
def test_every_runtime_agent_is_denied(agent_id: AgentId) -> None:
    actor = ActorRef(ActorKind.AGENT, agent_id.value)

    assert not BASELINE_GATE_AUTHORITY_POLICY.allows(actor)


def test_agent_kind_cannot_be_configured_as_gate_authority() -> None:
    with pytest.raises(ValueError):
        GateAuthorityPolicy((ActorKind.USER, ActorKind.AGENT))


def test_gate_authority_policy_is_frozen_and_rejects_duplicates() -> None:
    with pytest.raises(FrozenInstanceError):
        BASELINE_GATE_AUTHORITY_POLICY.allowed_actor_kinds = ()  # type: ignore[misc]
    with pytest.raises(ValueError):
        GateAuthorityPolicy((ActorKind.USER, ActorKind.USER))
