from __future__ import annotations

from dataclasses import dataclass

from backend.agent_runtime.contracts.observability.trace import (
    SamplingDecision,
    SpanId,
    TraceContext,
    TraceId,
)


@dataclass(frozen=True, slots=True)
class TraceContextPolicy:
    """Pure explicit-passing policy for local trace lineage."""

    def root(
        self,
        *,
        trace_id: TraceId,
        span_id: SpanId,
        sampling_decision: SamplingDecision,
    ) -> TraceContext:
        if not isinstance(trace_id, TraceId):
            raise TypeError("trace_id must be a TraceId")
        if not isinstance(span_id, SpanId):
            raise TypeError("span_id must be a SpanId")
        if not isinstance(sampling_decision, SamplingDecision):
            raise TypeError("sampling_decision must be a SamplingDecision")
        return TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            sampling_decision=sampling_decision,
        )

    def child(
        self,
        *,
        parent: TraceContext,
        child_span_id: SpanId,
    ) -> TraceContext:
        if not isinstance(parent, TraceContext):
            raise TypeError("parent must be a TraceContext")
        if not isinstance(child_span_id, SpanId):
            raise TypeError("child_span_id must be a SpanId")
        if child_span_id == parent.span_id:
            raise ValueError("child_span_id must differ from parent.span_id")
        return TraceContext(
            trace_id=parent.trace_id,
            span_id=child_span_id,
            parent_span_id=parent.span_id,
            sampling_decision=parent.sampling_decision,
        )

    def same_trace(self, first: TraceContext, second: TraceContext) -> bool:
        _require_context(first, "first")
        _require_context(second, "second")
        return first.trace_id == second.trace_id

    def is_direct_child(
        self,
        parent: TraceContext,
        child: TraceContext,
    ) -> bool:
        _require_context(parent, "parent")
        _require_context(child, "child")
        return bool(
            child.trace_id == parent.trace_id
            and child.parent_span_id == parent.span_id
            and child.span_id != parent.span_id
            and child.sampling_decision is parent.sampling_decision
        )


def _require_context(value: TraceContext, field_name: str) -> None:
    if not isinstance(value, TraceContext):
        raise TypeError(f"{field_name} must be a TraceContext")
