from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.agent_runtime.contracts import SpanId, TraceContext
from backend.shared_kernel.time import Instant


@runtime_checkable
class ObservationIdSourcePort(Protocol):
    """Technical opaque identifiers; never derived from business content."""

    def new_record_id(self) -> str: ...

    def new_span_id(self) -> SpanId: ...


@runtime_checkable
class ObservationClockPort(Protocol):
    """Telemetry-only clock whose values never feed runtime decisions."""

    def now(self) -> Instant: ...


class RuntimeObservabilityContext:
    """Caller-owned trace sidecar for one logical run.

    The root must be restored explicitly by the caller after a crash.  The mutable
    current pointer is scoped to one synchronous cycle and is never snapshotted.
    """

    __slots__ = ("_current", "_root")

    def __init__(self, root: TraceContext) -> None:
        if not isinstance(root, TraceContext):
            raise TypeError("root must be a TraceContext")
        self._root = root
        self._current = root

    @property
    def root(self) -> TraceContext:
        return self._root

    @property
    def current(self) -> TraceContext:
        return self._current

    def activate(self, context: TraceContext) -> TraceContext:
        if not isinstance(context, TraceContext):
            raise TypeError("context must be a TraceContext")
        if context.trace_id != self._root.trace_id:
            raise ValueError("active context must belong to the logical-run trace")
        previous = self._current
        self._current = context
        return previous

    def restore(self, context: TraceContext) -> None:
        if not isinstance(context, TraceContext):
            raise TypeError("context must be a TraceContext")
        if context.trace_id != self._root.trace_id:
            raise ValueError("restored context must belong to the logical-run trace")
        self._current = context


@dataclass(frozen=True, slots=True)
class PendingObservationSpan:
    trace_context: TraceContext
    started_at: Instant

    def __post_init__(self) -> None:
        if not isinstance(self.trace_context, TraceContext):
            raise TypeError("trace_context must be a TraceContext")
        if not isinstance(self.started_at, Instant):
            raise TypeError("started_at must be an Instant")
