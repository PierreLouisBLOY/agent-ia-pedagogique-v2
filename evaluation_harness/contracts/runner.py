from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from evaluation_harness.contracts.identity import (
    MAX_DURATION_MILLISECONDS,
    MAX_OBSERVATION_REFS_PER_EXECUTION,
    EvaluationCaseId,
    EvaluationObservationRef,
    EvaluationSchemaVersion,
    require_supported_schema_version,
)
from evaluation_harness.contracts.observation import (
    EvaluationObservationValue,
    validate_observation_value,
)


class EvaluationRunnerReasonCode(Enum):
    CASE_CONFIGURATION_MISSING = "CASE_CONFIGURATION_MISSING"
    FIXTURE_NOT_FOUND = "FIXTURE_NOT_FOUND"
    FIXTURE_SETUP_ERROR = "FIXTURE_SETUP_ERROR"
    FIXTURE_CLEANUP_ERROR = "FIXTURE_CLEANUP_ERROR"
    INPUT_FACTORY_NOT_FOUND = "INPUT_FACTORY_NOT_FOUND"
    INPUT_FACTORY_ERROR = "INPUT_FACTORY_ERROR"
    TARGET_EXECUTOR_NOT_FOUND = "TARGET_EXECUTOR_NOT_FOUND"
    TARGET_EXECUTOR_ERROR = "TARGET_EXECUTOR_ERROR"
    TARGET_EXECUTION_ERROR = "TARGET_EXECUTION_ERROR"
    EVALUATION_TIMEOUT = "EVALUATION_TIMEOUT"
    CLOCK_ERROR = "CLOCK_ERROR"
    ASSERTION_CONFIGURATION_ERROR = "ASSERTION_CONFIGURATION_ERROR"
    ASSERTION_FAILED = "ASSERTION_FAILED"
    ASSERTION_INCONCLUSIVE = "ASSERTION_INCONCLUSIVE"
    ASSERTION_EVALUATION_ERROR = "ASSERTION_EVALUATION_ERROR"
    SCORING_CONFIGURATION_ERROR = "SCORING_CONFIGURATION_ERROR"
    SCORING_EVALUATION_ERROR = "SCORING_EVALUATION_ERROR"
    SUITE_ABORTED = "SUITE_ABORTED"
    CASE_EXPLICITLY_SKIPPED = "CASE_EXPLICITLY_SKIPPED"


class TargetExecutionStatus(Enum):
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True, slots=True)
class EvaluationRepetitionContext:
    schema_version: EvaluationSchemaVersion
    case_id: EvaluationCaseId
    repetition_index: int

    def __post_init__(self) -> None:
        require_supported_schema_version(self.schema_version)
        if not isinstance(self.case_id, EvaluationCaseId):
            raise TypeError("case_id must be an EvaluationCaseId")
        if type(self.repetition_index) is not int or self.repetition_index < 1:
            raise ValueError("repetition_index must be a positive integer")


@dataclass(frozen=True, slots=True)
class EvaluationDeadline:
    started_at_second: int
    expires_at_second: int | None

    def __post_init__(self) -> None:
        if type(self.started_at_second) is not int or self.started_at_second < 0:
            raise ValueError("started_at_second must be a non-negative integer")
        if self.expires_at_second is not None:
            if type(self.expires_at_second) is not int:
                raise TypeError("expires_at_second must be an integer or None")
            if self.expires_at_second <= self.started_at_second:
                raise ValueError("deadline must be after its start")

    def is_expired_at(self, current_second: int) -> bool:
        if type(current_second) is not int or current_second < 0:
            raise ValueError("current_second must be a non-negative integer")
        return (
            self.expires_at_second is not None
            and current_second >= self.expires_at_second
        )


@dataclass(frozen=True, slots=True)
class EvaluationObservationSnapshotEntry:
    observation_ref: EvaluationObservationRef
    value: EvaluationObservationValue

    def __post_init__(self) -> None:
        if not isinstance(self.observation_ref, EvaluationObservationRef):
            raise TypeError("observation_ref must be an EvaluationObservationRef")
        validate_observation_value(self.value)


@dataclass(frozen=True, slots=True)
class EvaluationObservationSnapshot:
    entries: tuple[EvaluationObservationSnapshotEntry, ...] = ()

    def __post_init__(self) -> None:
        if type(self.entries) is not tuple:
            raise TypeError("observation snapshot entries must be a tuple")
        if len(self.entries) > MAX_OBSERVATION_REFS_PER_EXECUTION:
            raise ValueError("observation snapshot exceeds the offline limit")
        if any(
            type(entry) is not EvaluationObservationSnapshotEntry
            for entry in self.entries
        ):
            raise TypeError("snapshot entries contain an unsupported value")
        refs = tuple(entry.observation_ref for entry in self.entries)
        if len(refs) != len(set(refs)):
            raise ValueError("observation snapshot refs must be unique")


@dataclass(frozen=True, slots=True)
class TargetExecutionOutcome:
    status: TargetExecutionStatus
    observations: EvaluationObservationSnapshot = field(
        default_factory=EvaluationObservationSnapshot
    )
    duration_milliseconds: int | None = None
    reason_code: EvaluationRunnerReasonCode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, TargetExecutionStatus):
            raise TypeError("status must be a TargetExecutionStatus")
        if type(self.observations) is not EvaluationObservationSnapshot:
            raise TypeError("observations must be an EvaluationObservationSnapshot")
        if self.duration_milliseconds is not None:
            if type(self.duration_milliseconds) is not int:
                raise TypeError("duration_milliseconds must be an integer or None")
            if not 0 <= self.duration_milliseconds <= MAX_DURATION_MILLISECONDS:
                raise ValueError("duration_milliseconds exceeds the offline limit")
        if self.reason_code is not None and not isinstance(
            self.reason_code, EvaluationRunnerReasonCode
        ):
            raise TypeError("reason_code must be an EvaluationRunnerReasonCode")
        if self.status is TargetExecutionStatus.COMPLETED:
            if self.reason_code is not None:
                raise ValueError("a completed target has no failure reason")
        else:
            expected = (
                EvaluationRunnerReasonCode.EVALUATION_TIMEOUT
                if self.status is TargetExecutionStatus.TIMEOUT
                else EvaluationRunnerReasonCode.TARGET_EXECUTION_ERROR
            )
            if self.reason_code is not expected:
                raise ValueError("target failure status requires its closed reason")
            if self.observations.entries:
                raise ValueError("a failed target exposes no observations")
