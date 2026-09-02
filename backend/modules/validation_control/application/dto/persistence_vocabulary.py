from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.shared_kernel._strings import require_non_empty


class ValidationType(StrEnum):
    RUNTIME_CONTRACT = "RUNTIME_CONTRACT"


class ValidationResult(StrEnum):
    PASS = "PASS"


@dataclass(frozen=True, slots=True)
class ValidatorRef:
    """Technical validator identity kept at the Application boundary."""

    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.value, "value")
        if len(self.value) > 256:
            raise ValueError("value must contain at most 256 characters")


@dataclass(frozen=True, slots=True)
class ValidationPersistenceValues:
    validation_type: ValidationType
    result: ValidationResult
    validator_ref: ValidatorRef

    def __post_init__(self) -> None:
        if not isinstance(self.validation_type, ValidationType):
            raise TypeError("validation_type must be a ValidationType")
        if not isinstance(self.result, ValidationResult):
            raise TypeError("result must be a ValidationResult")
        if not isinstance(self.validator_ref, ValidatorRef):
            raise TypeError("validator_ref must be a ValidatorRef")
