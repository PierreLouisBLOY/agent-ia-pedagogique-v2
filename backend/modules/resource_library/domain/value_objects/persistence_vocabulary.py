from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.modules.resource_library.domain.value_objects.resource_semantics import (
    ResourceSemanticState,
)


class ResourceType(StrEnum):
    """Resource kinds proven by the active contracts or persistence adapter."""

    OTHER = "OTHER"
    COURSE = "COURSE"
    EXERCISE_SET = "EXERCISE_SET"


@dataclass(frozen=True, slots=True)
class ResourcePersistenceValues:
    """M03-owned values supplied to the resource persistence adapter.

    The physical legacy column is intentionally hidden behind the outbound
    mapper; Domain owns two independent semantic dimensions.
    """

    resource_type: ResourceType
    semantic_state: ResourceSemanticState

    def __post_init__(self) -> None:
        if not isinstance(self.resource_type, ResourceType):
            raise TypeError("resource_type must be a ResourceType")
        if not isinstance(self.semantic_state, ResourceSemanticState):
            raise TypeError("semantic_state must be a ResourceSemanticState")
