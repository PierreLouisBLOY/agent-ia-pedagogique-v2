from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from backend.agent_runtime.contracts import ActorKind, ActorRef


@dataclass(frozen=True, slots=True)
class GateAuthorityPolicy:
    """Closed authority policy for external gate decision actors."""

    allowed_actor_kinds: tuple[ActorKind, ...] = (ActorKind.USER,)

    def __post_init__(self) -> None:
        kinds = tuple(self.allowed_actor_kinds)
        if any(not isinstance(kind, ActorKind) for kind in kinds):
            raise TypeError("allowed_actor_kinds must contain ActorKind values")
        if len(kinds) != len(set(kinds)):
            raise ValueError("allowed_actor_kinds must be unique")
        if not kinds:
            raise ValueError("at least one gate authority kind is required")
        if ActorKind.AGENT in kinds:
            raise ValueError("agent actors can never hold gate authority")
        object.__setattr__(self, "allowed_actor_kinds", kinds)

    def allows(self, actor: ActorRef) -> bool:
        if not isinstance(actor, ActorRef):
            raise TypeError("actor must be an ActorRef")
        return actor.kind in self.allowed_actor_kinds


BASELINE_GATE_AUTHORITY_POLICY: Final = GateAuthorityPolicy()
