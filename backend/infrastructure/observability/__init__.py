"""Bounded provider-neutral observability delivery adapters."""

from backend.infrastructure.observability.buffering import (
    BoundedDeliveryBuffer,
    BufferEnqueueResult,
)
from backend.infrastructure.observability.local import (
    LOCAL_OBSERVABILITY_OPTION,
    MAX_LOG_FILE_COUNT,
    MAX_SHUTDOWN_FLUSH_SECONDS,
    OBSERVABILITY_LOG_RELATIVE_PATH,
    RETENTION_DAYS,
    ROTATION_SIZE_BYTES,
    LocalRotatingNdjsonWriter,
)
from backend.infrastructure.observability.operational import (
    FailureIsolatedOperationalEventSink,
    NullOperationalEventSink,
    OperationalComponent,
    OperationalEvent,
    OperationalEventCode,
    OperationalEventLevel,
    OperationalEventSinkPort,
    OperationalSinkHealth,
    serialize_operational_event,
    utc_now,
)
from backend.infrastructure.observability.providers import (
    UtcObservationClock,
    UuidObservationIdProvider,
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
    "FailureIsolatedOperationalEventSink",
    "LOCAL_OBSERVABILITY_OPTION",
    "LocalRotatingNdjsonWriter",
    "MAX_LOG_FILE_COUNT",
    "MAX_SHUTDOWN_FLUSH_SECONDS",
    "MAX_SERIALIZED_RECORD_BYTES",
    "ObservabilitySerializationError",
    "ObservabilitySerializationErrorCode",
    "OBSERVABILITY_LOG_RELATIVE_PATH",
    "NullOperationalEventSink",
    "OperationalComponent",
    "OperationalEvent",
    "OperationalEventCode",
    "OperationalEventLevel",
    "OperationalEventSinkPort",
    "OperationalSinkHealth",
    "RETENTION_DAYS",
    "ROTATION_SIZE_BYTES",
    "SerializedObservation",
    "StreamTextRecordWriter",
    "TextRecordWriter",
    "UtcObservationClock",
    "UuidObservationIdProvider",
    "serialize_log_record",
    "serialize_metric_point",
    "serialize_operational_event",
    "serialize_span_record",
    "utc_now",
]
