from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Final

from calibration_tooling.contracts.errors import CalibrationErrorCode

MAX_PLAN_CALLS: Final = 256
MAX_PROVIDER_OUTPUT_BYTES: Final = 8_192
MAX_COST_USD: Final = Decimal("1000000")

_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CalibrationSchemaVersion(StrEnum):
    V1 = "calibration-tooling.v1"


CALIBRATION_SCHEMA_V1: Final = CalibrationSchemaVersion.V1


class ObservationKind(StrEnum):
    ABSOLUTE = "ABSOLUTE"
    PAIRWISE = "PAIRWISE"


class AnchorTier(StrEnum):
    STRONG = "STRONG"
    MIXED = "MIXED"
    WEAK = "WEAK"


class AbsoluteScoreStatus(StrEnum):
    SCORED = "SCORED"
    INCONCLUSIVE = "INCONCLUSIVE"


class PairwiseDecision(StrEnum):
    A_BETTER = "A_BETTER"
    B_BETTER = "B_BETTER"
    TIE = "TIE"


class RunStatus(StrEnum):
    COMPLETED = "COMPLETED"


class CallExecutionState(StrEnum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class _OpaqueReference:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str or _SAFE_REFERENCE.fullmatch(self.value) is None:
            raise ValueError("reference must be a bounded opaque identifier")

    def __str__(self) -> str:
        return self.value


class RunRef(_OpaqueReference):
    pass


class CallRef(_OpaqueReference):
    pass


class CriterionRef(_OpaqueReference):
    pass


class ProjectionRef(_OpaqueReference):
    pass


class AuthorizationRef(_OpaqueReference):
    pass


@dataclass(frozen=True, slots=True)
class Sha256Digest:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str or _SHA256.fullmatch(self.value) is None:
            raise ValueError("digest must be a lowercase SHA-256 value")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class AnchorDescriptor:
    projection_ref: ProjectionRef
    tier: AnchorTier

    def __post_init__(self) -> None:
        if type(self.projection_ref) is not ProjectionRef:
            raise TypeError("projection_ref must be a ProjectionRef")
        if not isinstance(self.tier, AnchorTier):
            raise TypeError("tier must be an AnchorTier")


@dataclass(frozen=True, slots=True)
class AnchorTriplet:
    strong: AnchorDescriptor
    mixed: AnchorDescriptor
    weak: AnchorDescriptor

    def __post_init__(self) -> None:
        expected = (
            (self.strong, AnchorTier.STRONG),
            (self.mixed, AnchorTier.MIXED),
            (self.weak, AnchorTier.WEAK),
        )
        for descriptor, tier in expected:
            if type(descriptor) is not AnchorDescriptor or descriptor.tier is not tier:
                raise ValueError("anchor triplet must contain strong, mixed and weak")
        refs = tuple(descriptor.projection_ref for descriptor, _ in expected)
        if len(set(refs)) != 3:
            raise ValueError("anchor triplet projection refs must be unique")


@dataclass(frozen=True, slots=True)
class AbsoluteObservationSpec:
    schema_version: CalibrationSchemaVersion
    call_ref: CallRef
    criterion_ref: CriterionRef
    projection_ref: ProjectionRef
    maximum_cost_usd: Decimal

    def __post_init__(self) -> None:
        _require_schema(self.schema_version)
        _require_exact_type(self.call_ref, CallRef, "call_ref")
        _require_exact_type(self.criterion_ref, CriterionRef, "criterion_ref")
        _require_exact_type(self.projection_ref, ProjectionRef, "projection_ref")
        _require_money(self.maximum_cost_usd, positive=True)

    @property
    def kind(self) -> ObservationKind:
        return ObservationKind.ABSOLUTE


@dataclass(frozen=True, slots=True)
class PairwiseObservationSpec:
    schema_version: CalibrationSchemaVersion
    call_ref: CallRef
    criterion_ref: CriterionRef
    candidate_a_ref: ProjectionRef
    candidate_b_ref: ProjectionRef
    maximum_cost_usd: Decimal

    def __post_init__(self) -> None:
        _require_schema(self.schema_version)
        _require_exact_type(self.call_ref, CallRef, "call_ref")
        _require_exact_type(self.criterion_ref, CriterionRef, "criterion_ref")
        _require_exact_type(self.candidate_a_ref, ProjectionRef, "candidate_a_ref")
        _require_exact_type(self.candidate_b_ref, ProjectionRef, "candidate_b_ref")
        if self.candidate_a_ref == self.candidate_b_ref:
            raise ValueError("pairwise projection refs must differ")
        _require_money(self.maximum_cost_usd, positive=True)

    @property
    def kind(self) -> ObservationKind:
        return ObservationKind.PAIRWISE


type CalibrationObservationSpec = AbsoluteObservationSpec | PairwiseObservationSpec


@dataclass(frozen=True, slots=True)
class CalibrationPlan:
    schema_version: CalibrationSchemaVersion
    run_ref: RunRef
    matrix_sha256: Sha256Digest
    observations: tuple[CalibrationObservationSpec, ...]

    def __post_init__(self) -> None:
        _require_schema(self.schema_version)
        _require_exact_type(self.run_ref, RunRef, "run_ref")
        _require_exact_type(self.matrix_sha256, Sha256Digest, "matrix_sha256")
        if type(self.observations) is not tuple:
            raise TypeError("observations must be a tuple")
        if not 1 <= len(self.observations) <= MAX_PLAN_CALLS:
            raise ValueError("observation count is outside the active limit")
        if any(
            type(item) not in (AbsoluteObservationSpec, PairwiseObservationSpec)
            for item in self.observations
        ):
            raise TypeError("observations contain an unsupported specification")
        if any(item.schema_version is not self.schema_version for item in self.observations):
            raise ValueError("observation schema versions must match the plan")
        call_refs = tuple(item.call_ref for item in self.observations)
        if len(call_refs) != len(set(call_refs)):
            raise ValueError("call refs must be unique")


@dataclass(frozen=True, slots=True)
class RawProviderResponse:
    call_ref: CallRef
    output_text: str = field(repr=False)
    measured_cost_usd: Decimal
    complete: bool
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        _require_exact_type(self.call_ref, CallRef, "call_ref")
        if type(self.output_text) is not str:
            raise TypeError("output_text must be a string")
        _require_money(self.measured_cost_usd, positive=False)
        if type(self.complete) is not bool:
            raise TypeError("complete must be a bool")
        for value in (
            self.input_tokens,
            self.cached_input_tokens,
            self.output_tokens,
        ):
            if value is not None and (
                type(value) is not int or not 0 <= value <= 10**12
            ):
                raise ValueError("provider usage must be bounded non-negative integers")
        if self.cached_input_tokens is not None and (
            self.input_tokens is None
            or self.cached_input_tokens > self.input_tokens
        ):
            raise ValueError("cached input usage cannot exceed total input usage")


@dataclass(frozen=True, slots=True)
class AbsoluteObservationResult:
    call_ref: CallRef
    status: AbsoluteScoreStatus
    score_level: int | None

    def __post_init__(self) -> None:
        _require_exact_type(self.call_ref, CallRef, "call_ref")
        if not isinstance(self.status, AbsoluteScoreStatus):
            raise TypeError("status must be an AbsoluteScoreStatus")
        if self.status is AbsoluteScoreStatus.SCORED:
            if type(self.score_level) is not int or not 0 <= self.score_level <= 4:
                raise ValueError("a scored result requires an integer level from 0 to 4")
        elif self.score_level is not None:
            raise ValueError("an inconclusive result cannot carry a score")

    @property
    def kind(self) -> ObservationKind:
        return ObservationKind.ABSOLUTE


@dataclass(frozen=True, slots=True)
class PairwiseObservationResult:
    call_ref: CallRef
    decision: PairwiseDecision

    def __post_init__(self) -> None:
        _require_exact_type(self.call_ref, CallRef, "call_ref")
        if not isinstance(self.decision, PairwiseDecision):
            raise TypeError("decision must be a PairwiseDecision")

    @property
    def kind(self) -> ObservationKind:
        return ObservationKind.PAIRWISE


type CalibrationObservationResult = AbsoluteObservationResult | PairwiseObservationResult


@dataclass(frozen=True, slots=True)
class ScoredCall:
    result: CalibrationObservationResult
    measured_cost_usd: Decimal
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        if type(self.result) not in (AbsoluteObservationResult, PairwiseObservationResult):
            raise TypeError("result must be a calibration observation result")
        _require_money(self.measured_cost_usd, positive=False)
        for value in (
            self.input_tokens,
            self.cached_input_tokens,
            self.output_tokens,
        ):
            if value is not None and (
                type(value) is not int or not 0 <= value <= 10**12
            ):
                raise ValueError("provider usage must be bounded non-negative integers")
        if self.cached_input_tokens is not None and (
            self.input_tokens is None
            or self.cached_input_tokens > self.input_tokens
        ):
            raise ValueError("cached input usage cannot exceed total input usage")


@dataclass(frozen=True, slots=True)
class CallLedgerRecord:
    call_ref: CallRef
    state: CallExecutionState
    result: CalibrationObservationResult | None = None
    measured_cost_usd: Decimal | None = None
    error_code: CalibrationErrorCode | None = None

    def __post_init__(self) -> None:
        _require_exact_type(self.call_ref, CallRef, "call_ref")
        if not isinstance(self.state, CallExecutionState):
            raise TypeError("state must be a CallExecutionState")
        if self.measured_cost_usd is not None:
            _require_money(self.measured_cost_usd, positive=False)
        if self.error_code is not None and not isinstance(
            self.error_code, CalibrationErrorCode
        ):
            raise TypeError("error_code must be a CalibrationErrorCode")
        if self.state is CallExecutionState.STARTED and any(
            value is not None
            for value in (self.result, self.measured_cost_usd, self.error_code)
        ):
            raise ValueError("a started record cannot carry terminal data")
        if self.state is CallExecutionState.COMPLETED and (
            self.result is None
            or self.measured_cost_usd is None
            or self.error_code is not None
        ):
            raise ValueError("a completed record requires result and exact cost")
        if self.state is CallExecutionState.FAILED and (
            self.result is not None or self.error_code is None
        ):
            raise ValueError("a failed record requires only a closed error")


@dataclass(frozen=True, slots=True)
class CalibrationRunOutput:
    schema_version: CalibrationSchemaVersion
    run_ref: RunRef
    status: RunStatus
    results: tuple[CalibrationObservationResult, ...]
    measured_cost_usd: Decimal

    def __post_init__(self) -> None:
        _require_schema(self.schema_version)
        _require_exact_type(self.run_ref, RunRef, "run_ref")
        if self.status is not RunStatus.COMPLETED:
            raise ValueError("only terminal completed outputs are materialized")
        if type(self.results) is not tuple or not self.results:
            raise ValueError("a completed run requires results")
        if any(
            type(item) not in (AbsoluteObservationResult, PairwiseObservationResult)
            for item in self.results
        ):
            raise TypeError("results contain an unsupported observation")
        refs = tuple(item.call_ref for item in self.results)
        if len(refs) != len(set(refs)):
            raise ValueError("result call refs must be unique")
        _require_money(self.measured_cost_usd, positive=False)


def _require_schema(value: CalibrationSchemaVersion) -> None:
    if value is not CALIBRATION_SCHEMA_V1:
        raise ValueError("schema version is not supported")


def _require_exact_type(value: object, expected: type[object], field_name: str) -> None:
    if type(value) is not expected:
        raise TypeError(f"{field_name} has an invalid contract type")


def _require_money(value: Decimal, *, positive: bool) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise TypeError("cost must be a finite Decimal")
    if value < 0 or (positive and value == 0) or value > MAX_COST_USD:
        raise ValueError("cost is outside the active limit")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -6:
        raise ValueError("cost precision exceeds six decimal places")
