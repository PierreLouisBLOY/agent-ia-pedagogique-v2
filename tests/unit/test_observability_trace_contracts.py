from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    InvocationStatus,
    SamplingDecision,
    SpanId,
    TraceContext,
    TraceId,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


def test_trace_context_is_minimal_immutable_and_has_no_baggage() -> None:
    context = TraceContext(
        trace_id=TraceId("trace-01"),
        span_id=SpanId("span-01"),
        parent_span_id=SpanId("span-parent"),
        sampling_decision=SamplingDecision.RECORD_AND_SAMPLE,
    )

    assert {item.name for item in fields(TraceContext)} == {
        "trace_id",
        "span_id",
        "parent_span_id",
        "sampling_decision",
    }
    assert not hasattr(context, "baggage")
    assert not hasattr(context, "trace_state")
    assert not hasattr(context, "__dict__")
    with pytest.raises(FrozenInstanceError):
        context.parent_span_id = None  # type: ignore[misc]


def test_sampling_decision_is_closed_and_observation_only() -> None:
    assert [item.value for item in SamplingDecision] == [
        "DROP",
        "RECORD_ONLY",
        "RECORD_AND_SAMPLE",
    ]
    assert {item.name for item in fields(TraceContext)}.isdisjoint(
        {"authority", "permission", "gate", "retry", "recovery", "effect_state"}
    )


@pytest.mark.parametrize(
    "factory",
    [TraceId, SpanId],
)
@pytest.mark.parametrize(
    "value",
    ["", "../trace", "https://trace.test/1", "trace with spaces", "x" * 129],
)
def test_trace_identifiers_reject_non_opaque_values(
    factory: type[TraceId] | type[SpanId], value: str
) -> None:
    with pytest.raises((ValueError, TypeError)):
        factory(value)


def test_trace_context_rejects_self_parent_and_untyped_values() -> None:
    span_id = SpanId("span-01")

    with pytest.raises(ValueError, match="differ"):
        TraceContext(
            TraceId("trace-01"),
            span_id,
            span_id,
            SamplingDecision.RECORD_ONLY,
        )
    with pytest.raises(TypeError, match="sampling_decision"):
        TraceContext(
            TraceId("trace-01"),
            span_id,
            None,
            "RECORD_ONLY",  # type: ignore[arg-type]
        )


def test_correlation_id_and_trace_id_remain_distinct_types() -> None:
    correlation_id = CorrelationId("correlation-01")
    trace_id = TraceId("trace-01")

    assert correlation_id != trace_id
    assert type(correlation_id) is CorrelationId
    assert type(trace_id) is TraceId


def test_legacy_trace_flags_remain_opaque_and_are_not_interpreted() -> None:
    meta = ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id="run-01",
        step_id="step-01",
        parent_step_id=None,
        correlation_id=CorrelationId("correlation-01"),
        created_at=Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC)),
        actor=ActorRef(ActorKind.AGENT, "AG-01"),
        status=InvocationStatus.PLANNED,
        trace_flags={"legacy_vendor_flag": "opaque", "sample_hint": False},
    )

    assert meta.trace_flags == {
        "legacy_vendor_flag": "opaque",
        "sample_hint": False,
    }
    assert not hasattr(meta, "trace_context")
    assert not isinstance(meta.trace_flags, TraceContext)
