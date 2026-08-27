from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    MetricDescriptor,
    MetricKind,
    MetricLabelSpec,
    MetricName,
    MetricPoint,
    MetricUnit,
    ObservationCode,
    SamplingDecision,
    SpanId,
    TraceContext,
    TraceId,
)
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))


def _descriptor(**changes: object) -> MetricDescriptor:
    values: dict[str, object] = {
        "schema_version": AGENT_CONTRACT_SCHEMA_V1_0,
        "name": MetricName("agent_runtime.step.duration"),
        "kind": MetricKind.HISTOGRAM,
        "unit": MetricUnit("ms"),
        "description_code": ObservationCode("METRIC.STEP_DURATION"),
        "allowed_labels": (
            MetricLabelSpec("route", ("AGENT", "APPLICATION", "UTILITY")),
            MetricLabelSpec("status", ("SUCCEEDED", "FAILED")),
        ),
    }
    values.update(changes)
    return MetricDescriptor(**values)  # type: ignore[arg-type]


def test_metric_descriptor_defines_closed_low_cardinality_series() -> None:
    descriptor = _descriptor()

    assert descriptor.allowed_label_keys == ("route", "status")
    assert [item.value for item in MetricKind] == [
        "COUNTER",
        "UP_DOWN_COUNTER",
        "GAUGE",
        "HISTOGRAM",
    ]
    assert not hasattr(descriptor, "__dict__")
    with pytest.raises(FrozenInstanceError):
        descriptor.kind = MetricKind.GAUGE  # type: ignore[misc]


@pytest.mark.parametrize(
    "key",
    [
        "correlation_id",
        "run_id",
        "step_id",
        "invocation_id",
        "delegation_id",
        "record_id",
        "artifact_ref",
        "evidence_ref",
        "trace_id",
        "span_id",
        "url",
        "file_path",
        "local_path",
    ],
)
def test_metric_descriptor_rejects_high_cardinality_label_keys(key: str) -> None:
    with pytest.raises(ValueError, match="high-cardinality"):
        MetricLabelSpec(key, ("value",))


def test_metric_label_values_are_closed_bounded_and_unique() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        MetricLabelSpec("route", ())
    with pytest.raises(ValueError, match="unique"):
        MetricLabelSpec("route", ("AGENT", "AGENT"))
    with pytest.raises(ValueError, match="bounded registry"):
        MetricLabelSpec("route", ("user supplied value",))
    with pytest.raises(ValueError, match="at most 8"):
        _descriptor(
            allowed_labels=tuple(
                MetricLabelSpec(f"label_{index}", ("FIXED",))
                for index in range(9)
            )
        )


def test_metric_point_accepts_only_exact_allowlisted_labels() -> None:
    descriptor = _descriptor()
    point = MetricPoint(
        descriptor=descriptor,
        observed_at=NOW,
        value=Decimal("12.5"),
        labels={"route": "AGENT", "status": "SUCCEEDED"},
        trace_context=TraceContext(
            TraceId("trace-01"),
            SpanId("span-01"),
            None,
            SamplingDecision.RECORD_ONLY,
        ),
    )

    assert isinstance(point.labels, MappingProxyType)
    assert point.labels == {"route": "AGENT", "status": "SUCCEEDED"}
    with pytest.raises(TypeError):
        point.labels["route"] = "UTILITY"  # type: ignore[index]

    with pytest.raises(ValueError, match="exactly"):
        MetricPoint(descriptor, NOW, 1, {"route": "AGENT"})
    with pytest.raises(ValueError, match="outside"):
        MetricPoint(
            descriptor,
            NOW,
            1,
            {"route": "DYNAMIC", "status": "SUCCEEDED"},
        )


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf"), Decimal("NaN"), Decimal("Infinity")],
)
def test_metric_point_rejects_non_finite_values(value: float | Decimal) -> None:
    with pytest.raises(ValueError, match="finite"):
        MetricPoint(
            _descriptor(),
            NOW,
            value,
            {"route": "AGENT", "status": "SUCCEEDED"},
        )


def test_metric_point_rejects_boolean_or_non_numeric_values() -> None:
    labels = {"route": "AGENT", "status": "SUCCEEDED"}
    with pytest.raises(TypeError, match="numeric"):
        MetricPoint(_descriptor(), NOW, True, labels)
    with pytest.raises(TypeError, match="numeric"):
        MetricPoint(_descriptor(), NOW, "1", labels)  # type: ignore[arg-type]
