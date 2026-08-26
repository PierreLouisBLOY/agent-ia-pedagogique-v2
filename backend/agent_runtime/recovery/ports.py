from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.agent_runtime.recovery.model import (
    EffectLedgerRecord,
    EffectReservationResult,
    IdempotencyIdentity,
)
from backend.shared_kernel.time import Instant


@runtime_checkable
class EffectLedgerPort(Protocol):
    """Atomic technical persistence boundary without permission semantics."""

    def reserve(
        self,
        *,
        identity: IdempotencyIdentity,
        now: Instant,
        reservation_expires_at: Instant | None = None,
    ) -> EffectReservationResult: ...

    def get(self, *, record_id: str) -> EffectLedgerRecord | None: ...

    def compare_and_set(
        self,
        *,
        record_id: str,
        expected_version: int,
        replacement: EffectLedgerRecord,
    ) -> EffectLedgerRecord: ...
