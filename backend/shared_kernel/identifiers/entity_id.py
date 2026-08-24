from dataclasses import dataclass

from backend.shared_kernel._strings import require_non_empty


@dataclass(frozen=True, slots=True)
class TypedEntityId:
    """An opaque identity qualified by a generic entity type."""

    entity_type: str
    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.entity_type, "entity_type")
        require_non_empty(self.value, "value")
