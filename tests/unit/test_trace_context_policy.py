from __future__ import annotations

import pytest

from backend.agent_runtime.contracts import (
    SamplingDecision,
    SpanId,
    TraceContext,
    TraceId,
)
from backend.agent_runtime.observability import TraceContextPolicy


@pytest.mark.parametrize("sampling_decision", list(SamplingDecision))
def test_root_context_uses_only_caller_supplied_values(
    sampling_decision: SamplingDecision,
) -> None:
    policy = TraceContextPolicy()
    trace_id = TraceId("trace-run-01")
    span_id = SpanId("span-root-01")

    root = policy.root(
        trace_id=trace_id,
        span_id=span_id,
        sampling_decision=sampling_decision,
    )

    assert root == TraceContext(trace_id, span_id, None, sampling_decision)
    assert root.trace_id is trace_id
    assert root.span_id is span_id
    assert root.parent_span_id is None


@pytest.mark.parametrize("sampling_decision", list(SamplingDecision))
def test_child_preserves_exact_lineage_and_sampling(
    sampling_decision: SamplingDecision,
) -> None:
    policy = TraceContextPolicy()
    parent = policy.root(
        trace_id=TraceId("trace-run-01"),
        span_id=SpanId("span-parent-01"),
        sampling_decision=sampling_decision,
    )
    child_span_id = SpanId("span-child-01")

    child = policy.child(parent=parent, child_span_id=child_span_id)

    assert child.trace_id is parent.trace_id
    assert child.parent_span_id is parent.span_id
    assert child.span_id is child_span_id
    assert child.sampling_decision is sampling_decision
    assert policy.same_trace(parent, child)
    assert policy.is_direct_child(parent, child)


def test_continuity_helpers_reject_unrelated_or_non_direct_contexts() -> None:
    policy = TraceContextPolicy()
    parent = policy.root(
        trace_id=TraceId("trace-run-01"),
        span_id=SpanId("span-root-01"),
        sampling_decision=SamplingDecision.RECORD_ONLY,
    )
    sibling = TraceContext(
        trace_id=parent.trace_id,
        span_id=SpanId("span-sibling-01"),
        parent_span_id=None,
        sampling_decision=parent.sampling_decision,
    )
    other_trace = TraceContext(
        trace_id=TraceId("trace-run-02"),
        span_id=SpanId("span-other-01"),
        parent_span_id=parent.span_id,
        sampling_decision=parent.sampling_decision,
    )

    assert policy.same_trace(parent, sibling)
    assert not policy.is_direct_child(parent, sibling)
    assert not policy.same_trace(parent, other_trace)
    assert not policy.is_direct_child(parent, other_trace)


def test_child_refuses_parent_span_id_reuse() -> None:
    policy = TraceContextPolicy()
    parent = policy.root(
        trace_id=TraceId("trace-run-01"),
        span_id=SpanId("span-root-01"),
        sampling_decision=SamplingDecision.RECORD_AND_SAMPLE,
    )

    with pytest.raises(ValueError, match="differ from parent"):
        policy.child(parent=parent, child_span_id=parent.span_id)


def test_policy_requires_typed_context_and_identifiers() -> None:
    policy = TraceContextPolicy()

    with pytest.raises(TypeError, match="trace_id"):
        policy.root(  # type: ignore[arg-type]
            trace_id="trace-run-01",
            span_id=SpanId("span-root-01"),
            sampling_decision=SamplingDecision.RECORD_ONLY,
        )
    with pytest.raises(TypeError, match="parent"):
        policy.child(  # type: ignore[arg-type]
            parent={"trace_id": "legacy"},
            child_span_id=SpanId("span-child-01"),
        )
    with pytest.raises(TypeError, match="first"):
        policy.same_trace("legacy", TraceContextPolicy())  # type: ignore[arg-type]


def test_retry_attempts_keep_trace_and_use_distinct_caller_supplied_spans() -> None:
    policy = TraceContextPolicy()
    cycle = policy.root(
        trace_id=TraceId("trace-run-01"),
        span_id=SpanId("span-cycle-01"),
        sampling_decision=SamplingDecision.RECORD_ONLY,
    )

    first_attempt = policy.child(
        parent=cycle,
        child_span_id=SpanId("span-attempt-01"),
    )
    second_attempt = policy.child(
        parent=cycle,
        child_span_id=SpanId("span-attempt-02"),
    )

    assert first_attempt.trace_id == second_attempt.trace_id == cycle.trace_id
    assert first_attempt.span_id != second_attempt.span_id
    assert policy.is_direct_child(cycle, first_attempt)
    assert policy.is_direct_child(cycle, second_attempt)
