from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._strings import require_non_empty


class PromotionStatus(StrEnum):
    PROMOTED = "PROMOTED"


@dataclass(frozen=True, slots=True)
class PromotionJustification:
    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")
        if len(self.value) > 2000:
            raise ValueError("value must contain at most 2000 characters")


@dataclass(frozen=True, slots=True)
class PromotionPersistenceValues:
    status: PromotionStatus
    justification: PromotionJustification

    def __post_init__(self) -> None:
        if not isinstance(self.status, PromotionStatus):
            raise TypeError("status must be a PromotionStatus")
        if not isinstance(self.justification, PromotionJustification):
            raise TypeError("justification must be a PromotionJustification")
