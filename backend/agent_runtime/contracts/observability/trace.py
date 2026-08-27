from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.agent_runtime.contracts.observability._validation import (
    require_observability_id,
)


class SamplingDecision(StrEnum):
    """Observation-only recording decision with no runtime semantics."""

    DROP = "DROP"
    RECORD_ONLY = "RECORD_ONLY"
    RECORD_AND_SAMPLE = "RECORD_AND_SAMPLE"


@dataclass(frozen=True, slots=True)
class TraceId:
    value: str

    def __post_init__(self) -> None:
        require_observability_id(self.value, "trace_id")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class SpanId:
    value: str

    def __post_init__(self) -> None:
        require_observability_id(self.value, "span_id")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Provider-neutral trace lineage without baggage or authority."""

    trace_id: TraceId
    span_id: SpanId
    parent_span_id: SpanId | None
    sampling_decision: SamplingDecision

    def __post_init__(self) -> None:
        if not isinstance(self.trace_id, TraceId):
            raise TypeError("trace_id must be a TraceId")
        if not isinstance(self.span_id, SpanId):
            raise TypeError("span_id must be a SpanId")
        if self.parent_span_id is not None and not isinstance(
            self.parent_span_id, SpanId
        ):
            raise TypeError("parent_span_id must be a SpanId or None")
        if self.parent_span_id == self.span_id:
            raise ValueError("parent_span_id must differ from span_id")
        if not isinstance(self.sampling_decision, SamplingDecision):
            raise TypeError("sampling_decision must be a SamplingDecision")
