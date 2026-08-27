from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from backend.agent_runtime.contracts.common import ContractRef, ContractSchemaVersion
from backend.agent_runtime.contracts.observability._validation import (
    freeze_observability_attributes,
    normalize_observation_refs,
    require_observability_id,
    require_utc_instant,
)
from backend.agent_runtime.contracts.observability.log import ObservationCode
from backend.agent_runtime.contracts.observability.trace import TraceContext
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


class SpanKind(StrEnum):
    INTERNAL = "INTERNAL"
    RUNTIME = "RUNTIME"
    AGENT = "AGENT"
    TOOL = "TOOL"
    APPLICATION = "APPLICATION"
    GATE = "GATE"
    RECOVERY = "RECOVERY"


class SpanStatus(StrEnum):
    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class SpanRecord:
    """Completed data-only span; OK is technical and grants no authority."""

    schema_version: ContractSchemaVersion
    trace_context: TraceContext
    code: ObservationCode
    kind: SpanKind
    status: SpanStatus
    started_at: Instant
    ended_at: Instant
    correlation_id: CorrelationId
    run_id: str | None = None
    step_id: str | None = None
    refs: tuple[ContractRef, ...] = ()
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, ContractSchemaVersion):
            raise TypeError("schema_version must be a ContractSchemaVersion")
        if not isinstance(self.trace_context, TraceContext):
            raise TypeError("trace_context must be a TraceContext")
        if not isinstance(self.code, ObservationCode):
            raise TypeError("code must be an ObservationCode")
        if not isinstance(self.kind, SpanKind):
            raise TypeError("kind must be a SpanKind")
        if not isinstance(self.status, SpanStatus):
            raise TypeError("status must be a SpanStatus")
        require_utc_instant(self.started_at, "started_at")
        require_utc_instant(self.ended_at, "ended_at")
        if self.ended_at.value < self.started_at.value:
            raise ValueError("ended_at must be >= started_at")
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")
        require_observability_id(self.correlation_id.value, "correlation_id")
        for field_name in ("run_id", "step_id"):
            value = getattr(self, field_name)
            if value is not None:
                require_observability_id(value, field_name)
        object.__setattr__(self, "refs", normalize_observation_refs(self.refs))
        object.__setattr__(
            self,
            "attributes",
            freeze_observability_attributes(self.attributes),
        )
