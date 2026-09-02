from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._strings import require_non_empty


class ProductionType(StrEnum):
    OTHER = "OTHER"


class ProductionLifecycleStatus(StrEnum):
    VALIDATED = "VALIDATED"


@dataclass(frozen=True, slots=True)
class ProductionTitle:
    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")
        if len(self.value) > 512:
            raise ValueError("value must contain at most 512 characters")


@dataclass(frozen=True, slots=True)
class ProductionPersistenceValues:
    production_type: ProductionType
    title: ProductionTitle
    lifecycle_status: ProductionLifecycleStatus

    def __post_init__(self) -> None:
        if not isinstance(self.production_type, ProductionType):
            raise TypeError("production_type must be a ProductionType")
        if not isinstance(self.title, ProductionTitle):
            raise TypeError("title must be a ProductionTitle")
        if not isinstance(self.lifecycle_status, ProductionLifecycleStatus):
            raise TypeError("lifecycle_status must be a ProductionLifecycleStatus")
