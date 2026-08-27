from __future__ import annotations

from collections.abc import Mapping

from backend.agent_runtime.contracts.common import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ContractRef,
)
from backend.agent_runtime.contracts.observability.span import (
    SpanKind,
    SpanRecord,
    SpanStatus,
)
from backend.agent_runtime.contracts.observability.trace import TraceContext
from backend.agent_runtime.observability.span_catalog import (
    SpanCode,
    span_observation_code,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


def completed_span(
    *,
    trace_context: TraceContext,
    code: SpanCode,
    kind: SpanKind,
    status: SpanStatus,
    started_at: Instant,
    ended_at: Instant,
    correlation_id: CorrelationId,
    run_id: str | None = None,
    step_id: str | None = None,
    refs: tuple[ContractRef, ...] = (),
    attributes: Mapping[str, object] | None = None,
) -> SpanRecord:
    """Compose one completed span from fully caller-supplied data."""

    return SpanRecord(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        trace_context=trace_context,
        code=span_observation_code(code),
        kind=kind,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        correlation_id=correlation_id,
        run_id=run_id,
        step_id=step_id,
        refs=refs,
        attributes={} if attributes is None else attributes,
    )
