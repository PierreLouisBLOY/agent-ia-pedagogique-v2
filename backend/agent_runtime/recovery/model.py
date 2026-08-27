from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Self

from backend.agent_runtime.contracts import (
    ActorRef,
    ContractRef,
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    RecommendedAction,
)
from backend.agent_runtime.contracts.common import require_contract_ref
from backend.agent_runtime.registry import CapabilityExecutionRoute
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant

_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_.-]{0,127}$")
_MAX_FINGERPRINT_INPUT_BYTES = 65_536
_RECORD_PREFIX = "effect:v1:"
_COLLISION_PREFIX = "effect-collision:v1:"


class EffectLedgerLifecycle(StrEnum):
    RESERVED = "RESERVED"
    IN_PROGRESS = "IN_PROGRESS"
    FINALIZED = "FINALIZED"
    ABANDONED = "ABANDONED"


class ReconciliationStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"


@dataclass(frozen=True, slots=True)
class RetryFailureFacts:
    """Crash-safe, closed projection of the latest retry-relevant failure."""

    error_code: str
    category: ErrorCategory
    retryable: bool
    recommended_action: RecommendedAction
    source: ErrorSource

    def __post_init__(self) -> None:
        if type(self.error_code) is not str or not _SAFE_ERROR_CODE.fullmatch(
            self.error_code
        ):
            raise ValueError("error_code must be a safe closed code")
        if not isinstance(self.category, ErrorCategory):
            raise TypeError("category must be an ErrorCategory")
        if type(self.retryable) is not bool:
            raise TypeError("retryable must be a bool")
        if not isinstance(self.recommended_action, RecommendedAction):
            raise TypeError("recommended_action must be a RecommendedAction")
        if not isinstance(self.source, ErrorSource):
            raise TypeError("source must be an ErrorSource")

    @classmethod
    def from_error(cls, error: ErrorEnvelope) -> Self:
        if not isinstance(error, ErrorEnvelope):
            raise TypeError("error must be an ErrorEnvelope")
        return cls(
            error_code=error.error_code,
            category=error.category,
            retryable=error.retryable,
            recommended_action=error.recommended_action,
            source=error.source,
        )

    def to_error(
        self,
        *,
        step_id: str,
        attempt: int,
        effect_state: EffectState,
    ) -> ErrorEnvelope:
        _require_safe_identifier(step_id, "step_id")
        if type(attempt) is not int or attempt < 1:
            raise ValueError("attempt must be >= 1")
        if not isinstance(effect_state, EffectState):
            raise TypeError("effect_state must be an EffectState")
        return ErrorEnvelope(
            error_code=self.error_code,
            category=self.category,
            source=self.source,
            retryable=self.retryable,
            severity=ErrorSeverity.ERROR,
            message="persisted recovery failure",
            step_id=step_id,
            attempt=attempt,
            effect_state=effect_state,
            recommended_action=self.recommended_action,
        )


class EffectReservationDisposition(StrEnum):
    RESERVED_NEW = "RESERVED_NEW"
    DUPLICATE_ACTIVE = "DUPLICATE_ACTIVE"
    DUPLICATE_FINALIZED = "DUPLICATE_FINALIZED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    COLLISION = "COLLISION"
    RESERVATION_EXPIRED = "RESERVATION_EXPIRED"
    ABANDONED = "ABANDONED"


class EffectLedgerErrorCode(StrEnum):
    VERSION_CONFLICT = "VERSION_CONFLICT"
    IDENTITY_COLLISION = "IDENTITY_COLLISION"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    UNKNOWN_RECORD = "UNKNOWN_RECORD"
    RESERVATION_NOT_ACTIVE = "RESERVATION_NOT_ACTIVE"
    RESERVATION_EXPIRED = "RESERVATION_EXPIRED"
    INVALID_RECORD = "INVALID_RECORD"


_ERROR_MESSAGES = MappingProxyType({
    EffectLedgerErrorCode.VERSION_CONFLICT: "effect ledger version conflict",
    EffectLedgerErrorCode.IDENTITY_COLLISION: "idempotency identity collision",
    EffectLedgerErrorCode.INVALID_TRANSITION: "invalid effect ledger transition",
    EffectLedgerErrorCode.UNKNOWN_RECORD: "unknown effect ledger record",
    EffectLedgerErrorCode.RESERVATION_NOT_ACTIVE: "effect reservation is not active",
    EffectLedgerErrorCode.RESERVATION_EXPIRED: "effect reservation has expired",
    EffectLedgerErrorCode.INVALID_RECORD: "invalid effect ledger record",
})


class EffectLedgerError(ValueError):
    code: EffectLedgerErrorCode

    def __init__(self, code: EffectLedgerErrorCode) -> None:
        if not isinstance(code, EffectLedgerErrorCode):
            raise TypeError("code must be an EffectLedgerErrorCode")
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])


@dataclass(frozen=True, slots=True)
class IntentFingerprint:
    value: str

    def __post_init__(self) -> None:
        _require_digest(self.value, "intent fingerprint")

    @classmethod
    def from_value(cls, value: str | bytes) -> Self:
        return cls(_fingerprint("agent-runtime:intent:v1", value))


@dataclass(frozen=True, slots=True)
class IdempotencyKeyFingerprint:
    value: str

    def __post_init__(self) -> None:
        _require_digest(self.value, "idempotency key fingerprint")

    @classmethod
    def from_key(cls, value: str | bytes) -> Self:
        return cls(_fingerprint("agent-runtime:idempotency-key:v1", value))


@dataclass(frozen=True, slots=True)
class IdempotencyIdentity:
    principal: ActorRef
    run_id: str
    step_id: str
    capability_id: CapabilityId
    execution_route: CapabilityExecutionRoute
    target_id: str
    operation: str
    intent_fingerprint: IntentFingerprint
    caller_key_fingerprint: IdempotencyKeyFingerprint

    def __post_init__(self) -> None:
        if not isinstance(self.principal, ActorRef):
            raise TypeError("principal must be an ActorRef")
        _require_safe_identifier(self.run_id, "run_id")
        _require_safe_identifier(self.step_id, "step_id")
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if not isinstance(self.execution_route, CapabilityExecutionRoute):
            raise TypeError("execution_route must be a CapabilityExecutionRoute")
        _require_safe_identifier(self.target_id, "target_id")
        _require_safe_identifier(self.operation, "operation")
        if not isinstance(self.intent_fingerprint, IntentFingerprint):
            raise TypeError("intent_fingerprint must be an IntentFingerprint")
        if not isinstance(self.caller_key_fingerprint, IdempotencyKeyFingerprint):
            raise TypeError(
                "caller_key_fingerprint must be an IdempotencyKeyFingerprint"
            )

    @property
    def record_id(self) -> str:
        digest = _digest_parts(
            "agent-runtime:effect-record:v1",
            self._identity_parts(),
        )
        return f"{_RECORD_PREFIX}{digest}"

    @property
    def collision_key(self) -> str:
        digest = _digest_parts(
            "agent-runtime:effect-collision:v1",
            (
                self.principal.kind.value,
                self.principal.actor_id,
                self.run_id,
                self.step_id,
                self.caller_key_fingerprint.value,
            ),
        )
        return f"{_COLLISION_PREFIX}{digest}"

    def _identity_parts(self) -> tuple[str, ...]:
        return (
            self.principal.kind.value,
            self.principal.actor_id,
            self.run_id,
            self.step_id,
            self.capability_id.value,
            self.execution_route.value,
            self.target_id,
            self.operation,
            self.intent_fingerprint.value,
            self.caller_key_fingerprint.value,
        )


@dataclass(frozen=True, slots=True)
class EffectAttemptRecord:
    attempt: int
    started_at: Instant
    effect_state: EffectState
    ended_at: Instant | None = None
    result_refs: tuple[ContractRef, ...] = ()
    error_code: str | None = None
    retry_failure_facts: RetryFailureFacts | None = None

    def __post_init__(self) -> None:
        if type(self.attempt) is not int:
            raise TypeError("attempt must be an integer")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        _require_instant(self.started_at, "started_at")
        if self.ended_at is not None:
            _require_instant(self.ended_at, "ended_at")
            if self.ended_at.value < self.started_at.value:
                raise ValueError("ended_at must be >= started_at")
        if not isinstance(self.effect_state, EffectState):
            raise TypeError("effect_state must be an EffectState")
        if not isinstance(self.result_refs, tuple):
            raise TypeError("result_refs must be a tuple")
        for result_ref in self.result_refs:
            _require_ledger_ref(result_ref)
        if self.error_code is not None and not _SAFE_ERROR_CODE.fullmatch(
            self.error_code
        ):
            raise ValueError("error_code must be a safe closed code")
        if self.retry_failure_facts is not None:
            if not isinstance(self.retry_failure_facts, RetryFailureFacts):
                raise TypeError(
                    "retry_failure_facts must be RetryFailureFacts or None"
                )
            if self.error_code != self.retry_failure_facts.error_code:
                raise ValueError("retry failure facts must match error_code")
        if self.ended_at is None:
            if self.effect_state is not EffectState.UNKNOWN:
                raise ValueError("an active attempt must have UNKNOWN effect state")
            if (
                self.result_refs
                or self.error_code is not None
                or self.retry_failure_facts is not None
            ):
                raise ValueError("an active attempt cannot contain final outcome data")


@dataclass(frozen=True, slots=True)
class EffectLedgerRecord:
    record_id: str
    identity: IdempotencyIdentity
    version: int
    lifecycle: EffectLedgerLifecycle
    effect_state: EffectState
    reconciliation_status: ReconciliationStatus
    created_at: Instant
    updated_at: Instant
    reservation_expires_at: Instant | None = None
    attempts: tuple[EffectAttemptRecord, ...] = ()

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        if not isinstance(self.identity, IdempotencyIdentity):
            raise TypeError("identity must be an IdempotencyIdentity")
        if self.record_id != self.identity.record_id:
            raise ValueError("record_id must match identity")
        if type(self.version) is not int:
            raise TypeError("version must be an integer")
        if self.version < 1:
            raise ValueError("version must be >= 1")
        if not isinstance(self.lifecycle, EffectLedgerLifecycle):
            raise TypeError("lifecycle must be an EffectLedgerLifecycle")
        if not isinstance(self.effect_state, EffectState):
            raise TypeError("effect_state must be an EffectState")
        if not isinstance(self.reconciliation_status, ReconciliationStatus):
            raise TypeError("reconciliation_status must be a ReconciliationStatus")
        _require_instant(self.created_at, "created_at")
        _require_instant(self.updated_at, "updated_at")
        if self.updated_at.value < self.created_at.value:
            raise ValueError("updated_at must be >= created_at")
        if self.reservation_expires_at is not None:
            _require_instant(self.reservation_expires_at, "reservation_expires_at")
            if self.reservation_expires_at.value <= self.created_at.value:
                raise ValueError("reservation_expires_at must be > created_at")
        if not isinstance(self.attempts, tuple):
            raise TypeError("attempts must be a tuple")
        if any(not isinstance(item, EffectAttemptRecord) for item in self.attempts):
            raise TypeError("attempts must contain EffectAttemptRecord values")
        if tuple(item.attempt for item in self.attempts) != tuple(
            range(1, len(self.attempts) + 1)
        ):
            raise ValueError("attempt lineage must be contiguous and start at one")
        if any(item.ended_at is None for item in self.attempts[:-1]):
            raise ValueError("only the latest attempt may be active")
        self._validate_lifecycle_coherence()

    @property
    def attempt(self) -> int:
        return self.attempts[-1].attempt if self.attempts else 0

    @property
    def result_refs(self) -> tuple[ContractRef, ...]:
        return self.attempts[-1].result_refs if self.attempts else ()

    @property
    def error_code(self) -> str | None:
        return self.attempts[-1].error_code if self.attempts else None

    @property
    def retry_failure_facts(self) -> RetryFailureFacts | None:
        return self.attempts[-1].retry_failure_facts if self.attempts else None

    def _validate_lifecycle_coherence(self) -> None:
        if self.lifecycle in {EffectLedgerLifecycle.RESERVED, EffectLedgerLifecycle.ABANDONED}:
            if self.lifecycle is EffectLedgerLifecycle.ABANDONED and self.attempts:
                raise ValueError("abandoned records cannot have attempts")
            if self.attempts and any(item.ended_at is None for item in self.attempts):
                raise ValueError(
                    "reserved records cannot have attempts unless all are finalized"
                )
            if self.effect_state is not EffectState.NONE:
                raise ValueError("reserved and abandoned records require NONE effect")
            if self.reconciliation_status is not ReconciliationStatus.NOT_REQUIRED:
                raise ValueError(
                    "reserved and abandoned records cannot require reconciliation"
                )
            return
        if not self.attempts:
            raise ValueError("started records require an attempt")
        latest = self.attempts[-1]
        if self.lifecycle is EffectLedgerLifecycle.IN_PROGRESS:
            if latest.ended_at is not None:
                raise ValueError("in-progress records require an active attempt")
            if self.effect_state is not EffectState.UNKNOWN:
                raise ValueError("in-progress records require UNKNOWN effect")
            if self.reconciliation_status is not ReconciliationStatus.PENDING:
                raise ValueError("in-progress records require pending reconciliation")
            return
        if latest.ended_at is None:
            raise ValueError("finalized records require an ended attempt")
        if self.effect_state is not latest.effect_state:
            raise ValueError("record effect_state must match the latest attempt")
        if self.effect_state is EffectState.UNKNOWN and self.reconciliation_status not in {
            ReconciliationStatus.PENDING,
            ReconciliationStatus.MANUAL_REQUIRED,
        }:
            raise ValueError(
                "UNKNOWN effect requires pending or manual reconciliation"
            )
        if self.effect_state is EffectState.PARTIAL and self.reconciliation_status not in {
            ReconciliationStatus.PENDING,
            ReconciliationStatus.RESOLVED,
            ReconciliationStatus.MANUAL_REQUIRED,
        }:
            raise ValueError("PARTIAL effect requires explicit reconciliation state")
        if self.effect_state in {EffectState.NONE, EffectState.COMMITTED} and (
            self.reconciliation_status
            not in {ReconciliationStatus.NOT_REQUIRED, ReconciliationStatus.RESOLVED}
        ):
            raise ValueError("known effects cannot have unresolved reconciliation")


@dataclass(frozen=True, slots=True)
class EffectReservationResult:
    disposition: EffectReservationDisposition
    record: EffectLedgerRecord | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, EffectReservationDisposition):
            raise TypeError("disposition must be an EffectReservationDisposition")
        if self.disposition is EffectReservationDisposition.COLLISION:
            if self.record is not None:
                raise ValueError("collision results must not expose an existing record")
            return
        if not isinstance(self.record, EffectLedgerRecord):
            raise TypeError("non-collision results require an EffectLedgerRecord")


def _fingerprint(domain: str, value: str | bytes) -> str:
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bytes):
        raw = value
    else:
        raise TypeError("fingerprint input must be str or bytes")
    if not raw:
        raise ValueError("fingerprint input must not be empty")
    if len(raw) > _MAX_FINGERPRINT_INPUT_BYTES:
        raise ValueError("fingerprint input exceeds the bounded size")
    return _digest_bytes(domain, raw)


def _digest_parts(domain: str, parts: tuple[str, ...]) -> str:
    encoded = bytearray()
    for part in parts:
        chunk = part.encode("utf-8")
        encoded.extend(len(chunk).to_bytes(8, "big"))
        encoded.extend(chunk)
    return _digest_bytes(domain, bytes(encoded))


def _digest_bytes(domain: str, raw: bytes) -> str:
    digest = sha256()
    digest.update(domain.encode("ascii"))
    digest.update(b"\x00")
    digest.update(raw)
    return digest.hexdigest()


def _require_digest(value: str, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    if not _HEX_DIGEST.fullmatch(value):
        raise ValueError(f"{field_name} must be lowercase SHA-256 hex")


def _require_safe_identifier(value: str, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field_name} must be a safe non-empty identifier")


def _require_instant(value: Instant, field_name: str) -> None:
    if not isinstance(value, Instant):
        raise TypeError(f"{field_name} must be an Instant")


def _require_ledger_ref(value: ContractRef) -> None:
    require_contract_ref(value, "result_ref")
    if isinstance(value, str) and not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError("string result refs must be opaque safe identifiers")
