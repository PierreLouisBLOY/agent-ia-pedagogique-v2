from __future__ import annotations

from backend.agent_runtime.contracts.common import AGENT_CONTRACT_SCHEMA_V1_0
from backend.agent_runtime.contracts.errors.error_envelope import ErrorEnvelope
from backend.agent_runtime.contracts.events.workflow_event import WorkflowEvent
from backend.agent_runtime.contracts.observability.log import StructuredLogRecord
from backend.agent_runtime.contracts.observability.trace import TraceContext
from backend.agent_runtime.contracts.security.security_event import SecurityEvent
from backend.agent_runtime.observability.log_catalog import (
    directive_log_level,
    directive_observation_code,
    error_log_level,
    error_observation_code,
    security_log_level,
    security_observation_code,
    workflow_log_level,
    workflow_observation_code,
)
from backend.agent_runtime.runtime.execution.directives import ExecutionDirective
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


def structured_log_from_workflow_event(
    source: WorkflowEvent,
    *,
    record_id: str,
    trace_context: TraceContext | None = None,
) -> StructuredLogRecord:
    """Map one lifecycle fact without copying summary, metrics or trace flags."""

    if not isinstance(source, WorkflowEvent):
        raise TypeError("source must be a WorkflowEvent")
    return StructuredLogRecord(
        schema_version=source.meta.schema_version,
        record_id=record_id,
        occurred_at=source.meta.created_at,
        level=workflow_log_level(source.meta.status),
        code=workflow_observation_code(source.event_type),
        correlation_id=source.meta.correlation_id,
        run_id=source.meta.run_id,
        step_id=source.meta.step_id,
        trace_context=trace_context,
        attributes={
            "event_type": source.event_type.value,
            "workflow_status": source.meta.status.value,
            "ref_count": len(source.refs),
        },
    )


def structured_log_from_security_event(
    source: SecurityEvent,
    *,
    record_id: str,
    trace_context: TraceContext | None = None,
) -> StructuredLogRecord:
    """Map one security fact without copying metadata or content lineage."""

    if not isinstance(source, SecurityEvent):
        raise TypeError("source must be a SecurityEvent")
    return StructuredLogRecord(
        schema_version=source.schema_version,
        record_id=record_id,
        occurred_at=source.occurred_at,
        level=security_log_level(source.severity),
        code=security_observation_code(source.event_type),
        correlation_id=source.correlation_id,
        run_id=source.run_id,
        step_id=source.step_id,
        trace_context=trace_context,
        attributes={
            "event_type": source.event_type.value,
            "severity": source.severity.value,
            "boundary": source.boundary.value,
            "reason_code": source.reason_code.value,
            "ref_count": len(source.refs),
        },
    )


def structured_log_from_error_envelope(
    source: ErrorEnvelope,
    *,
    correlation_id: CorrelationId,
    run_id: str,
    occurred_at: Instant,
    record_id: str,
    trace_context: TraceContext | None = None,
) -> StructuredLogRecord:
    """Map closed error facts while excluding message and details."""

    if not isinstance(source, ErrorEnvelope):
        raise TypeError("source must be an ErrorEnvelope")
    return StructuredLogRecord(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        record_id=record_id,
        occurred_at=occurred_at,
        level=error_log_level(source.severity),
        code=error_observation_code(),
        correlation_id=correlation_id,
        run_id=run_id,
        step_id=source.step_id,
        trace_context=trace_context,
        attributes={
            "error_code": source.error_code,
            "category": source.category.value,
            "source": source.source.value,
            "retryable": source.retryable,
            "severity": source.severity.value,
            "effect_state": source.effect_state.value,
            "recommended_action": source.recommended_action.value,
            "attempt": source.attempt,
            "related_ref_count": len(source.related_refs),
        },
    )


def structured_log_from_execution_directive(
    source: ExecutionDirective,
    *,
    correlation_id: CorrelationId,
    run_id: str,
    occurred_at: Instant,
    record_id: str,
    trace_context: TraceContext | None = None,
) -> StructuredLogRecord:
    """Map one runtime control fact without interpreting or executing it."""

    if not isinstance(source, ExecutionDirective):
        raise TypeError("source must be an ExecutionDirective")
    attributes: dict[str, object] = {"directive_code": source.code.value}
    if source.reason_code is not None:
        attributes["reason_code"] = source.reason_code
    return StructuredLogRecord(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        record_id=record_id,
        occurred_at=occurred_at,
        level=directive_log_level(source.code),
        code=directive_observation_code(source.code),
        correlation_id=correlation_id,
        run_id=run_id,
        step_id=source.step_id,
        trace_context=trace_context,
        attributes=attributes,
    )
