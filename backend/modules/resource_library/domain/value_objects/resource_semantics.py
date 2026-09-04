from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResourceAvailabilityStatus(StrEnum):
    """Whether the resource is known to be usable by the system."""

    UNKNOWN = "UNKNOWN"
    ACTIVE = "ACTIVE"


class ResourceCanonicalityStatus(StrEnum):
    """Whether the resource is known to carry canonical authority."""

    UNKNOWN = "UNKNOWN"
    CANONICAL = "CANONICAL"


@dataclass(frozen=True, slots=True)
class ResourceSemanticState:
    """Independent availability and canonicality observations.

    No implication between the two dimensions is encoded: the approved
    business decision separates them, while their relationship and transition
    authority remain unproven.
    """

    availability_status: ResourceAvailabilityStatus
    canonicality_status: ResourceCanonicalityStatus

    def __post_init__(self) -> None:
        if not isinstance(self.availability_status, ResourceAvailabilityStatus):
            raise TypeError(
                "availability_status must be a ResourceAvailabilityStatus"
            )
        if not isinstance(self.canonicality_status, ResourceCanonicalityStatus):
            raise TypeError(
                "canonicality_status must be a ResourceCanonicalityStatus"
            )
        if (
            self.availability_status is not ResourceAvailabilityStatus.UNKNOWN
            and self.canonicality_status is not ResourceCanonicalityStatus.UNKNOWN
        ):
            raise ValueError(
                "combined availability and canonicality observations are not authorized"
            )
