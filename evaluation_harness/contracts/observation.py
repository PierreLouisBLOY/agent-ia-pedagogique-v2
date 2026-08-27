from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Final

from evaluation_harness.contracts.identity import EvaluationObservationFieldCode

MAX_OBSERVATION_DEPTH: Final = 8
MAX_OBSERVATION_SEQUENCE_LENGTH: Final = 64
MAX_OBSERVATION_OBJECT_FIELDS: Final = 32
MAX_OBSERVATION_STRING_LENGTH: Final = 4_096
MAX_OBSERVATION_TOTAL_NODES: Final = 512
MAX_OBSERVATION_INTEGER_ABS: Final = 10**128 - 1
MAX_OBSERVATION_DECIMAL_DIGITS: Final = 128
MAX_OBSERVATION_DECIMAL_EXPONENT_ABS: Final = 128


class ObservationScalarKind(Enum):
    NULL = "NULL"
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    STRING = "STRING"


type ObservationScalarValue = None | bool | int | Decimal | str


@dataclass(frozen=True, slots=True)
class ObservationScalar:
    """Canonical scalar; strings may contain bounded synthetic adversarial data."""

    kind: ObservationScalarKind
    value: ObservationScalarValue

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ObservationScalarKind):
            raise TypeError("kind must be an ObservationScalarKind")
        if self.kind is ObservationScalarKind.NULL:
            if self.value is not None:
                raise TypeError("a NULL observation requires None")
            return
        if self.kind is ObservationScalarKind.BOOLEAN:
            if type(self.value) is not bool:
                raise TypeError("a BOOLEAN observation requires bool")
            return
        if self.kind is ObservationScalarKind.INTEGER:
            if type(self.value) is not int:
                raise TypeError("an INTEGER observation requires int")
            if abs(self.value) > MAX_OBSERVATION_INTEGER_ABS:
                raise ValueError("integer observation exceeds the offline limit")
            return
        if self.kind is ObservationScalarKind.DECIMAL:
            if type(self.value) is not Decimal:
                raise TypeError("a DECIMAL observation requires Decimal")
            _validate_decimal(self.value)
            return
        if type(self.value) is not str:
            raise TypeError("a STRING observation requires str")
        if len(self.value) > MAX_OBSERVATION_STRING_LENGTH:
            raise ValueError("string observation exceeds the offline limit")


@dataclass(frozen=True, slots=True)
class ObservationSequence:
    items: tuple[EvaluationObservationValue, ...]

    def __post_init__(self) -> None:
        if type(self.items) is not tuple:
            raise TypeError("observation sequence items must be a tuple")
        if len(self.items) > MAX_OBSERVATION_SEQUENCE_LENGTH:
            raise ValueError("observation sequence exceeds the offline limit")
        validate_observation_value(self)


@dataclass(frozen=True, slots=True)
class ObservationField:
    code: EvaluationObservationFieldCode
    value: EvaluationObservationValue

    def __post_init__(self) -> None:
        if not isinstance(self.code, EvaluationObservationFieldCode):
            raise TypeError("code must be an EvaluationObservationFieldCode")
        validate_observation_value(self.value)


@dataclass(frozen=True, slots=True)
class ObservationObject:
    fields: tuple[ObservationField, ...]

    def __post_init__(self) -> None:
        if type(self.fields) is not tuple:
            raise TypeError("observation object fields must be a tuple")
        if len(self.fields) > MAX_OBSERVATION_OBJECT_FIELDS:
            raise ValueError("observation object exceeds the offline field limit")
        if any(type(field) is not ObservationField for field in self.fields):
            raise TypeError("observation object must contain ObservationField values")
        codes = tuple(field.code for field in self.fields)
        if len(codes) != len(set(codes)):
            raise ValueError("observation object field codes must be unique")
        validate_observation_value(self)


type EvaluationObservationValue = (
    ObservationScalar | ObservationSequence | ObservationObject
)


def validate_observation_value(value: EvaluationObservationValue) -> None:
    """Validate the complete immutable graph without reflecting runtime objects."""

    stack: list[tuple[object, int]] = [(value, 0)]
    visited = 0
    while stack:
        current, depth = stack.pop()
        visited += 1
        if visited > MAX_OBSERVATION_TOTAL_NODES:
            raise ValueError("observation graph exceeds the offline node limit")
        if depth > MAX_OBSERVATION_DEPTH:
            raise ValueError("observation graph exceeds the offline depth limit")
        if type(current) is ObservationScalar:
            continue
        if type(current) is ObservationSequence:
            if len(current.items) > MAX_OBSERVATION_SEQUENCE_LENGTH:
                raise ValueError("observation sequence exceeds the offline limit")
            stack.extend((item, depth + 1) for item in reversed(current.items))
            continue
        if type(current) is ObservationObject:
            if len(current.fields) > MAX_OBSERVATION_OBJECT_FIELDS:
                raise ValueError("observation object exceeds the offline field limit")
            stack.extend(
                (field.value, depth + 1) for field in reversed(current.fields)
            )
            continue
        raise TypeError("unsupported canonical observation value")


def _validate_decimal(value: Decimal) -> None:
    if not value.is_finite():
        raise ValueError("decimal observation must be finite")
    representation = value.as_tuple()
    if len(representation.digits) > MAX_OBSERVATION_DECIMAL_DIGITS:
        raise ValueError("decimal observation exceeds the offline digit limit")
    exponent = representation.exponent
    if not isinstance(exponent, int):
        raise ValueError("decimal observation must have a finite exponent")
    if abs(exponent) > MAX_OBSERVATION_DECIMAL_EXPONENT_ABS:
        raise ValueError("decimal observation exceeds the offline exponent limit")
