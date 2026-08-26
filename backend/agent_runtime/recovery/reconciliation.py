from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType

from backend.agent_runtime.contracts import ActorRef, ContractRef, EffectState
from backend.agent_runtime.contracts.common import require_contract_ref
from backend.agent_runtime.recovery.model import (
    EffectAttemptRecord,
    EffectLedgerLifecycle,
    EffectLedgerRecord,
    IntentFingerprint,
    ReconciliationStatus,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.time import Instant

_EFFECT_RECORD_ID = re.compile(r"^effect:v1:[0-9a-f]{64}$")
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_SAFE_OBSERVATION_CODE = re.compile(r"^[A-Z][A-Z0-9_.-]{0,127}$")


class ReconciliationObservationDisposition(StrEnum):
    COMMITTED = "COMMITTED"
    NOT_COMMITTED = "NOT_COMMITTED"
    PARTIAL = "PARTIAL"
    STILL_UNKNOWN = "STILL_UNKNOWN"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"


class ReconciliationEligibility(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    RECORD_STILL_ACTIVE = "RECORD_STILL_ACTIVE"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"


class EffectReconciliationDisposition(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    RECONCILED = "RECONCILED"
    STILL_UNKNOWN = "STILL_UNKNOWN"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class EffectReconciliationErrorCode(StrEnum):
    UNKNOWN_RECORD = "UNKNOWN_RECORD"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    RECORD_NOT_ELIGIBLE = "RECORD_NOT_ELIGIBLE"
    RECORD_STILL_ACTIVE = "RECORD_STILL_ACTIVE"
    UNSUPPORTED_ROUTE = "UNSUPPORTED_ROUTE"
    PROBE_FAILED = "PROBE_FAILED"
    OBSERVATION_RECORD_MISMATCH = "OBSERVATION_RECORD_MISMATCH"
    OBSERVATION_VERSION_MISMATCH = "OBSERVATION_VERSION_MISMATCH"
    OBSERVATION_ATTEMPT_MISMATCH = "OBSERVATION_ATTEMPT_MISMATCH"
    INVALID_OBSERVATION = "INVALID_OBSERVATION"
    LEDGER_VERSION_CONFLICT = "LEDGER_VERSION_CONFLICT"
    INVALID_RECONCILIATION_TRANSITION = "INVALID_RECONCILIATION_TRANSITION"


_ERROR_MESSAGES = MappingProxyType(
    {
        EffectReconciliationErrorCode.UNKNOWN_RECORD: "unknown effect ledger record",
        EffectReconciliationErrorCode.VERSION_MISMATCH: "reconciliation version mismatch",
        EffectReconciliationErrorCode.RECORD_NOT_ELIGIBLE: (
            "effect ledger record is not eligible for reconciliation"
        ),
        EffectReconciliationErrorCode.RECORD_STILL_ACTIVE: (
            "effect ledger record is still active"
        ),
        EffectReconciliationErrorCode.UNSUPPORTED_ROUTE: (
            "effect reconciliation route is unsupported"
        ),
        EffectReconciliationErrorCode.PROBE_FAILED: "effect reconciliation probe failed",
        EffectReconciliationErrorCode.OBSERVATION_RECORD_MISMATCH: (
            "reconciliation observation record mismatch"
        ),
        EffectReconciliationErrorCode.OBSERVATION_VERSION_MISMATCH: (
            "reconciliation observation version mismatch"
        ),
        EffectReconciliationErrorCode.OBSERVATION_ATTEMPT_MISMATCH: (
            "reconciliation observation attempt mismatch"
        ),
        EffectReconciliationErrorCode.INVALID_OBSERVATION: (
            "invalid reconciliation observation"
        ),
        EffectReconciliationErrorCode.LEDGER_VERSION_CONFLICT: (
            "effect ledger reconciliation version conflict"
        ),
        EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION: (
            "invalid effect reconciliation transition"
        ),
    }
)


class EffectReconciliationError(ValueError):
    code: EffectReconciliationErrorCode

    def __init__(self, code: EffectReconciliationErrorCode) -> None:
        if not isinstance(code, EffectReconciliationErrorCode):
            raise TypeError("code must be an EffectReconciliationErrorCode")
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])


@dataclass(frozen=True, slots=True)
class EffectReconciliationRequest:
    record_id: str
    expected_version: int

    def __post_init__(self) -> None:
        _require_record_id(self.record_id)
        _require_positive_int(self.expected_version, "expected_version")


@dataclass(frozen=True, slots=True)
class ToolEffectProbeRequest:
    record_id: str
    record_version: int
    attempt: int
    principal: ActorRef
    run_id: str
    step_id: str
    capability_id: CapabilityId
    tool_id: str
    operation: str
    intent_fingerprint: IntentFingerprint
    result_refs: tuple[ContractRef, ...] = ()

    def __post_init__(self) -> None:
        _validate_probe_request(
            record_id=self.record_id,
            record_version=self.record_version,
            attempt=self.attempt,
            principal=self.principal,
            run_id=self.run_id,
            step_id=self.step_id,
            capability_id=self.capability_id,
            target_id=self.tool_id,
            operation=self.operation,
            intent_fingerprint=self.intent_fingerprint,
            result_refs=self.result_refs,
        )


@dataclass(frozen=True, slots=True)
class ApplicationEffectProbeRequest:
    record_id: str
    record_version: int
    attempt: int
    principal: ActorRef
    run_id: str
    step_id: str
    capability_id: CapabilityId
    use_case_id: str
    operation: str
    intent_fingerprint: IntentFingerprint
    result_refs: tuple[ContractRef, ...] = ()

    def __post_init__(self) -> None:
        _validate_probe_request(
            record_id=self.record_id,
            record_version=self.record_version,
            attempt=self.attempt,
            principal=self.principal,
            run_id=self.run_id,
            step_id=self.step_id,
            capability_id=self.capability_id,
            target_id=self.use_case_id,
            operation=self.operation,
            intent_fingerprint=self.intent_fingerprint,
            result_refs=self.result_refs,
        )


@dataclass(frozen=True, slots=True)
class ReconciliationObservation:
    record_id: str
    record_version: int
    attempt: int
    disposition: ReconciliationObservationDisposition
    observed_result_refs: tuple[ContractRef, ...]
    observed_at: Instant
    observation_code: str | None = None

    def __post_init__(self) -> None:
        _require_record_id(self.record_id)
        _require_positive_int(self.record_version, "record_version")
        _require_positive_int(self.attempt, "attempt")
        if not isinstance(self.disposition, ReconciliationObservationDisposition):
            raise TypeError("disposition must be a ReconciliationObservationDisposition")
        _require_result_refs(self.observed_result_refs, "observed_result_refs")
        if not isinstance(self.observed_at, Instant):
            raise TypeError("observed_at must be an Instant")
        if self.observation_code is not None:
            if type(self.observation_code) is not str:
                raise TypeError("observation_code must be a string or None")
            if not _SAFE_OBSERVATION_CODE.fullmatch(self.observation_code):
                raise ValueError("observation_code must be a safe closed code")


@dataclass(frozen=True, slots=True)
class EffectReconciliationResult:
    disposition: EffectReconciliationDisposition
    record: EffectLedgerRecord
    previous_version: int
    current_version: int

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, EffectReconciliationDisposition):
            raise TypeError("disposition must be an EffectReconciliationDisposition")
        if not isinstance(self.record, EffectLedgerRecord):
            raise TypeError("record must be an EffectLedgerRecord")
        _require_positive_int(self.previous_version, "previous_version")
        _require_positive_int(self.current_version, "current_version")
        if self.current_version < self.previous_version:
            raise ValueError("current_version must be >= previous_version")
        if self.record.version != self.current_version:
            raise ValueError("record.version must match current_version")


@dataclass(frozen=True, slots=True)
class EffectReconciliationPolicy:
    """Pure observation mapping and ledger transition policy without probe I/O."""

    def classify_eligibility(
        self,
        *,
        record: EffectLedgerRecord,
        now: Instant,
    ) -> ReconciliationEligibility:
        _require_record(record)
        _require_instant(now, "now")
        if record.lifecycle in {
            EffectLedgerLifecycle.RESERVED,
            EffectLedgerLifecycle.ABANDONED,
        }:
            return ReconciliationEligibility.NOT_ELIGIBLE
        if record.lifecycle is EffectLedgerLifecycle.IN_PROGRESS:
            expires_at = record.reservation_expires_at
            if expires_at is None or now.value < expires_at.value:
                return ReconciliationEligibility.RECORD_STILL_ACTIVE
            return ReconciliationEligibility.ELIGIBLE
        if record.effect_state in {EffectState.NONE, EffectState.COMMITTED}:
            return ReconciliationEligibility.NOT_REQUIRED
        if record.reconciliation_status is ReconciliationStatus.MANUAL_REQUIRED:
            return ReconciliationEligibility.MANUAL_REQUIRED
        if (
            record.effect_state is EffectState.PARTIAL
            and record.reconciliation_status is ReconciliationStatus.RESOLVED
        ):
            return ReconciliationEligibility.NOT_REQUIRED
        if record.reconciliation_status is ReconciliationStatus.PENDING:
            return ReconciliationEligibility.ELIGIBLE
        raise EffectReconciliationError(
            EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
        )

    def prepare_replacement(
        self,
        *,
        record: EffectLedgerRecord,
        observation: ReconciliationObservation,
    ) -> EffectLedgerRecord:
        _require_record(record)
        if not isinstance(observation, ReconciliationObservation):
            raise TypeError("observation must be a ReconciliationObservation")
        self.validate_observation(record=record, observation=observation)
        if record.lifecycle not in {
            EffectLedgerLifecycle.IN_PROGRESS,
            EffectLedgerLifecycle.FINALIZED,
        }:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.RECORD_NOT_ELIGIBLE
            )
        if observation.observed_at.value < record.updated_at.value:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.INVALID_OBSERVATION
            )
        effect_state, reconciliation_status = _map_observation(
            record,
            observation.disposition,
        )
        latest = record.attempts[-1]
        merged_refs = _merge_result_refs(
            latest.result_refs,
            observation.observed_result_refs,
        )
        ended_at = (
            observation.observed_at
            if record.lifecycle is EffectLedgerLifecycle.IN_PROGRESS
            else latest.ended_at
        )
        updated_attempt = replace(
            latest,
            ended_at=ended_at,
            effect_state=effect_state,
            result_refs=merged_refs,
        )
        replacement = replace(
            record,
            version=record.version + 1,
            lifecycle=EffectLedgerLifecycle.FINALIZED,
            effect_state=effect_state,
            reconciliation_status=reconciliation_status,
            updated_at=observation.observed_at,
            attempts=(*record.attempts[:-1], updated_attempt),
        )
        self.validate_compare_and_set(
            current=record,
            expected_version=record.version,
            replacement=replacement,
        )
        return replacement

    def validate_observation(
        self,
        *,
        record: EffectLedgerRecord,
        observation: ReconciliationObservation,
    ) -> None:
        _require_record(record)
        if not isinstance(observation, ReconciliationObservation):
            raise TypeError("observation must be a ReconciliationObservation")
        if observation.record_id != record.record_id:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.OBSERVATION_RECORD_MISMATCH
            )
        if observation.record_version != record.version:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.OBSERVATION_VERSION_MISMATCH
            )
        if observation.attempt != record.attempt:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.OBSERVATION_ATTEMPT_MISMATCH
            )

    def validate_compare_and_set(
        self,
        *,
        current: EffectLedgerRecord,
        expected_version: int,
        replacement: EffectLedgerRecord,
    ) -> None:
        _require_record(current)
        _require_record(replacement)
        if type(expected_version) is not int:
            raise TypeError("expected_version must be an integer")
        if expected_version != current.version or replacement.version != current.version + 1:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.LEDGER_VERSION_CONFLICT
            )
        if (
            replacement.record_id != current.record_id
            or replacement.identity != current.identity
            or replacement.created_at != current.created_at
            or replacement.reservation_expires_at != current.reservation_expires_at
        ):
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
            )
        if current.lifecycle not in {
            EffectLedgerLifecycle.IN_PROGRESS,
            EffectLedgerLifecycle.FINALIZED,
        } or replacement.lifecycle is not EffectLedgerLifecycle.FINALIZED:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
            )
        if replacement.updated_at.value < current.updated_at.value:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
            )
        if len(replacement.attempts) != len(current.attempts):
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
            )
        if replacement.attempts[:-1] != current.attempts[:-1]:
            raise EffectReconciliationError(
                EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
            )
        _validate_attempt_progression(current.attempts[-1], replacement.attempts[-1])


def tool_probe_request_for(record: EffectLedgerRecord) -> ToolEffectProbeRequest:
    _require_record(record)
    identity = record.identity
    return ToolEffectProbeRequest(
        record_id=record.record_id,
        record_version=record.version,
        attempt=record.attempt,
        principal=identity.principal,
        run_id=identity.run_id,
        step_id=identity.step_id,
        capability_id=identity.capability_id,
        tool_id=identity.target_id,
        operation=identity.operation,
        intent_fingerprint=identity.intent_fingerprint,
        result_refs=record.result_refs,
    )


def application_probe_request_for(
    record: EffectLedgerRecord,
) -> ApplicationEffectProbeRequest:
    _require_record(record)
    identity = record.identity
    return ApplicationEffectProbeRequest(
        record_id=record.record_id,
        record_version=record.version,
        attempt=record.attempt,
        principal=identity.principal,
        run_id=identity.run_id,
        step_id=identity.step_id,
        capability_id=identity.capability_id,
        use_case_id=identity.target_id,
        operation=identity.operation,
        intent_fingerprint=identity.intent_fingerprint,
        result_refs=record.result_refs,
    )


def _map_observation(
    record: EffectLedgerRecord,
    disposition: ReconciliationObservationDisposition,
) -> tuple[EffectState, ReconciliationStatus]:
    if disposition is ReconciliationObservationDisposition.COMMITTED:
        return EffectState.COMMITTED, ReconciliationStatus.RESOLVED
    if disposition is ReconciliationObservationDisposition.NOT_COMMITTED:
        return EffectState.NONE, ReconciliationStatus.RESOLVED
    if disposition is ReconciliationObservationDisposition.PARTIAL:
        return EffectState.PARTIAL, ReconciliationStatus.RESOLVED
    if disposition is ReconciliationObservationDisposition.STILL_UNKNOWN:
        return EffectState.UNKNOWN, ReconciliationStatus.PENDING
    preserved = (
        EffectState.PARTIAL
        if record.effect_state is EffectState.PARTIAL
        else EffectState.UNKNOWN
    )
    return preserved, ReconciliationStatus.MANUAL_REQUIRED


def _validate_attempt_progression(
    current: EffectAttemptRecord,
    replacement: EffectAttemptRecord,
) -> None:
    if (
        replacement.attempt != current.attempt
        or replacement.started_at != current.started_at
        or replacement.error_code != current.error_code
    ):
        raise EffectReconciliationError(
            EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
        )
    if current.ended_at is not None and replacement.ended_at != current.ended_at:
        raise EffectReconciliationError(
            EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
        )
    if replacement.ended_at is None:
        raise EffectReconciliationError(
            EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
        )
    if _merge_result_refs(current.result_refs, replacement.result_refs) != (
        replacement.result_refs
    ):
        raise EffectReconciliationError(
            EffectReconciliationErrorCode.INVALID_RECONCILIATION_TRANSITION
        )


def _merge_result_refs(
    existing: tuple[ContractRef, ...],
    observed: tuple[ContractRef, ...],
) -> tuple[ContractRef, ...]:
    merged = list(existing)
    for item in observed:
        if item not in merged:
            merged.append(item)
    return tuple(merged)


def _validate_probe_request(
    *,
    record_id: str,
    record_version: int,
    attempt: int,
    principal: ActorRef,
    run_id: str,
    step_id: str,
    capability_id: CapabilityId,
    target_id: str,
    operation: str,
    intent_fingerprint: IntentFingerprint,
    result_refs: tuple[ContractRef, ...],
) -> None:
    _require_record_id(record_id)
    _require_positive_int(record_version, "record_version")
    _require_positive_int(attempt, "attempt")
    if not isinstance(principal, ActorRef):
        raise TypeError("principal must be an ActorRef")
    _require_safe_identifier(run_id, "run_id")
    _require_safe_identifier(step_id, "step_id")
    if not isinstance(capability_id, CapabilityId):
        raise TypeError("capability_id must be a CapabilityId")
    _require_safe_identifier(target_id, "target_id")
    _require_safe_identifier(operation, "operation")
    if not isinstance(intent_fingerprint, IntentFingerprint):
        raise TypeError("intent_fingerprint must be an IntentFingerprint")
    _require_result_refs(result_refs, "result_refs")


def _require_result_refs(value: tuple[ContractRef, ...], field_name: str) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    for item in value:
        require_contract_ref(item, field_name)
        if isinstance(item, str) and not _SAFE_IDENTIFIER.fullmatch(item):
            raise ValueError(f"{field_name} must contain opaque safe references")


def _require_record_id(value: str) -> None:
    if type(value) is not str:
        raise TypeError("record_id must be a string")
    if not _EFFECT_RECORD_ID.fullmatch(value):
        raise ValueError("record_id must be an opaque effect ledger identifier")


def _require_safe_identifier(value: str, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field_name} must be a safe non-empty identifier")


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")


def _require_record(value: EffectLedgerRecord) -> None:
    if not isinstance(value, EffectLedgerRecord):
        raise TypeError("record must be an EffectLedgerRecord")


def _require_instant(value: Instant, field_name: str) -> None:
    if not isinstance(value, Instant):
        raise TypeError(f"{field_name} must be an Instant")
