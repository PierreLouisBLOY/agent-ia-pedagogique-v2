from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from evaluation_harness.contracts.identity import (
    EvaluationAssertionRef,
    EvaluationInvariantCode,
    EvaluationObservationRef,
    EvaluationSchemaVersion,
    require_supported_schema_version,
)
from evaluation_harness.contracts.verdict import EvaluationVerdict

MAX_ASSERTION_SPECS_PER_CATALOG = 512
MAX_FORBIDDEN_CONTENT_REFS = 32
MAX_EXACT_COUNT = 512


class AssertionKind(Enum):
    EXACT = "EXACT"
    STRUCTURAL = "STRUCTURAL"
    COUNT = "COUNT"
    SEQUENCE = "SEQUENCE"
    MEMBERSHIP = "MEMBERSHIP"
    RANGE = "RANGE"
    FORBIDDEN_CONTENT = "FORBIDDEN_CONTENT"
    INVARIANT = "INVARIANT"


class AssertionReasonCode(Enum):
    EXACT_MISMATCH = "EXACT_MISMATCH"
    STRUCTURE_MISMATCH = "STRUCTURE_MISMATCH"
    COUNT_MISMATCH = "COUNT_MISMATCH"
    SEQUENCE_MISMATCH = "SEQUENCE_MISMATCH"
    MEMBERSHIP_MISMATCH = "MEMBERSHIP_MISMATCH"
    RANGE_MISMATCH = "RANGE_MISMATCH"
    FORBIDDEN_CONTENT_FOUND = "FORBIDDEN_CONTENT_FOUND"
    INVARIANT_FAILED = "INVARIANT_FAILED"
    INVARIANT_INCONCLUSIVE = "INVARIANT_INCONCLUSIVE"
    OBSERVATION_NOT_FOUND = "OBSERVATION_NOT_FOUND"
    OBSERVATION_TYPE_UNSUPPORTED = "OBSERVATION_TYPE_UNSUPPORTED"
    INVALID_ASSERTION_CONFIGURATION = "INVALID_ASSERTION_CONFIGURATION"
    INVARIANT_NOT_FOUND = "INVARIANT_NOT_FOUND"
    INVARIANT_EVALUATION_ERROR = "INVARIANT_EVALUATION_ERROR"
    OBSERVATION_RESOLUTION_ERROR = "OBSERVATION_RESOLUTION_ERROR"


@dataclass(frozen=True, slots=True)
class ExactAssertionSpec:
    assertion_ref: EvaluationAssertionRef
    schema_version: EvaluationSchemaVersion
    subject_ref: EvaluationObservationRef
    expected_ref: EvaluationObservationRef

    def __post_init__(self) -> None:
        _validate_common_spec(self.assertion_ref, self.schema_version)
        _require_observation_ref(self.subject_ref, "subject_ref")
        _require_observation_ref(self.expected_ref, "expected_ref")

    @property
    def kind(self) -> AssertionKind:
        return AssertionKind.EXACT


@dataclass(frozen=True, slots=True)
class StructuralAssertionSpec:
    assertion_ref: EvaluationAssertionRef
    schema_version: EvaluationSchemaVersion
    subject_ref: EvaluationObservationRef
    expected_ref: EvaluationObservationRef

    def __post_init__(self) -> None:
        _validate_common_spec(self.assertion_ref, self.schema_version)
        _require_observation_ref(self.subject_ref, "subject_ref")
        _require_observation_ref(self.expected_ref, "expected_ref")

    @property
    def kind(self) -> AssertionKind:
        return AssertionKind.STRUCTURAL


@dataclass(frozen=True, slots=True)
class CountAssertionSpec:
    assertion_ref: EvaluationAssertionRef
    schema_version: EvaluationSchemaVersion
    subject_ref: EvaluationObservationRef
    expected_count: int

    def __post_init__(self) -> None:
        _validate_common_spec(self.assertion_ref, self.schema_version)
        _require_observation_ref(self.subject_ref, "subject_ref")
        if type(self.expected_count) is not int:
            raise TypeError("expected_count must be an integer")
        if not 0 <= self.expected_count <= MAX_EXACT_COUNT:
            raise ValueError("expected_count exceeds the offline assertion limit")

    @property
    def kind(self) -> AssertionKind:
        return AssertionKind.COUNT


@dataclass(frozen=True, slots=True)
class SequenceAssertionSpec:
    assertion_ref: EvaluationAssertionRef
    schema_version: EvaluationSchemaVersion
    subject_ref: EvaluationObservationRef
    expected_ref: EvaluationObservationRef

    def __post_init__(self) -> None:
        _validate_common_spec(self.assertion_ref, self.schema_version)
        _require_observation_ref(self.subject_ref, "subject_ref")
        _require_observation_ref(self.expected_ref, "expected_ref")

    @property
    def kind(self) -> AssertionKind:
        return AssertionKind.SEQUENCE


@dataclass(frozen=True, slots=True)
class MembershipAssertionSpec:
    assertion_ref: EvaluationAssertionRef
    schema_version: EvaluationSchemaVersion
    subject_ref: EvaluationObservationRef
    member_ref: EvaluationObservationRef

    def __post_init__(self) -> None:
        _validate_common_spec(self.assertion_ref, self.schema_version)
        _require_observation_ref(self.subject_ref, "subject_ref")
        _require_observation_ref(self.member_ref, "member_ref")

    @property
    def kind(self) -> AssertionKind:
        return AssertionKind.MEMBERSHIP


@dataclass(frozen=True, slots=True)
class RangeAssertionSpec:
    assertion_ref: EvaluationAssertionRef
    schema_version: EvaluationSchemaVersion
    subject_ref: EvaluationObservationRef
    minimum_ref: EvaluationObservationRef | None = None
    maximum_ref: EvaluationObservationRef | None = None
    include_minimum: bool = True
    include_maximum: bool = True

    def __post_init__(self) -> None:
        _validate_common_spec(self.assertion_ref, self.schema_version)
        _require_observation_ref(self.subject_ref, "subject_ref")
        if self.minimum_ref is None and self.maximum_ref is None:
            raise ValueError("a range assertion requires at least one bound ref")
        for field_name in ("minimum_ref", "maximum_ref"):
            value = getattr(self, field_name)
            if value is not None:
                _require_observation_ref(value, field_name)
        if type(self.include_minimum) is not bool or type(self.include_maximum) is not bool:
            raise TypeError("range inclusivity flags must be booleans")

    @property
    def kind(self) -> AssertionKind:
        return AssertionKind.RANGE


@dataclass(frozen=True, slots=True)
class ForbiddenContentAssertionSpec:
    assertion_ref: EvaluationAssertionRef
    schema_version: EvaluationSchemaVersion
    subject_ref: EvaluationObservationRef
    forbidden_refs: tuple[EvaluationObservationRef, ...]
    case_sensitive: bool = True

    def __post_init__(self) -> None:
        _validate_common_spec(self.assertion_ref, self.schema_version)
        _require_observation_ref(self.subject_ref, "subject_ref")
        if type(self.forbidden_refs) is not tuple:
            raise TypeError("forbidden_refs must be a tuple")
        if not self.forbidden_refs:
            raise ValueError("forbidden content requires at least one ref")
        if len(self.forbidden_refs) > MAX_FORBIDDEN_CONTENT_REFS:
            raise ValueError("too many forbidden content refs")
        if any(
            type(reference) is not EvaluationObservationRef
            for reference in self.forbidden_refs
        ):
            raise TypeError("forbidden_refs must contain EvaluationObservationRef values")
        if len(self.forbidden_refs) != len(set(self.forbidden_refs)):
            raise ValueError("forbidden content refs must be unique")
        if type(self.case_sensitive) is not bool:
            raise TypeError("case_sensitive must be a boolean")

    @property
    def kind(self) -> AssertionKind:
        return AssertionKind.FORBIDDEN_CONTENT


@dataclass(frozen=True, slots=True)
class InvariantAssertionSpec:
    assertion_ref: EvaluationAssertionRef
    schema_version: EvaluationSchemaVersion
    subject_ref: EvaluationObservationRef
    invariant_code: EvaluationInvariantCode

    def __post_init__(self) -> None:
        _validate_common_spec(self.assertion_ref, self.schema_version)
        _require_observation_ref(self.subject_ref, "subject_ref")
        if not isinstance(self.invariant_code, EvaluationInvariantCode):
            raise TypeError("invariant_code must be an EvaluationInvariantCode")

    @property
    def kind(self) -> AssertionKind:
        return AssertionKind.INVARIANT


type AssertionSpec = (
    ExactAssertionSpec
    | StructuralAssertionSpec
    | CountAssertionSpec
    | SequenceAssertionSpec
    | MembershipAssertionSpec
    | RangeAssertionSpec
    | ForbiddenContentAssertionSpec
    | InvariantAssertionSpec
)


@dataclass(frozen=True, slots=True)
class AssertionResult:
    """Raw-value-free result of one normative offline assertion."""

    schema_version: EvaluationSchemaVersion
    assertion_ref: EvaluationAssertionRef
    kind: AssertionKind
    verdict: EvaluationVerdict
    reason_code: AssertionReasonCode | None = None

    def __post_init__(self) -> None:
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.assertion_ref, EvaluationAssertionRef):
            raise TypeError("assertion_ref must be an EvaluationAssertionRef")
        if not isinstance(self.kind, AssertionKind):
            raise TypeError("kind must be an AssertionKind")
        if not isinstance(self.verdict, EvaluationVerdict):
            raise TypeError("verdict must be an EvaluationVerdict")
        if self.verdict is EvaluationVerdict.SKIPPED:
            raise ValueError("assertion evaluation does not produce SKIPPED")
        if self.reason_code is not None and not isinstance(
            self.reason_code, AssertionReasonCode
        ):
            raise TypeError("reason_code must be an AssertionReasonCode or None")
        if self.verdict is EvaluationVerdict.PASS and self.reason_code is not None:
            raise ValueError("a PASS assertion has no failure reason")
        if self.verdict is not EvaluationVerdict.PASS and self.reason_code is None:
            raise ValueError("a non-PASS assertion requires a closed reason code")


def _validate_common_spec(
    assertion_ref: EvaluationAssertionRef,
    schema_version: EvaluationSchemaVersion,
) -> None:
    if not isinstance(assertion_ref, EvaluationAssertionRef):
        raise TypeError("assertion_ref must be an EvaluationAssertionRef")
    require_supported_schema_version(schema_version)


def _require_observation_ref(value: object, field_name: str) -> None:
    if not isinstance(value, EvaluationObservationRef):
        raise TypeError(f"{field_name} must be an EvaluationObservationRef")
