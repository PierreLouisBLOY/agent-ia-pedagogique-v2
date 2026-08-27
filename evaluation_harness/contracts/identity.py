from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from backend.shared_kernel._value_safety import (
    SensitiveValueClass,
    classify_sensitive_text,
)

MAX_IDENTIFIER_LENGTH: Final = 128
MAX_TITLE_LENGTH: Final = 256
MAX_TAGS: Final = 16
MAX_CASES_PER_SUITE: Final = 256
MAX_ASSERTION_REFS_PER_CASE: Final = 64
MAX_OBSERVATION_REFS_PER_EXECUTION: Final = 64
MAX_REASON_CODES_PER_RESULT: Final = 32
MAX_REPEAT_COUNT: Final = 100
MAX_TIMEOUT_SECONDS: Final = 86_400
MAX_DURATION_MILLISECONDS: Final = 86_400_000

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SAFE_TAG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SAFE_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_.-]{0,127}$")


@dataclass(frozen=True, slots=True)
class EvaluationSchemaVersion:
    """Version of offline evaluation contracts, independent from runtime schemas."""

    major: int
    minor: int

    def __post_init__(self) -> None:
        for field_name in ("major", "minor"):
            value = getattr(self, field_name)
            if type(value) is not int:
                raise TypeError(f"{field_name} must be an integer")
            if not 0 <= value <= 255:
                raise ValueError(f"{field_name} must be between 0 and 255")
        if self.major == 0:
            raise ValueError("major must be >= 1")


EVALUATION_SCHEMA_V1_0: Final = EvaluationSchemaVersion(major=1, minor=0)
SUPPORTED_EVALUATION_SCHEMA_VERSIONS: Final = frozenset({EVALUATION_SCHEMA_V1_0})


def require_supported_schema_version(value: EvaluationSchemaVersion) -> None:
    if not isinstance(value, EvaluationSchemaVersion):
        raise TypeError("schema_version must be an EvaluationSchemaVersion")
    if value not in SUPPORTED_EVALUATION_SCHEMA_VERSIONS:
        raise ValueError("schema_version is not supported by this evaluation contract")


def require_safe_title(value: str) -> None:
    if type(value) is not str:
        raise TypeError("title must be a string")
    if not value or value != value.strip():
        raise ValueError("title must be non-empty and normalized")
    if len(value) > MAX_TITLE_LENGTH:
        raise ValueError("title exceeds the offline evaluation limit")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("title contains a control character")
    if "://" in value or value.startswith(("/", "~/", "~\\")):
        raise ValueError("title must not contain an external or private reference")
    if classify_sensitive_text(value) is not SensitiveValueClass.SAFE_VALUE:
        raise ValueError("title must not contain a sensitive value")


def _require_safe_identifier(value: str, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field_name} must be a bounded opaque identifier")
    if classify_sensitive_text(value) is not SensitiveValueClass.SAFE_VALUE:
        raise ValueError(f"{field_name} must not contain a sensitive value")


@dataclass(frozen=True, slots=True)
class _EvaluationIdentifier:
    value: str

    def __post_init__(self) -> None:
        _require_safe_identifier(self.value, type(self).__name__)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class EvaluationCaseId(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationSuiteId(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationCaseCode(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationSuiteCode(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationTargetCode(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationFixtureRef(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationInputFactoryRef(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationAssertionRef(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationObservationRef(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationObservationFieldCode(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationInvariantCode(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationScorerRef(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationRubricRef(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationCriterionRef(_EvaluationIdentifier):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationReasonCode:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str:
            raise TypeError("reason code must be a string")
        if not _SAFE_REASON_CODE.fullmatch(self.value):
            raise ValueError("reason code must be a bounded closed code")
        if classify_sensitive_text(self.value) is not SensitiveValueClass.SAFE_VALUE:
            raise ValueError("reason code must not contain a sensitive value")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class EvaluationTagCode:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str:
            raise TypeError("tag code must be a string")
        if not _SAFE_TAG.fullmatch(self.value):
            raise ValueError("tag code must be a normalized bounded identifier")
        if classify_sensitive_text(self.value) is not SensitiveValueClass.SAFE_VALUE:
            raise ValueError("tag code must not contain a sensitive value")

    def __str__(self) -> str:
        return self.value


def require_unique_bounded_tags(tags: tuple[EvaluationTagCode, ...]) -> None:
    if type(tags) is not tuple:
        raise TypeError("tags must be a tuple")
    if len(tags) > MAX_TAGS:
        raise ValueError("too many evaluation tags")
    if any(type(tag) is not EvaluationTagCode for tag in tags):
        raise TypeError("tags must contain EvaluationTagCode values")
    if len(tags) != len(set(tags)):
        raise ValueError("evaluation tags must be unique")
