"""Bounded provider-neutral observability delivery adapters."""

from backend.infrastructure.observability.buffering import (
    BoundedDeliveryBuffer,
    BufferEnqueueResult,
)
from backend.infrastructure.observability.serialization import (
    MAX_SERIALIZED_RECORD_BYTES,
    ObservabilitySerializationError,
    ObservabilitySerializationErrorCode,
    SerializedObservation,
    serialize_log_record,
    serialize_metric_point,
    serialize_span_record,
)
from backend.infrastructure.observability.sinks import (
    FailureIsolatedLogSink,
    FailureIsolatedMetricSink,
    FailureIsolatedTraceSink,
)
from backend.infrastructure.observability.writers import (
    StreamTextRecordWriter,
    TextRecordWriter,
)

__all__ = [
    "BoundedDeliveryBuffer",
    "BufferEnqueueResult",
    "FailureIsolatedLogSink",
    "FailureIsolatedMetricSink",
    "FailureIsolatedTraceSink",
    "MAX_SERIALIZED_RECORD_BYTES",
    "ObservabilitySerializationError",
    "ObservabilitySerializationErrorCode",
    "SerializedObservation",
    "StreamTextRecordWriter",
    "TextRecordWriter",
    "serialize_log_record",
    "serialize_metric_point",
    "serialize_span_record",
]
