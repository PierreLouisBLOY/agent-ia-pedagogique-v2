from __future__ import annotations

from dataclasses import dataclass, replace

from backend.agent_runtime.contracts import ContractRef, EffectState
from backend.agent_runtime.recovery.model import (
    EffectAttemptRecord,
    EffectLedgerError,
    EffectLedgerErrorCode,
    EffectLedgerLifecycle,
    EffectLedgerRecord,
    EffectReservationDisposition,
    EffectReservationResult,
    IdempotencyIdentity,
    ReconciliationStatus,
    RetryFailureFacts,
)
from backend.shared_kernel.time import Instant

_ALLOWED_TRANSITIONS = frozenset(
    {
        (EffectLedgerLifecycle.RESERVED, EffectLedgerLifecycle.IN_PROGRESS),
        (EffectLedgerLifecycle.RESERVED, EffectLedgerLifecycle.ABANDONED),
        (EffectLedgerLifecycle.ABANDONED, EffectLedgerLifecycle.RESERVED),
        (EffectLedgerLifecycle.IN_PROGRESS, EffectLedgerLifecycle.FINALIZED),
        (EffectLedgerLifecycle.FINALIZED, EffectLedgerLifecycle.RESERVED),
    }
)


@dataclass(frozen=True, slots=True)
class IdempotencyPolicy:
    """Pure lifecycle and deduplication policy; it grants no execution authority."""

    def new_reservation(
        self,
        *,
        identity: IdempotencyIdentity,
        now: Instant,
        reservation_expires_at: Instant | None = None,
    ) -> EffectLedgerRecord:
        _require_identity(identity)
        _require_instant(now, "now")
        return EffectLedgerRecord(
            record_id=identity.record_id,
            identity=identity,
            version=1,
            lifecycle=EffectLedgerLifecycle.RESERVED,
            effect_state=EffectState.NONE,
            reconciliation_status=ReconciliationStatus.NOT_REQUIRED,
            created_at=now,
            updated_at=now,
            reservation_expires_at=reservation_expires_at,
        )

    def classify_reservation(
        self,
        *,
        identity: IdempotencyIdentity,
        existing: EffectLedgerRecord,
        now: Instant,
    ) -> EffectReservationResult:
        _require_identity(identity)
        _require_record(existing)
        _require_instant(now, "now")
        if existing.identity != identity:
            if existing.identity.collision_key != identity.collision_key:
                raise EffectLedgerError(EffectLedgerErrorCode.INVALID_RECORD)
            return EffectReservationResult(EffectReservationDisposition.COLLISION)
        if existing.lifecycle is EffectLedgerLifecycle.RESERVED:
            disposition = (
                EffectReservationDisposition.RESERVATION_EXPIRED
                if _is_expired(existing, now)
                else EffectReservationDisposition.DUPLICATE_ACTIVE
            )
        elif existing.lifecycle is EffectLedgerLifecycle.IN_PROGRESS:
            disposition = (
                EffectReservationDisposition.RECONCILIATION_REQUIRED
                if _is_expired(existing, now)
                else EffectReservationDisposition.DUPLICATE_ACTIVE
            )
        elif existing.lifecycle is EffectLedgerLifecycle.ABANDONED:
            disposition = EffectReservationDisposition.ABANDONED
        elif existing.effect_state in {EffectState.UNKNOWN, EffectState.PARTIAL}:
            disposition = EffectReservationDisposition.RECONCILIATION_REQUIRED
        else:
            disposition = EffectReservationDisposition.DUPLICATE_FINALIZED
        return EffectReservationResult(disposition=disposition, record=existing)

    def new_reservation_result(
        self, record: EffectLedgerRecord
    ) -> EffectReservationResult:
        _require_record(record)
        if record.lifecycle is not EffectLedgerLifecycle.RESERVED or record.version != 1:
            raise EffectLedgerError(EffectLedgerErrorCode.INVALID_RECORD)
        return EffectReservationResult(
            disposition=EffectReservationDisposition.RESERVED_NEW,
            record=record,
        )

    def prepare_start(
        self,
        *,
        record: EffectLedgerRecord,
        attempt: int,
        now: Instant,
    ) -> EffectLedgerRecord:
        _require_record(record)
        _require_instant(now, "now")
        if record.lifecycle is not EffectLedgerLifecycle.RESERVED:
            raise EffectLedgerError(EffectLedgerErrorCode.RESERVATION_NOT_ACTIVE)
        if _is_expired(record, now):
            raise EffectLedgerError(EffectLedgerErrorCode.RESERVATION_EXPIRED)
        if attempt != record.attempt + 1:
            raise EffectLedgerError(EffectLedgerErrorCode.INVALID_TRANSITION)
        replacement = replace(
            record,
            version=record.version + 1,
            lifecycle=EffectLedgerLifecycle.IN_PROGRESS,
            effect_state=EffectState.UNKNOWN,
            reconciliation_status=ReconciliationStatus.PENDING,
            updated_at=now,
            attempts=(
                *record.attempts,
                EffectAttemptRecord(
                    attempt=attempt,
                    started_at=now,
                    effect_state=EffectState.UNKNOWN,
                ),
            ),
        )
        self.validate_compare_and_set(
            current=record,
            expected_version=record.version,
            replacement=replacement,
        )
        return replacement

    def prepare_finalize(
        self,
        *,
        record: EffectLedgerRecord,
        effect_state: EffectState,
        now: Instant,
        result_refs: tuple[ContractRef, ...] = (),
        error_code: str | None = None,
        retry_failure_facts: RetryFailureFacts | None = None,
    ) -> EffectLedgerRecord:
        _require_record(record)
        _require_instant(now, "now")
        if not isinstance(effect_state, EffectState):
            raise TypeError("effect_state must be an EffectState")
        if record.lifecycle is not EffectLedgerLifecycle.IN_PROGRESS:
            raise EffectLedgerError(EffectLedgerErrorCode.RESERVATION_NOT_ACTIVE)
        if retry_failure_facts is not None and not isinstance(
            retry_failure_facts, RetryFailureFacts
        ):
            raise TypeError("retry_failure_facts must be RetryFailureFacts or None")
        if retry_failure_facts is not None and error_code is None:
            error_code = retry_failure_facts.error_code
        latest = record.attempts[-1]
        finalized_attempt = replace(
            latest,
            ended_at=now,
            effect_state=effect_state,
            result_refs=tuple(result_refs),
            error_code=error_code,
            retry_failure_facts=retry_failure_facts,
        )
        reconciliation_status = (
            ReconciliationStatus.PENDING
            if effect_state in {EffectState.UNKNOWN, EffectState.PARTIAL}
            else ReconciliationStatus.NOT_REQUIRED
        )
        replacement = replace(
            record,
            version=record.version + 1,
            lifecycle=EffectLedgerLifecycle.FINALIZED,
            effect_state=effect_state,
            reconciliation_status=reconciliation_status,
            updated_at=now,
            attempts=(*record.attempts[:-1], finalized_attempt),
        )
        self.validate_compare_and_set(
            current=record,
            expected_version=record.version,
            replacement=replacement,
        )
        return replacement

    def prepare_retry_reservation(
        self,
        *,
        record: EffectLedgerRecord,
        now: Instant,
        reservation_expires_at: Instant | None = None,
    ) -> EffectLedgerRecord:
        """Reserve the same finalized NONE identity for its next explicit attempt."""
        _require_record(record)
        _require_instant(now, "now")
        if (
            record.lifecycle is not EffectLedgerLifecycle.FINALIZED
            or record.effect_state is not EffectState.NONE
            or record.reconciliation_status
            not in {ReconciliationStatus.NOT_REQUIRED, ReconciliationStatus.RESOLVED}
        ):
            raise EffectLedgerError(EffectLedgerErrorCode.INVALID_TRANSITION)
        _require_future_expiry(reservation_expires_at, now)
        replacement = replace(
            record,
            version=record.version + 1,
            lifecycle=EffectLedgerLifecycle.RESERVED,
            reconciliation_status=ReconciliationStatus.NOT_REQUIRED,
            updated_at=now,
            reservation_expires_at=reservation_expires_at,
        )
        self.validate_compare_and_set(
            current=record,
            expected_version=record.version,
            replacement=replacement,
        )
        return replacement

    def reactivate_abandoned_reservation(
        self,
        *,
        record: EffectLedgerRecord,
        now: Instant,
        reservation_expires_at: Instant | None = None,
    ) -> EffectLedgerRecord:
        """Reactivate a crash-abandoned reservation without creating an attempt."""
        _require_record(record)
        _require_instant(now, "now")
        if (
            record.lifecycle is not EffectLedgerLifecycle.ABANDONED
            or record.effect_state is not EffectState.NONE
            or record.attempt != 0
        ):
            raise EffectLedgerError(EffectLedgerErrorCode.INVALID_TRANSITION)
        _require_future_expiry(reservation_expires_at, now)
        replacement = replace(
            record,
            version=record.version + 1,
            lifecycle=EffectLedgerLifecycle.RESERVED,
            updated_at=now,
            reservation_expires_at=reservation_expires_at,
        )
        self.validate_compare_and_set(
            current=record,
            expected_version=record.version,
            replacement=replacement,
        )
        return replacement

    def prepare_abandon(
        self,
        *,
        record: EffectLedgerRecord,
        now: Instant,
    ) -> EffectLedgerRecord:
        _require_record(record)
        _require_instant(now, "now")
        if record.lifecycle is not EffectLedgerLifecycle.RESERVED:
            raise EffectLedgerError(EffectLedgerErrorCode.RESERVATION_NOT_ACTIVE)
        if not _is_expired(record, now):
            raise EffectLedgerError(EffectLedgerErrorCode.INVALID_TRANSITION)
        replacement = replace(
            record,
            version=record.version + 1,
            lifecycle=EffectLedgerLifecycle.ABANDONED,
            updated_at=now,
        )
        self.validate_compare_and_set(
            current=record,
            expected_version=record.version,
            replacement=replacement,
        )
        return replacement

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
        if expected_version != current.version:
            raise EffectLedgerError(EffectLedgerErrorCode.VERSION_CONFLICT)
        if replacement.version != current.version + 1:
            raise EffectLedgerError(EffectLedgerErrorCode.VERSION_CONFLICT)
        if (
            replacement.record_id != current.record_id
            or replacement.identity != current.identity
            or replacement.created_at != current.created_at
        ):
            raise EffectLedgerError(EffectLedgerErrorCode.INVALID_RECORD)
        expiry_change_allowed = (
            (current.lifecycle, replacement.lifecycle)
            in {
                (EffectLedgerLifecycle.ABANDONED, EffectLedgerLifecycle.RESERVED),
                (EffectLedgerLifecycle.FINALIZED, EffectLedgerLifecycle.RESERVED),
            }
        )
        if (
            replacement.reservation_expires_at != current.reservation_expires_at
            and not expiry_change_allowed
        ):
            raise EffectLedgerError(EffectLedgerErrorCode.INVALID_RECORD)
        if (current.lifecycle, replacement.lifecycle) not in _ALLOWED_TRANSITIONS:
            raise EffectLedgerError(EffectLedgerErrorCode.INVALID_TRANSITION)
        if replacement.attempts[: len(current.attempts)] != current.attempts:
            if current.lifecycle is not EffectLedgerLifecycle.IN_PROGRESS:
                raise EffectLedgerError(EffectLedgerErrorCode.INVALID_RECORD)
            if replacement.attempts[:-1] != current.attempts[:-1]:
                raise EffectLedgerError(EffectLedgerErrorCode.INVALID_RECORD)


def _is_expired(record: EffectLedgerRecord, now: Instant) -> bool:
    expires_at = record.reservation_expires_at
    return expires_at is not None and now.value >= expires_at.value


def _require_identity(value: IdempotencyIdentity) -> None:
    if not isinstance(value, IdempotencyIdentity):
        raise TypeError("identity must be an IdempotencyIdentity")


def _require_record(value: EffectLedgerRecord) -> None:
    if not isinstance(value, EffectLedgerRecord):
        raise TypeError("record must be an EffectLedgerRecord")


def _require_instant(value: Instant, field_name: str) -> None:
    if not isinstance(value, Instant):
        raise TypeError(f"{field_name} must be an Instant")


def _require_future_expiry(value: Instant | None, now: Instant) -> None:
    if value is not None:
        _require_instant(value, "reservation_expires_at")
        if value.value <= now.value:
            raise EffectLedgerError(EffectLedgerErrorCode.RESERVATION_EXPIRED)
