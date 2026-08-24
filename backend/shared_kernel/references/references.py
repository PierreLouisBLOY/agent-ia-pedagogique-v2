from dataclasses import dataclass

from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.identifiers import TypedEntityId


@dataclass(frozen=True, slots=True)
class TypedEntityRef:
    """A generic reference to an entity identity."""

    entity_id: TypedEntityId


@dataclass(frozen=True, slots=True)
class VersionRef:
    """An opaque version identifier independent from entity identity."""

    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")


@dataclass(frozen=True, slots=True)
class ObjectVersionRef:
    """A reference to one exact entity identity and one exact version."""

    object_ref: TypedEntityRef
    version_ref: VersionRef
