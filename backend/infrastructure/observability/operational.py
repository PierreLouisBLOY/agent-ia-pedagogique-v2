"""Closed, privacy-safe events for the minimum local observability surface."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Protocol, runtime_checkable

from backend.infrastructure.observability.writers import TextRecordWriter

MAX_OPERATIONAL_RECORD_BYTES: Final = 65_536
MAX_DROPPED_EVENT_COUNT: Final = 2_147_483_647

_SAFE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_ROUTE = re.compile(r"^/[A-Za-z0-9_{}./:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE_KEY_FRAGMENTS: Final = (
    "authorization_header",
    "body",
    "cookie",
    "credential",
    "environment",
    "exception_message",
    "header",
    "local_path",
    "password",
    "payload",
    "prompt",
    "query",
    "raw",
    "response",
    "secret",
    "stack",
    "token_value",
    "username",
)
_SENSITIVE_VALUE_PATTERNS: Final = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~-]+"),
    re.compile(r"(?i)\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}"),
    re.compile(r"^[A-Za-z]:[\\/]"),
    re.compile(r"^(?:\\\\|//)"),
    re.compile(r"^/(?:home|Users)/"),
)


class OperationalEventLevel(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class OperationalComponent(StrEnum):
    APPLICATION = "application"
    HTTP = "http"
    PROVIDER = "provider"
    SECURITY = "security"
    SQLITE = "sqlite"
    VALIDATION = "validation"


class OperationalEventCode(StrEnum):
    APP_STARTUP = "app.startup"
    APP_SHUTDOWN = "app.shutdown"
    APP_UNHANDLED_EXCEPTION = "app.unhandled_exception"
    HTTP_REQUEST_COMPLETED = "http.request.completed"
    HTTP_REQUEST_FAILED = "http.request.failed"
    HTTP_VALIDATION_REJECTED = "http.validation.rejected"
    SQLITE_BOOTSTRAP_STARTED = "sqlite.bootstrap.started"
    SQLITE_BOOTSTRAP_COMPLETED = "sqlite.bootstrap.completed"
    SQLITE_BOOTSTRAP_FAILED = "sqlite.bootstrap.failed"
    SQLITE_MIGRATION_STARTED = "sqlite.migration.started"
    SQLITE_MIGRATION_COMPLETED = "sqlite.migration.completed"
    SQLITE_MIGRATION_FAILED = "sqlite.migration.failed"
    SQLITE_BACKUP_COMPLETED = "sqlite.backup.completed"
    SQLITE_BACKUP_FAILED = "sqlite.backup.failed"
    SQLITE_RECOVERY_COMPLETED = "sqlite.recovery.completed"
    SQLITE_RECOVERY_FAILED = "sqlite.recovery.failed"
    PROVIDER_CALL_STARTED = "provider.call.started"
    PROVIDER_CALL_COMPLETED = "provider.call.completed"
    PROVIDER_CALL_FAILED = "provider.call.failed"
    SECURITY_PATH_REJECTED = "security.path.rejected"
    SECURITY_RUNTIME_BOUNDARY_REJECTED = "security.runtime_boundary.rejected"


type OperationalFieldValue = str | int | float | bool


@dataclass(frozen=True, slots=True)
class _EventSpec:
    component: OperationalComponent
    levels: frozenset[OperationalEventLevel]
    required: frozenset[str]
    optional: frozenset[str] = frozenset()


_INFO = frozenset({OperationalEventLevel.INFO})
_WARNING = frozenset({OperationalEventLevel.WARNING})
_ERROR = frozenset({OperationalEventLevel.ERROR})
_INFO_ERROR = frozenset({OperationalEventLevel.INFO, OperationalEventLevel.ERROR})

_EVENT_SPECS: Final = MappingProxyType(
    {
        OperationalEventCode.APP_STARTUP: _EventSpec(
            OperationalComponent.APPLICATION,
            _INFO_ERROR,
            frozenset({"app_version", "config_profile_id", "sink_health", "runtime_mode", "outcome"}),
            frozenset({"closed_error_code"}),
        ),
        OperationalEventCode.APP_SHUTDOWN: _EventSpec(
            OperationalComponent.APPLICATION,
            frozenset({OperationalEventLevel.INFO, OperationalEventLevel.WARNING}),
            frozenset({"flush_outcome", "dropped_event_count", "duration_ms", "outcome"}),
        ),
        OperationalEventCode.APP_UNHANDLED_EXCEPTION: _EventSpec(
            OperationalComponent.APPLICATION,
            _ERROR,
            frozenset({"boundary", "exception_class_code", "shutdown_required", "outcome"}),
            frozenset({"correlation_id"}),
        ),
        OperationalEventCode.HTTP_REQUEST_COMPLETED: _EventSpec(
            OperationalComponent.HTTP,
            _INFO,
            frozenset({"method", "route_template", "status_class", "duration_ms", "correlation_id", "outcome"}),
        ),
        OperationalEventCode.HTTP_REQUEST_FAILED: _EventSpec(
            OperationalComponent.HTTP,
            frozenset({OperationalEventLevel.WARNING, OperationalEventLevel.ERROR}),
            frozenset({"method", "route_template", "status_class", "duration_ms", "correlation_id", "outcome"}),
            frozenset({"closed_error_code"}),
        ),
        OperationalEventCode.HTTP_VALIDATION_REJECTED: _EventSpec(
            OperationalComponent.VALIDATION,
            _WARNING,
            frozenset({"boundary", "rule_code", "field_code", "correlation_id", "outcome"}),
        ),
        OperationalEventCode.SQLITE_BOOTSTRAP_STARTED: _EventSpec(
            OperationalComponent.SQLITE,
            _INFO,
            frozenset({"schema_version", "outcome"}),
        ),
        OperationalEventCode.SQLITE_BOOTSTRAP_COMPLETED: _EventSpec(
            OperationalComponent.SQLITE,
            _INFO,
            frozenset({"schema_version", "seed_identity_digest", "runtime_identity_digest", "outcome"}),
        ),
        OperationalEventCode.SQLITE_BOOTSTRAP_FAILED: _EventSpec(
            OperationalComponent.SQLITE,
            _ERROR,
            frozenset({"schema_version", "outcome", "closed_error_code"}),
        ),
        OperationalEventCode.SQLITE_MIGRATION_STARTED: _EventSpec(
            OperationalComponent.SQLITE,
            _INFO,
            frozenset({"from_version", "to_version", "migration_id", "migration_checksum", "outcome"}),
        ),
        OperationalEventCode.SQLITE_MIGRATION_COMPLETED: _EventSpec(
            OperationalComponent.SQLITE,
            _INFO,
            frozenset({"from_version", "to_version", "migration_id", "migration_checksum", "outcome"}),
        ),
        OperationalEventCode.SQLITE_MIGRATION_FAILED: _EventSpec(
            OperationalComponent.SQLITE,
            _ERROR,
            frozenset({"from_version", "to_version", "migration_id", "migration_checksum", "outcome", "closed_error_code"}),
        ),
        OperationalEventCode.SQLITE_BACKUP_COMPLETED: _EventSpec(
            OperationalComponent.SQLITE,
            _INFO,
            frozenset({"operation", "artifact_digest", "authentication_outcome", "outcome"}),
        ),
        OperationalEventCode.SQLITE_BACKUP_FAILED: _EventSpec(
            OperationalComponent.SQLITE,
            _ERROR,
            frozenset({"operation", "authentication_outcome", "outcome", "closed_error_code"}),
        ),
        OperationalEventCode.SQLITE_RECOVERY_COMPLETED: _EventSpec(
            OperationalComponent.SQLITE,
            _INFO,
            frozenset({"operation", "artifact_digest", "authentication_outcome", "outcome"}),
        ),
        OperationalEventCode.SQLITE_RECOVERY_FAILED: _EventSpec(
            OperationalComponent.SQLITE,
            _ERROR,
            frozenset({"operation", "authentication_outcome", "outcome", "closed_error_code"}),
        ),
        OperationalEventCode.PROVIDER_CALL_STARTED: _EventSpec(
            OperationalComponent.PROVIDER,
            _INFO,
            frozenset({"provider_id", "model_profile_id", "call_id", "authorization_id", "attempt_number", "outcome"}),
        ),
        OperationalEventCode.PROVIDER_CALL_COMPLETED: _EventSpec(
            OperationalComponent.PROVIDER,
            _INFO,
            frozenset({"provider_id", "call_id", "input_tokens", "output_tokens", "cost_usd", "duration_ms", "outcome"}),
            frozenset({"cached_input_tokens"}),
        ),
        OperationalEventCode.PROVIDER_CALL_FAILED: _EventSpec(
            OperationalComponent.PROVIDER,
            _ERROR,
            frozenset({"provider_id", "call_id", "provider_error_code", "duration_ms", "authorization_consumed", "outcome"}),
        ),
        OperationalEventCode.SECURITY_PATH_REJECTED: _EventSpec(
            OperationalComponent.SECURITY,
            _WARNING,
            frozenset({"boundary", "policy_code", "outcome"}),
            frozenset({"correlation_id"}),
        ),
        OperationalEventCode.SECURITY_RUNTIME_BOUNDARY_REJECTED: _EventSpec(
            OperationalComponent.SECURITY,
            _WARNING,
            frozenset({"boundary", "policy_code", "outcome"}),
            frozenset({"correlation_id"}),
        ),
    }
)


@dataclass(frozen=True, slots=True)
class OperationalEvent:
    timestamp_utc: datetime
    level: OperationalEventLevel
    event_code: OperationalEventCode
    fields: Mapping[str, OperationalFieldValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        offset = (
            self.timestamp_utc.utcoffset()
            if type(self.timestamp_utc) is datetime
            else None
        )
        if (
            type(self.timestamp_utc) is not datetime
            or self.timestamp_utc.tzinfo is None
            or offset is None
            or offset.total_seconds() != 0
        ):
            raise ValueError("timestamp_utc must be timezone-aware UTC")
        if not isinstance(self.level, OperationalEventLevel):
            raise TypeError("level must be an OperationalEventLevel")
        if not isinstance(self.event_code, OperationalEventCode):
            raise TypeError("event_code must be an OperationalEventCode")
        if not isinstance(self.fields, Mapping):
            raise TypeError("fields must be a mapping")
        spec = _EVENT_SPECS[self.event_code]
        if self.level not in spec.levels:
            raise ValueError("level is not allowed for this event")
        values = dict(self.fields)
        keys = frozenset(values)
        if not spec.required <= keys or not keys <= spec.required | spec.optional:
            raise ValueError("event fields do not match the closed schema")
        for key, value in values.items():
            _require_safe_field(key, value)
        object.__setattr__(self, "fields", MappingProxyType(values))

    @property
    def component(self) -> OperationalComponent:
        return _EVENT_SPECS[self.event_code].component


@dataclass(frozen=True, slots=True)
class OperationalSinkHealth:
    healthy: bool
    delivered_event_count: int
    dropped_event_count: int


@runtime_checkable
class OperationalEventSinkPort(Protocol):
    def emit(self, event: OperationalEvent) -> None: ...


class NullOperationalEventSink:
    def emit(self, event: OperationalEvent) -> None:
        del event


class FailureIsolatedOperationalEventSink:
    """Persist closed events without allowing sink failure to escape."""

    def __init__(self, writer: TextRecordWriter) -> None:
        if not isinstance(writer, TextRecordWriter):
            raise TypeError("writer must implement TextRecordWriter")
        self._writer = writer
        self._delivered = 0
        self._dropped = 0

    def emit(self, event: OperationalEvent) -> None:
        try:
            serialized = serialize_operational_event(event)
            written = self._writer.write(serialized)
            if type(written) is not int or written != len(serialized):
                raise ValueError("writer did not accept the complete record")
        except Exception:
            self._dropped = min(MAX_DROPPED_EVENT_COUNT, self._dropped + 1)
            return
        self._delivered += 1

    def flush(self) -> bool:
        flush = getattr(self._writer, "flush", None)
        if flush is None:
            return True
        try:
            flush()
        except Exception:
            self._dropped = min(MAX_DROPPED_EVENT_COUNT, self._dropped + 1)
            return False
        return True

    def close(self) -> bool:
        close = getattr(self._writer, "close", None)
        if close is None:
            return True
        try:
            close()
        except Exception:
            self._dropped = min(MAX_DROPPED_EVENT_COUNT, self._dropped + 1)
            return False
        return True

    def health_snapshot(self) -> OperationalSinkHealth:
        return OperationalSinkHealth(
            healthy=self._dropped == 0,
            delivered_event_count=self._delivered,
            dropped_event_count=self._dropped,
        )


def serialize_operational_event(event: OperationalEvent) -> str:
    if type(event) is not OperationalEvent:
        raise TypeError("event must be an OperationalEvent")
    payload: dict[str, OperationalFieldValue] = {
        "ts": event.timestamp_utc.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "level": event.level.value,
        "event": event.event_code.value,
        "component": event.component.value,
        "message": event.event_code.value,
    }
    payload.update(event.fields)
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"
    if len(serialized.encode("utf-8")) > MAX_OPERATIONAL_RECORD_BYTES:
        raise ValueError("operational event exceeds the record bound")
    return serialized


def utc_now() -> datetime:
    return datetime.now(UTC)


def _require_safe_field(key: str, value: OperationalFieldValue) -> None:
    if type(key) is not str or _SAFE_CODE.fullmatch(key) is None:
        raise ValueError("event field names must be bounded codes")
    folded_key = key.casefold()
    if any(fragment in folded_key for fragment in _SENSITIVE_KEY_FRAGMENTS):
        raise ValueError("sensitive event field is forbidden")
    if type(value) is bool:
        return
    if type(value) is int:
        if not 0 <= value <= 10**12:
            raise ValueError("integer event field is outside bounds")
        if key == "attempt_number" and value != 1:
            raise ValueError("provider attempt number must remain one")
        return
    if type(value) is float:
        if not math.isfinite(value) or not 0 <= value <= 10**12:
            raise ValueError("float event field is outside bounds")
        return
    if type(value) is not str or not value or len(value.encode("utf-8")) > 256:
        raise ValueError("string event field is outside bounds")
    if "\n" in value or "\r" in value or any(
        pattern.search(value) is not None for pattern in _SENSITIVE_VALUE_PATTERNS
    ):
        raise ValueError("sensitive or multiline event value is forbidden")
    if key == "route_template":
        if _SAFE_ROUTE.fullmatch(value) is None or ".." in value:
            raise ValueError("route_template must be a bounded template")
        return
    if key.endswith(("_digest", "_checksum")):
        if _SHA256.fullmatch(value) is None:
            raise ValueError("digest fields require lowercase SHA-256")
        return
    if _SAFE_CODE.fullmatch(value) is None:
        raise ValueError("string event values must be bounded opaque codes")
