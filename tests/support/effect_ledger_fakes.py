from __future__ import annotations

from threading import Lock
from typing import Protocol

from backend.agent_runtime.recovery import (
    EffectLedgerError,
    EffectLedgerErrorCode,
    EffectLedgerRecord,
    EffectReservationResult,
    IdempotencyIdentity,
    IdempotencyPolicy,
)
from backend.shared_kernel._strings import require_non_empty
from backend.shared_kernel.time import Instant


class EffectLedgerCasValidator(Protocol):
    def __call__(
        self,
        *,
        current: EffectLedgerRecord,
        expected_version: int,
        replacement: EffectLedgerRecord,
    ) -> None: ...


class InMemoryEffectLedgerFake:
    """Thread-safe test fake; no production store is provided by Phase 12.11-B."""

    def __init__(
        self,
        policy: IdempotencyPolicy | None = None,
        *,
        initial_records: tuple[EffectLedgerRecord, ...] = (),
        cas_validator: EffectLedgerCasValidator | None = None,
    ) -> None:
        self._policy = policy or IdempotencyPolicy()
        self._records: dict[str, EffectLedgerRecord] = {}
        self._collision_index: dict[str, str] = {}
        self._cas_validator = cas_validator or self._policy.validate_compare_and_set
        self._lock = Lock()
        for record in initial_records:
            if not isinstance(record, EffectLedgerRecord):
                raise TypeError("initial_records must contain EffectLedgerRecord values")
            if record.record_id in self._records:
                raise ValueError("initial_records must have distinct record IDs")
            if record.identity.collision_key in self._collision_index:
                raise ValueError("initial_records must have distinct collision keys")
            self._records[record.record_id] = record
            self._collision_index[record.identity.collision_key] = record.record_id

    def reserve(
        self,
        *,
        identity: IdempotencyIdentity,
        now: Instant,
        reservation_expires_at: Instant | None = None,
    ) -> EffectReservationResult:
        with self._lock:
            existing_id = self._collision_index.get(identity.collision_key)
            if existing_id is not None:
                return self._policy.classify_reservation(
                    identity=identity,
                    existing=self._records[existing_id],
                    now=now,
                )
            existing = self._records.get(identity.record_id)
            if existing is not None:
                return self._policy.classify_reservation(
                    identity=identity,
                    existing=existing,
                    now=now,
                )
            record = self._policy.new_reservation(
                identity=identity,
                now=now,
                reservation_expires_at=reservation_expires_at,
            )
            self._records[record.record_id] = record
            self._collision_index[identity.collision_key] = record.record_id
            return self._policy.new_reservation_result(record)

    def get(self, *, record_id: str) -> EffectLedgerRecord | None:
        require_non_empty(record_id, "record_id")
        with self._lock:
            return self._records.get(record_id)

    def compare_and_set(
        self,
        *,
        record_id: str,
        expected_version: int,
        replacement: EffectLedgerRecord,
    ) -> EffectLedgerRecord:
        require_non_empty(record_id, "record_id")
        with self._lock:
            current = self._records.get(record_id)
            if current is None:
                raise EffectLedgerError(EffectLedgerErrorCode.UNKNOWN_RECORD)
            if current.version != expected_version:
                raise EffectLedgerError(EffectLedgerErrorCode.VERSION_CONFLICT)
            if replacement.record_id != record_id:
                raise EffectLedgerError(EffectLedgerErrorCode.INVALID_RECORD)
            self._cas_validator(
                current=current,
                expected_version=expected_version,
                replacement=replacement,
            )
            self._records[record_id] = replacement
            return replacement
