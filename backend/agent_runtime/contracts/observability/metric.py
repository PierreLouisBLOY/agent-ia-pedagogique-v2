from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from backend.agent_runtime.contracts.common import ContractSchemaVersion
from backend.agent_runtime.contracts.observability._validation import require_utc_instant
from backend.agent_runtime.contracts.observability.log import ObservationCode
from backend.agent_runtime.contracts.observability.trace import TraceContext
from backend.shared_kernel.time import Instant

_METRIC_NAME = re.compile(r"^[a-z][a-z0-9_.]{0,127}$")
_METRIC_UNIT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_LABEL_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_LABEL_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_FORBIDDEN_LABEL_KEYS = frozenset(
    {
        "artifact_ref",
        "correlation_id",
        "delegation_id",
        "evidence_ref",
        "invocation_id",
        "record_id",
        "run_id",
        "step_id",
        "trace_id",
        "span_id",
        "url",
        "file_path",
        "local_path",
    }
)


class MetricKind(StrEnum):
    COUNTER = "COUNTER"
    UP_DOWN_COUNTER = "UP_DOWN_COUNTER"
    GAUGE = "GAUGE"
    HISTOGRAM = "HISTOGRAM"


@dataclass(frozen=True, slots=True)
class MetricName:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str or not _METRIC_NAME.fullmatch(self.value):
            raise ValueError("metric name must be a bounded canonical name")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class MetricUnit:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str or not _METRIC_UNIT.fullmatch(self.value):
            raise ValueError("metric unit must be a bounded canonical unit")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class MetricLabelSpec:
    key: str
    allowed_values: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.key) is not str or not _LABEL_KEY.fullmatch(self.key):
            raise ValueError("metric label key must be a bounded canonical key")
        if self.key in _FORBIDDEN_LABEL_KEYS:
            raise ValueError("high-cardinality metric label key is forbidden")
        if type(self.allowed_values) is not tuple or not self.allowed_values:
            raise ValueError("metric label values must be a non-empty tuple")
        if len(self.allowed_values) > 64:
            raise ValueError("metric label values must contain at most 64 items")
        if any(
            type(value) is not str or not _LABEL_VALUE.fullmatch(value)
            for value in self.allowed_values
        ):
            raise ValueError("metric label values must be bounded registry values")
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("metric label values must be unique")


@dataclass(frozen=True, slots=True)
class MetricDescriptor:
    """Canonical bounded series definition independent from any exporter."""

    schema_version: ContractSchemaVersion
    name: MetricName
    kind: MetricKind
    unit: MetricUnit
    description_code: ObservationCode
    allowed_labels: tuple[MetricLabelSpec, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, ContractSchemaVersion):
            raise TypeError("schema_version must be a ContractSchemaVersion")
        if not isinstance(self.name, MetricName):
            raise TypeError("name must be a MetricName")
        if not isinstance(self.kind, MetricKind):
            raise TypeError("kind must be a MetricKind")
        if not isinstance(self.unit, MetricUnit):
            raise TypeError("unit must be a MetricUnit")
        if not isinstance(self.description_code, ObservationCode):
            raise TypeError("description_code must be an ObservationCode")
        if type(self.allowed_labels) is not tuple:
            raise TypeError("allowed_labels must be a tuple")
        if len(self.allowed_labels) > 8:
            raise ValueError("allowed_labels must contain at most 8 items")
        if any(not isinstance(item, MetricLabelSpec) for item in self.allowed_labels):
            raise TypeError("allowed_labels must contain MetricLabelSpec values")
        keys = tuple(item.key for item in self.allowed_labels)
        if len(set(keys)) != len(keys):
            raise ValueError("metric label keys must be unique")

    @property
    def allowed_label_keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.allowed_labels)


@dataclass(frozen=True, slots=True)
class MetricPoint:
    descriptor: MetricDescriptor
    observed_at: Instant
    value: int | float | Decimal
    labels: Mapping[str, str] = field(default_factory=dict)
    trace_context: TraceContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, MetricDescriptor):
            raise TypeError("descriptor must be a MetricDescriptor")
        require_utc_instant(self.observed_at, "observed_at")
        _require_finite_metric_value(self.value)
        if not isinstance(self.labels, Mapping):
            raise TypeError("labels must be a mapping")
        if any(type(key) is not str or type(value) is not str for key, value in self.labels.items()):
            raise TypeError("metric labels must map strings to strings")
        expected = {item.key: item for item in self.descriptor.allowed_labels}
        if set(self.labels) != set(expected):
            raise ValueError("metric labels must exactly match the descriptor")
        normalized: dict[str, str] = {}
        for key, value in self.labels.items():
            if value not in expected[key].allowed_values:
                raise ValueError("metric label value is outside the descriptor allowlist")
            normalized[key] = value
        if self.trace_context is not None and not isinstance(
            self.trace_context, TraceContext
        ):
            raise TypeError("trace_context must be a TraceContext or None")
        object.__setattr__(self, "labels", MappingProxyType(normalized))


def _require_finite_metric_value(value: int | float | Decimal) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError("metric value must be numeric")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("metric value must be finite")
    elif isinstance(value, float) and (
        value != value or value in (float("inf"), float("-inf"))
    ):
        raise ValueError("metric value must be finite")
