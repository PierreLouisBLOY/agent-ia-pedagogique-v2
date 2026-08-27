from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.contracts import (
    MetricPoint,
    SpanRecord,
    StructuredLogRecord,
    TraceContext,
)
from backend.agent_runtime.observability.delivery_model import ObservationChannel
from backend.shared_kernel._value_safety import require_safe_structured_value
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import (
    ObjectVersionRef,
    TypedEntityRef,
    VersionRef,
)
from backend.shared_kernel.time import Instant

MAX_SERIALIZED_RECORD_BYTES: Final = 65_536


class ObservabilitySerializationErrorCode(StrEnum):
    INVALID_RECORD = "INVALID_RECORD"
    UNSUPPORTED_VALUE = "UNSUPPORTED_VALUE"
    NON_FINITE_VALUE = "NON_FINITE_VALUE"
    RECORD_TOO_LARGE = "RECORD_TOO_LARGE"


_ERROR_MESSAGES = MappingProxyType(
    {
        ObservabilitySerializationErrorCode.INVALID_RECORD: (
            "invalid observability record"
        ),
        ObservabilitySerializationErrorCode.UNSUPPORTED_VALUE: (
            "unsupported observability value"
        ),
        ObservabilitySerializationErrorCode.NON_FINITE_VALUE: (
            "non-finite observability value"
        ),
        ObservabilitySerializationErrorCode.RECORD_TOO_LARGE: (
            "serialized observability record is too large"
        ),
    }
)


class ObservabilitySerializationError(ValueError):
    code: ObservabilitySerializationErrorCode
    channel: ObservationChannel

    def __init__(
        self,
        code: ObservabilitySerializationErrorCode,
        channel: ObservationChannel,
    ) -> None:
        if not isinstance(code, ObservabilitySerializationErrorCode):
            raise TypeError("code must be an ObservabilitySerializationErrorCode")
        if not isinstance(channel, ObservationChannel):
            raise TypeError("channel must be an ObservationChannel")
        self.code = code
        self.channel = channel
        super().__init__(_ERROR_MESSAGES[code])


@dataclass(frozen=True, slots=True)
class SerializedObservation:
    channel: ObservationChannel
    payload: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.channel, ObservationChannel):
            raise TypeError("channel must be an ObservationChannel")
        if type(self.payload) is not str or not self.payload.endswith("\n"):
            raise ValueError("payload must be one complete NDJSON record")
        if type(self.size_bytes) is not int:
            raise TypeError("size_bytes must be an integer")
        if self.size_bytes != len(self.payload.encode("utf-8")):
            raise ValueError("size_bytes must match the UTF-8 payload")
        if not 1 <= self.size_bytes <= MAX_SERIALIZED_RECORD_BYTES:
            raise ValueError("serialized observation size is outside bounds")


def serialize_log_record(record: StructuredLogRecord) -> SerializedObservation:
    channel = ObservationChannel.LOG
    if type(record) is not StructuredLogRecord:
        raise ObservabilitySerializationError(
            ObservabilitySerializationErrorCode.INVALID_RECORD,
            channel,
        )
    try:
        payload = {
            "type": channel.value,
            "schema_version": str(record.schema_version),
            "record_id": record.record_id,
            "occurred_at": _instant(record.occurred_at),
            "level": record.level.value,
            "code": record.code.value,
            "correlation_id": record.correlation_id.value,
            "run_id": record.run_id,
            "step_id": record.step_id,
            "trace_context": _trace_context(record.trace_context),
            "refs": [_safe_value(item) for item in record.refs],
            "attributes": _safe_value(record.attributes),
        }
        return _ndjson(channel, payload)
    except ObservabilitySerializationError:
        raise
    except Exception:
        raise ObservabilitySerializationError(
            ObservabilitySerializationErrorCode.UNSUPPORTED_VALUE,
            channel,
        ) from None


def serialize_span_record(record: SpanRecord) -> SerializedObservation:
    channel = ObservationChannel.SPAN
    if type(record) is not SpanRecord:
        raise ObservabilitySerializationError(
            ObservabilitySerializationErrorCode.INVALID_RECORD,
            channel,
        )
    try:
        payload = {
            "type": channel.value,
            "schema_version": str(record.schema_version),
            "trace_context": _trace_context(record.trace_context),
            "code": record.code.value,
            "kind": record.kind.value,
            "status": record.status.value,
            "started_at": _instant(record.started_at),
            "ended_at": _instant(record.ended_at),
            "correlation_id": record.correlation_id.value,
            "run_id": record.run_id,
            "step_id": record.step_id,
            "refs": [_safe_value(item) for item in record.refs],
            "attributes": _safe_value(record.attributes),
        }
        return _ndjson(channel, payload)
    except ObservabilitySerializationError:
        raise
    except Exception:
        raise ObservabilitySerializationError(
            ObservabilitySerializationErrorCode.UNSUPPORTED_VALUE,
            channel,
        ) from None


def serialize_metric_point(point: MetricPoint) -> SerializedObservation:
    channel = ObservationChannel.METRIC
    if type(point) is not MetricPoint:
        raise ObservabilitySerializationError(
            ObservabilitySerializationErrorCode.INVALID_RECORD,
            channel,
        )
    try:
        descriptor = point.descriptor
        payload = {
            "type": channel.value,
            "schema_version": str(descriptor.schema_version),
            "observed_at": _instant(point.observed_at),
            "name": descriptor.name.value,
            "kind": descriptor.kind.value,
            "unit": descriptor.unit.value,
            "description_code": descriptor.description_code.value,
            "value": _metric_value(point.value),
            "labels": {key: point.labels[key] for key in sorted(point.labels)},
            "trace_context": _trace_context(point.trace_context),
        }
        return _ndjson(channel, payload)
    except ObservabilitySerializationError:
        raise
    except Exception:
        raise ObservabilitySerializationError(
            ObservabilitySerializationErrorCode.UNSUPPORTED_VALUE,
            channel,
        ) from None


def _ndjson(
    channel: ObservationChannel,
    payload: Mapping[str, object],
) -> SerializedObservation:
    try:
        require_safe_structured_value(
            payload,
            root_location="serialized_observation",
        )
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
    except (TypeError, ValueError):
        raise ObservabilitySerializationError(
            ObservabilitySerializationErrorCode.UNSUPPORTED_VALUE,
            channel,
        ) from None
    size_bytes = len(serialized.encode("utf-8"))
    if size_bytes > MAX_SERIALIZED_RECORD_BYTES:
        raise ObservabilitySerializationError(
            ObservabilitySerializationErrorCode.RECORD_TOO_LARGE,
            channel,
        )
    return SerializedObservation(channel, serialized, size_bytes)


def _instant(value: Instant) -> str:
    return value.value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _trace_context(value: TraceContext | None) -> Mapping[str, object] | None:
    if value is None:
        return None
    return {
        "trace_id": value.trace_id.value,
        "span_id": value.span_id.value,
        "parent_span_id": (
            value.parent_span_id.value if value.parent_span_id is not None else None
        ),
        "sampling_decision": value.sampling_decision.value,
    }


def _metric_value(value: int | float | Decimal) -> Mapping[str, str]:
    if type(value) is int:
        return {"type": "integer", "value": str(value)}
    if type(value) is float:
        if not math.isfinite(value):
            raise ObservabilitySerializationError(
                ObservabilitySerializationErrorCode.NON_FINITE_VALUE,
                ObservationChannel.METRIC,
            )
        return {"type": "float", "value": format(value, ".17g")}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ObservabilitySerializationError(
                ObservabilitySerializationErrorCode.NON_FINITE_VALUE,
                ObservationChannel.METRIC,
            )
        return {"type": "decimal", "value": format(value, "f")}
    raise ObservabilitySerializationError(
        ObservabilitySerializationErrorCode.UNSUPPORTED_VALUE,
        ObservationChannel.METRIC,
    )


def _safe_value(value: object) -> object:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite safe value")
        return value
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise TypeError("safe mappings require string keys")
        return {key: _safe_value(value[key]) for key in sorted(value)}
    if type(value) is tuple:
        return [_safe_value(item) for item in value]
    if isinstance(value, CorrelationId):
        return {"type": "correlation_id", "value": value.value}
    if isinstance(value, TypedEntityId):
        return {
            "type": "typed_entity_id",
            "entity_type": value.entity_type,
            "value": value.value,
        }
    if isinstance(value, TypedEntityRef):
        return {"type": "typed_entity_ref", "entity_id": _safe_value(value.entity_id)}
    if isinstance(value, VersionRef):
        return {"type": "version_ref", "value": value.value}
    if isinstance(value, ObjectVersionRef):
        return {
            "type": "object_version_ref",
            "object_ref": _safe_value(value.object_ref),
            "version_ref": _safe_value(value.version_ref),
        }
    raise TypeError("unsupported safe observability value")
