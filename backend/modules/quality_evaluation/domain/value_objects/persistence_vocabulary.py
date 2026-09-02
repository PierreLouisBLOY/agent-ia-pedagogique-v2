from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class QualityEvaluationStatus(StrEnum):
    COMPLETED = "COMPLETED"


@dataclass(frozen=True, slots=True)
class QualityScore:
    value: float

    def __post_init__(self) -> None:
        if not isinstance(self.value, float):
            raise TypeError("value must be a float")
        if not math.isfinite(self.value) or not 0.0 <= self.value <= 1.0:
            raise ValueError("value must be finite and between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class QualityPersistenceValues:
    status: QualityEvaluationStatus
    score: QualityScore

    def __post_init__(self) -> None:
        if not isinstance(self.status, QualityEvaluationStatus):
            raise TypeError("status must be a QualityEvaluationStatus")
        if not isinstance(self.score, QualityScore):
            raise TypeError("score must be a QualityScore")
