from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from backend.agent_runtime.contracts import (
    MetricDescriptor,
    MetricKind,
    MetricPoint,
    TraceContext,
)
from backend.agent_runtime.observability.metric_catalog import (
    METRIC_CATALOG,
    MetricCode,
    metric_descriptor,
)
from backend.shared_kernel.time import Instant

MetricValue = int | float | Decimal
SeriesIdentity = tuple[str, tuple[tuple[str, str], ...]]


class MetricPointErrorCode(StrEnum):
    KIND_MISMATCH = "KIND_MISMATCH"
    NEGATIVE_COUNTER = "NEGATIVE_COUNTER"


_ERROR_MESSAGES = MappingProxyType(
    {
        MetricPointErrorCode.KIND_MISMATCH: "metric kind does not match point factory",
        MetricPointErrorCode.NEGATIVE_COUNTER: "counter value must be non-negative",
    }
)


class MetricPointError(ValueError):
    code: MetricPointErrorCode

    def __init__(self, code: MetricPointErrorCode) -> None:
        if not isinstance(code, MetricPointErrorCode):
            raise TypeError("code must be a MetricPointErrorCode")
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])


def counter_metric_point(
    code: MetricCode,
    *,
    observed_at: Instant,
    value: MetricValue,
    labels: Mapping[str, str],
    trace_context: TraceContext | None = None,
) -> MetricPoint:
    descriptor = _require_kind(code, MetricKind.COUNTER)
    if _is_negative(value):
        raise MetricPointError(MetricPointErrorCode.NEGATIVE_COUNTER)
    return MetricPoint(descriptor, observed_at, value, labels, trace_context)


def gauge_metric_point(
    code: MetricCode,
    *,
    observed_at: Instant,
    value: MetricValue,
    labels: Mapping[str, str],
    trace_context: TraceContext | None = None,
) -> MetricPoint:
    descriptor = _require_kind(code, MetricKind.GAUGE)
    return MetricPoint(descriptor, observed_at, value, labels, trace_context)


def histogram_metric_point(
    code: MetricCode,
    *,
    observed_at: Instant,
    value: MetricValue,
    labels: Mapping[str, str],
    trace_context: TraceContext | None = None,
) -> MetricPoint:
    descriptor = _require_kind(code, MetricKind.HISTOGRAM)
    return MetricPoint(descriptor, observed_at, value, labels, trace_context)


def descriptor_series_bound(descriptor: MetricDescriptor) -> int:
    if not isinstance(descriptor, MetricDescriptor):
        raise TypeError("descriptor must be a MetricDescriptor")
    bound = 1
    for label in descriptor.allowed_labels:
        bound *= len(label.allowed_values)
    return bound


def catalog_series_bound() -> int:
    return sum(descriptor_series_bound(item) for item in METRIC_CATALOG)


def series_identity(point: MetricPoint) -> SeriesIdentity:
    if not isinstance(point, MetricPoint):
        raise TypeError("point must be a MetricPoint")
    return point.descriptor.name.value, tuple(sorted(point.labels.items()))


def _require_kind(code: MetricCode, expected: MetricKind) -> MetricDescriptor:
    descriptor = metric_descriptor(code)
    if descriptor.kind is not expected:
        raise MetricPointError(MetricPointErrorCode.KIND_MISMATCH)
    return descriptor


def _is_negative(value: MetricValue) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return False
    if isinstance(value, Decimal) and not value.is_finite():
        return False
    if isinstance(value, float) and (
        value != value or value in (float("inf"), float("-inf"))
    ):
        return False
    return value < 0
