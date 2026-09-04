"""Explicit composition and lifecycle wiring for local OBS-A observability."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Final
from uuid import uuid4

from backend.infrastructure.observability import (
    MAX_SHUTDOWN_FLUSH_SECONDS,
    FailureIsolatedOperationalEventSink,
    LocalRotatingNdjsonWriter,
    OperationalEvent,
    OperationalEventCode,
    OperationalEventLevel,
    OperationalSinkHealth,
    utc_now,
)

MINIMUM_OBSERVABILITY_SIGNAL_COUNT: Final = 12
_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class LocalObservabilitySession:
    """Own one injected sink and expose only closed operational event methods."""

    def __init__(
        self,
        sink: FailureIsolatedOperationalEventSink,
        *,
        clock: Callable[[], datetime] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        correlation_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if type(sink) is not FailureIsolatedOperationalEventSink:
            raise TypeError("sink must be a FailureIsolatedOperationalEventSink")
        self._sink = sink
        self._clock = clock
        self._monotonic = monotonic
        self._correlation_id_factory = correlation_id_factory or _new_correlation_id

    def startup(
        self,
        *,
        app_version: str,
        config_profile_id: str,
        runtime_mode: str,
    ) -> None:
        health = self._sink.health_snapshot()
        self._emit(
            OperationalEventCode.APP_STARTUP,
            OperationalEventLevel.INFO if health.healthy else OperationalEventLevel.ERROR,
            app_version=app_version,
            config_profile_id=config_profile_id,
            sink_health="HEALTHY" if health.healthy else "DEGRADED",
            runtime_mode=runtime_mode,
            outcome="SUCCEEDED" if health.healthy else "FAILED",
            **({} if health.healthy else {"closed_error_code": "SINK_DEGRADED"}),
        )

    def shutdown(self) -> float:
        started = self._monotonic()
        flush_ok = self._sink.flush()
        elapsed = max(0.0, self._monotonic() - started)
        bounded_ms = min(int(elapsed * 1_000), 10**12)
        health = self._sink.health_snapshot()
        within_deadline = elapsed <= MAX_SHUTDOWN_FLUSH_SECONDS
        success = flush_ok and within_deadline
        self._emit(
            OperationalEventCode.APP_SHUTDOWN,
            OperationalEventLevel.INFO if success else OperationalEventLevel.WARNING,
            flush_outcome="SUCCEEDED" if success else "FAILED",
            dropped_event_count=health.dropped_event_count,
            duration_ms=bounded_ms,
            outcome="SUCCEEDED" if success else "DEGRADED",
        )
        self._sink.flush()
        self._sink.close()
        return elapsed

    def unhandled_exception(
        self,
        error: BaseException,
        *,
        boundary: str,
        correlation_id: str | None = None,
    ) -> None:
        if not isinstance(error, BaseException):
            raise TypeError("error must be a BaseException")
        fields: dict[str, str | int | float | bool] = {
            "boundary": boundary,
            "exception_class_code": type(error).__name__,
            "shutdown_required": True,
            "outcome": "FAILED",
        }
        if correlation_id is not None:
            fields["correlation_id"] = self.correlation_id(correlation_id)
        self._emit(
            OperationalEventCode.APP_UNHANDLED_EXCEPTION,
            OperationalEventLevel.ERROR,
            **fields,
        )

    def correlation_id(self, incoming: str | None) -> str:
        if type(incoming) is str and _CORRELATION_ID.fullmatch(incoming) is not None:
            return incoming
        generated = self._correlation_id_factory()
        if type(generated) is not str or _CORRELATION_ID.fullmatch(generated) is None:
            raise ValueError("correlation id factory returned an invalid identifier")
        return generated

    def http_request(
        self,
        *,
        method: str,
        route_template: str,
        status_code: int,
        duration_ms: int,
        incoming_correlation_id: str | None,
    ) -> str:
        correlation_id = self.correlation_id(incoming_correlation_id)
        if type(status_code) is not int or not 100 <= status_code <= 599:
            raise ValueError("status_code must be between 100 and 599")
        status_class = f"{status_code // 100}xx"
        success = status_code < 400
        self._emit(
            OperationalEventCode.HTTP_REQUEST_COMPLETED if success else OperationalEventCode.HTTP_REQUEST_FAILED,
            OperationalEventLevel.INFO
            if success
            else OperationalEventLevel.ERROR
            if status_code >= 500
            else OperationalEventLevel.WARNING,
            method=method.upper(),
            route_template=route_template,
            status_class=status_class,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            outcome="SUCCEEDED" if success else "FAILED",
        )
        return correlation_id

    def validation_rejected(
        self,
        *,
        boundary: str,
        rule_code: str,
        field_code: str,
        correlation_id: str,
    ) -> None:
        self._emit(
            OperationalEventCode.HTTP_VALIDATION_REJECTED,
            OperationalEventLevel.WARNING,
            boundary=boundary,
            rule_code=rule_code,
            field_code=field_code,
            correlation_id=self.correlation_id(correlation_id),
            outcome="REJECTED",
        )

    def sqlite_bootstrap_started(self, *, schema_version: str) -> None:
        self._emit(
            OperationalEventCode.SQLITE_BOOTSTRAP_STARTED,
            OperationalEventLevel.INFO,
            schema_version=schema_version,
            outcome="STARTED",
        )

    def sqlite_bootstrap_completed(
        self,
        *,
        schema_version: str,
        seed_identity_digest: str,
        runtime_identity_digest: str,
    ) -> None:
        self._emit(
            OperationalEventCode.SQLITE_BOOTSTRAP_COMPLETED,
            OperationalEventLevel.INFO,
            schema_version=schema_version,
            seed_identity_digest=seed_identity_digest,
            runtime_identity_digest=runtime_identity_digest,
            outcome="SUCCEEDED",
        )

    def sqlite_bootstrap_failed(
        self, *, schema_version: str, closed_error_code: str
    ) -> None:
        self._emit(
            OperationalEventCode.SQLITE_BOOTSTRAP_FAILED,
            OperationalEventLevel.ERROR,
            schema_version=schema_version,
            outcome="FAILED",
            closed_error_code=closed_error_code,
        )

    def sqlite_migration(
        self,
        *,
        started: bool,
        succeeded: bool,
        from_version: str,
        to_version: str,
        migration_id: str,
        migration_checksum: str,
        closed_error_code: str | None = None,
    ) -> None:
        if started:
            code = OperationalEventCode.SQLITE_MIGRATION_STARTED
            level = OperationalEventLevel.INFO
            outcome = "STARTED"
        elif succeeded:
            code = OperationalEventCode.SQLITE_MIGRATION_COMPLETED
            level = OperationalEventLevel.INFO
            outcome = "SUCCEEDED"
        else:
            code = OperationalEventCode.SQLITE_MIGRATION_FAILED
            level = OperationalEventLevel.ERROR
            outcome = "FAILED"
        fields: dict[str, str | int | float | bool] = {
            "from_version": from_version,
            "to_version": to_version,
            "migration_id": migration_id,
            "migration_checksum": migration_checksum,
            "outcome": outcome,
        }
        if code is OperationalEventCode.SQLITE_MIGRATION_FAILED:
            if closed_error_code is None:
                raise ValueError("failed migration requires a closed error code")
            fields["closed_error_code"] = closed_error_code
        self._emit(code, level, **fields)

    def sqlite_artifact_operation(
        self,
        *,
        recovery: bool,
        succeeded: bool,
        artifact_digest: str | None = None,
        closed_error_code: str | None = None,
    ) -> None:
        if recovery:
            code = (
                OperationalEventCode.SQLITE_RECOVERY_COMPLETED
                if succeeded
                else OperationalEventCode.SQLITE_RECOVERY_FAILED
            )
            operation = "RESTORE"
        else:
            code = (
                OperationalEventCode.SQLITE_BACKUP_COMPLETED
                if succeeded
                else OperationalEventCode.SQLITE_BACKUP_FAILED
            )
            operation = "BACKUP"
        fields: dict[str, str | int | float | bool] = {
            "operation": operation,
            "authentication_outcome": "VERIFIED" if succeeded else "FAILED",
            "outcome": "SUCCEEDED" if succeeded else "FAILED",
        }
        if succeeded:
            if artifact_digest is None:
                raise ValueError("successful operation requires an artifact digest")
            fields["artifact_digest"] = artifact_digest
        else:
            if closed_error_code is None:
                raise ValueError("failed operation requires a closed error code")
            fields["closed_error_code"] = closed_error_code
        self._emit(code, OperationalEventLevel.INFO if succeeded else OperationalEventLevel.ERROR, **fields)

    def provider_call(
        self,
        *,
        state: str,
        provider_id: str,
        call_id: str,
        model_profile_id: str | None = None,
        authorization_id: str | None = None,
        input_tokens: int | None = None,
        cached_input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: str | None = None,
        duration_ms: int = 0,
        provider_error_code: str | None = None,
        authorization_consumed: bool | None = None,
    ) -> None:
        if state == "STARTED":
            if model_profile_id is None or authorization_id is None:
                raise ValueError("provider start requires model and authorization ids")
            self._emit(
                OperationalEventCode.PROVIDER_CALL_STARTED,
                OperationalEventLevel.INFO,
                provider_id=provider_id,
                model_profile_id=model_profile_id,
                call_id=call_id,
                authorization_id=authorization_id,
                attempt_number=1,
                outcome="STARTED",
            )
            return
        if state == "COMPLETED":
            if input_tokens is None or output_tokens is None or cost_usd is None:
                raise ValueError("provider completion requires bounded usage and cost")
            fields: dict[str, str | int | float | bool] = {
                "provider_id": provider_id,
                "call_id": call_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "duration_ms": duration_ms,
                "outcome": "SUCCEEDED",
            }
            if cached_input_tokens is not None:
                fields["cached_input_tokens"] = cached_input_tokens
            self._emit(
                OperationalEventCode.PROVIDER_CALL_COMPLETED,
                OperationalEventLevel.INFO,
                **fields,
            )
            return
        if state != "FAILED" or provider_error_code is None or authorization_consumed is None:
            raise ValueError("provider state or failure fields are invalid")
        self._emit(
            OperationalEventCode.PROVIDER_CALL_FAILED,
            OperationalEventLevel.ERROR,
            provider_id=provider_id,
            call_id=call_id,
            provider_error_code=provider_error_code,
            duration_ms=duration_ms,
            authorization_consumed=authorization_consumed,
            outcome="FAILED",
        )

    def security_rejected(
        self,
        *,
        runtime_boundary: bool,
        boundary: str,
        policy_code: str,
        correlation_id: str | None = None,
    ) -> None:
        fields: dict[str, str | int | float | bool] = {
            "boundary": boundary,
            "policy_code": policy_code,
            "outcome": "REJECTED",
        }
        if correlation_id is not None:
            fields["correlation_id"] = self.correlation_id(correlation_id)
        self._emit(
            OperationalEventCode.SECURITY_RUNTIME_BOUNDARY_REJECTED
            if runtime_boundary
            else OperationalEventCode.SECURITY_PATH_REJECTED,
            OperationalEventLevel.WARNING,
            **fields,
        )

    def health_snapshot(self) -> OperationalSinkHealth:
        return self._sink.health_snapshot()

    def _emit(
        self,
        code: OperationalEventCode,
        level: OperationalEventLevel,
        **fields: str | int | float | bool,
    ) -> None:
        self._sink.emit(OperationalEvent(self._clock(), level, code, fields))


def build_local_observability_session(
    data_root: Path,
    *,
    clock: Callable[[], datetime] = utc_now,
    monotonic: Callable[[], float] = time.monotonic,
    correlation_id_factory: Callable[[], str] | None = None,
) -> LocalObservabilitySession:
    writer = LocalRotatingNdjsonWriter(data_root, clock=clock)
    sink = FailureIsolatedOperationalEventSink(writer)
    return LocalObservabilitySession(
        sink,
        clock=clock,
        monotonic=monotonic,
        correlation_id_factory=correlation_id_factory,
    )


def _new_correlation_id() -> str:
    return f"corr-{uuid4().hex}"
