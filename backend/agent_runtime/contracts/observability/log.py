from __future__ import annotations

import re
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
from backend.agent_runtime.contracts.observability.trace import TraceContext
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

_OBSERVATION_CODE = re.compile(r"^[A-Z][A-Z0-9_.-]{0,127}$")


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ObservationCode:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str:
            raise TypeError("observation code must be a string")
        if not _OBSERVATION_CODE.fullmatch(self.value):
            raise ValueError("observation code must be a bounded closed code")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class StructuredLogRecord:
    """Completed data-only log observation identified by a closed code."""

    schema_version: ContractSchemaVersion
    record_id: str
    occurred_at: Instant
    level: LogLevel
    code: ObservationCode
    correlation_id: CorrelationId
    run_id: str | None = None
    step_id: str | None = None
    trace_context: TraceContext | None = None
    refs: tuple[ContractRef, ...] = ()
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, ContractSchemaVersion):
            raise TypeError("schema_version must be a ContractSchemaVersion")
        require_observability_id(self.record_id, "record_id")
        require_utc_instant(self.occurred_at, "occurred_at")
        if not isinstance(self.level, LogLevel):
            raise TypeError("level must be a LogLevel")
        if not isinstance(self.code, ObservationCode):
            raise TypeError("code must be an ObservationCode")
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")
        require_observability_id(self.correlation_id.value, "correlation_id")
        for field_name in ("run_id", "step_id"):
            value = getattr(self, field_name)
            if value is not None:
                require_observability_id(value, field_name)
        if self.trace_context is not None and not isinstance(
            self.trace_context, TraceContext
        ):
            raise TypeError("trace_context must be a TraceContext or None")
        object.__setattr__(self, "refs", normalize_observation_refs(self.refs))
        object.__setattr__(
            self,
            "attributes",
            freeze_observability_attributes(self.attributes),
        )
