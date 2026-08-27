from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType

import pytest

from backend.agent_runtime.contracts import (
    MetricKind,
    SamplingDecision,
    SpanId,
    TraceContext,
    TraceId,
)
from backend.agent_runtime.observability import (
    MAX_CATALOG_SERIES,
    MAX_SERIES_PER_DESCRIPTOR,
    METRIC_CATALOG,
    MetricCode,
    MetricPointError,
    MetricPointErrorCode,
    catalog_series_bound,
    counter_metric_point,
    descriptor_series_bound,
    gauge_metric_point,
    metric_descriptor,
    series_identity,
)
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))
LATER = Instant(NOW.value + timedelta(seconds=1))


def _trace(sampling: SamplingDecision) -> TraceContext:
    return TraceContext(TraceId("trace-01"), SpanId("span-01"), None, sampling)


def test_catalog_is_exhaustive_unique_and_immutable() -> None:
    names = tuple(item.name.value for item in METRIC_CATALOG)
    descriptions = tuple(item.description_code.value for item in METRIC_CATALOG)

    assert type(METRIC_CATALOG) is tuple
    assert names == tuple(item.value for item in MetricCode)
    assert len(set(names)) == len(names)
    assert len(set(descriptions)) == len(descriptions)
    assert all(item.kind is not MetricKind.UP_DOWN_COUNTER for item in METRIC_CATALOG)
    assert all(metric_descriptor(code).name.value == code.value for code in MetricCode)
    with pytest.raises(FrozenInstanceError):
        METRIC_CATALOG[0].kind = MetricKind.COUNTER  # type: ignore[misc]


def test_catalog_labels_are_exact_closed_source_vocabularies() -> None:
    assert metric_descriptor(
        MetricCode.BUDGET_CONSUMED_TOKENS
    ).allowed_labels[0].allowed_values == ("COMPLETE", "PARTIAL", "UNKNOWN")
    assert metric_descriptor(
        MetricCode.RETRIEVAL_RESULT_CANDIDATES
    ).allowed_labels[0].allowed_values == (
        "STRUCTURED",
        "LEXICAL",
        "SEMANTIC",
        "RELATIONAL",
        "DOCUMENT",
    )
    assert metric_descriptor(MetricCode.SECURITY_EVENTS).allowed_label_keys == (
        "event_type",
        "severity",
    )
    assert metric_descriptor(MetricCode.ERRORS).allowed_label_keys == (
        "category",
        "source",
        "severity",
    )


def test_catalog_cardinality_is_statically_bounded() -> None:
    bounds = tuple(descriptor_series_bound(item) for item in METRIC_CATALOG)

    assert max(bounds) == 192
    assert all(item <= MAX_SERIES_PER_DESCRIPTOR for item in bounds)
    assert catalog_series_bound() == 285
    assert catalog_series_bound() <= MAX_CATALOG_SERIES


def test_point_factories_enforce_kind_and_non_negative_counters() -> None:
    with pytest.raises(MetricPointError) as negative:
        counter_metric_point(
            MetricCode.SECURITY_EVENTS,
            observed_at=NOW,
            value=-1,
            labels={
                "event_type": "tool_injection",
                "severity": "high",
            },
        )
    assert negative.value.code is MetricPointErrorCode.NEGATIVE_COUNTER

    with pytest.raises(MetricPointError) as mismatch:
        gauge_metric_point(
            MetricCode.SECURITY_EVENTS,
            observed_at=NOW,
            value=1,
            labels={
                "event_type": "tool_injection",
                "severity": "high",
            },
        )
    assert mismatch.value.code is MetricPointErrorCode.KIND_MISMATCH

    with pytest.raises(ValueError, match="finite"):
        counter_metric_point(
            MetricCode.SECURITY_EVENTS,
            observed_at=NOW,
            value=Decimal("NaN"),
            labels={
                "event_type": "tool_injection",
                "severity": "high",
            },
        )


def test_series_identity_excludes_time_and_trace_exemplar() -> None:
    labels = {"event_type": "tool_injection", "severity": "high"}
    first = counter_metric_point(
        MetricCode.SECURITY_EVENTS,
        observed_at=NOW,
        value=1,
        labels=labels,
        trace_context=_trace(SamplingDecision.DROP),
    )
    second = counter_metric_point(
        MetricCode.SECURITY_EVENTS,
        observed_at=LATER,
        value=7,
        labels=dict(reversed(tuple(labels.items()))),
        trace_context=_trace(SamplingDecision.RECORD_AND_SAMPLE),
    )

    assert isinstance(first.labels, MappingProxyType)
    assert series_identity(first) == series_identity(second)
    assert series_identity(first) == (
        MetricCode.SECURITY_EVENTS.value,
        (("event_type", "tool_injection"), ("severity", "high")),
    )
