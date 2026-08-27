from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.agent_runtime.contracts import SpanId
from backend.shared_kernel.time import Instant


class UuidObservationIdProvider:
    """Opaque random technical IDs independent from runtime and business facts."""

    def new_record_id(self) -> str:
        return uuid4().hex

    def new_span_id(self) -> SpanId:
        return SpanId(uuid4().hex)


class UtcObservationClock:
    """System UTC time reserved for telemetry timestamps."""

    def now(self) -> Instant:
        return Instant(datetime.now(UTC))
