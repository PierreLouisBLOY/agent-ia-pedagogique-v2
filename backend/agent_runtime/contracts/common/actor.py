from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._strings import require_non_empty


class ActorKind(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    APPLICATION = "APPLICATION"
    TOOL = "TOOL"
    SYSTEM = "SYSTEM"
    PROVIDER = "PROVIDER"


@dataclass(frozen=True, slots=True)
class ActorRef:
    """Opaque runtime actor reference without auth or access-control semantics."""

    kind: ActorKind
    actor_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ActorKind):
            raise TypeError("kind must be an ActorKind")
        require_non_empty(self.actor_id, "actor_id")
