from dataclasses import dataclass

from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.identifiers import TypedEntityId


@dataclass(frozen=True, slots=True)
class TypedEntityRef:
    """A generic reference to an entity identity."""

    entity_id: TypedEntityId

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, TypedEntityId):
            raise TypeError("entity_id must be a TypedEntityId")


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

    def __post_init__(self) -> None:
        if not isinstance(self.object_ref, TypedEntityRef):
            raise TypeError("object_ref must be a TypedEntityRef")
        if not isinstance(self.version_ref, VersionRef):
            raise TypeError("version_ref must be a VersionRef")
