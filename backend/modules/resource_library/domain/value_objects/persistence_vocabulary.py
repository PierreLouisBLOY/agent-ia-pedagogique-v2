from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResourceType(StrEnum):
    """Resource kinds proven by the active contracts or persistence adapter."""

    OTHER = "OTHER"
    COURSE = "COURSE"
    EXERCISE_SET = "EXERCISE_SET"


class ResourceIdentityStatus(StrEnum):
    """Distinct observed values; their semantic relationship remains unresolved."""

    ACTIVE = "ACTIVE"
    CANONICAL = "CANONICAL"


@dataclass(frozen=True, slots=True)
class ResourcePersistenceValues:
    """M03-owned values supplied to the resource persistence adapter."""

    resource_type: ResourceType
    identity_status: ResourceIdentityStatus

    def __post_init__(self) -> None:
        if not isinstance(self.resource_type, ResourceType):
            raise TypeError("resource_type must be a ResourceType")
        if not isinstance(self.identity_status, ResourceIdentityStatus):
            raise TypeError("identity_status must be a ResourceIdentityStatus")
