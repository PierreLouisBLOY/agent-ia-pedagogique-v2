from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.contracts.errors.error_envelope import ErrorSeverity
from backend.agent_runtime.contracts.events.workflow_event import (
    WorkflowEventType,
    WorkflowStatus,
)
from backend.agent_runtime.contracts.observability.log import (
    LogLevel,
    ObservationCode,
)
from backend.agent_runtime.contracts.security.security_event import (
    SecurityEventType,
    SecuritySeverity,
)
from backend.agent_runtime.runtime.execution.directives import ExecutionDirectiveCode


class StructuredLogCode(StrEnum):
    """Closed catalog of source facts mapped during Phase 12.13-C."""

    WORKFLOW_PLANNED = "WORKFLOW.PLANNED"
    WORKFLOW_ROUTED = "WORKFLOW.ROUTED"
    WORKFLOW_DELEGATED = "WORKFLOW.DELEGATED"
    WORKFLOW_TOOL_CALLED = "WORKFLOW.TOOL_CALLED"
    WORKFLOW_USECASE_CALLED = "WORKFLOW.USECASE_CALLED"
    WORKFLOW_REVIEWED = "WORKFLOW.REVIEWED"
    WORKFLOW_CORRECTED = "WORKFLOW.CORRECTED"
    WORKFLOW_GATED = "WORKFLOW.GATED"
    WORKFLOW_STOPPED = "WORKFLOW.STOPPED"

    SECURITY_DIRECT_PROMPT_INJECTION = "SECURITY.DIRECT_PROMPT_INJECTION"
    SECURITY_INDIRECT_CONTENT_INJECTION = "SECURITY.INDIRECT_CONTENT_INJECTION"
    SECURITY_TOOL_INJECTION = "SECURITY.TOOL_INJECTION"
    SECURITY_APPLICATION_INJECTION = "SECURITY.APPLICATION_INJECTION"
    SECURITY_AGENT_HANDOFF_VIOLATION = "SECURITY.AGENT_HANDOFF_VIOLATION"
    SECURITY_AUTHORITY_SMUGGLING = "SECURITY.AUTHORITY_SMUGGLING"
    SECURITY_SECRET_EXFILTRATION_ATTEMPT = (
        "SECURITY.SECRET_EXFILTRATION_ATTEMPT"
    )
    SECURITY_SECRET_EXPOSURE = "SECURITY.SECRET_EXPOSURE"
    SECURITY_HOSTILE_CONTENT_PROPAGATION = (
        "SECURITY.HOSTILE_CONTENT_PROPAGATION"
    )
    SECURITY_TRUST_BOUNDARY_VIOLATION = "SECURITY.TRUST_BOUNDARY_VIOLATION"
    SECURITY_INPUT_LIMIT_EXCEEDED = "SECURITY.INPUT_LIMIT_EXCEEDED"

    ERROR_ENVELOPE = "ERROR.ENVELOPE"

    RUNTIME_CONTINUE = "RUNTIME.CONTINUE"
    RUNTIME_WAITING_GATE = "RUNTIME.WAITING_GATE"
    RUNTIME_CONDITION_REQUIRED = "RUNTIME.CONDITION_REQUIRED"
    RUNTIME_PRELAUNCH_DENIED = "RUNTIME.PRELAUNCH_DENIED"
    RUNTIME_RETRY_REQUIRED = "RUNTIME.RETRY_REQUIRED"
    RUNTIME_REPLAN_REQUIRED = "RUNTIME.REPLAN_REQUIRED"
    RUNTIME_ESCALATED = "RUNTIME.ESCALATED"
    RUNTIME_STOPPED = "RUNTIME.STOPPED"
    RUNTIME_PARTIAL_REQUIRES_DECISION = "RUNTIME.PARTIAL_REQUIRES_DECISION"
    RUNTIME_RECONCILIATION_REQUIRED = "RUNTIME.RECONCILIATION_REQUIRED"
    RUNTIME_READY_DEADLINE_EXPIRED = "RUNTIME.READY_DEADLINE_EXPIRED"
    RUNTIME_RUN_DEADLINE_EXCEEDED = "RUNTIME.RUN_DEADLINE_EXCEEDED"


_WORKFLOW_CODES: Final = MappingProxyType(
    {
        WorkflowEventType.PLANNED: StructuredLogCode.WORKFLOW_PLANNED,
        WorkflowEventType.ROUTED: StructuredLogCode.WORKFLOW_ROUTED,
        WorkflowEventType.DELEGATED: StructuredLogCode.WORKFLOW_DELEGATED,
        WorkflowEventType.TOOL_CALLED: StructuredLogCode.WORKFLOW_TOOL_CALLED,
        WorkflowEventType.USECASE_CALLED: StructuredLogCode.WORKFLOW_USECASE_CALLED,
        WorkflowEventType.REVIEWED: StructuredLogCode.WORKFLOW_REVIEWED,
        WorkflowEventType.CORRECTED: StructuredLogCode.WORKFLOW_CORRECTED,
        WorkflowEventType.GATED: StructuredLogCode.WORKFLOW_GATED,
        WorkflowEventType.STOPPED: StructuredLogCode.WORKFLOW_STOPPED,
    }
)
_SECURITY_CODES: Final = MappingProxyType(
    {
        SecurityEventType.DIRECT_PROMPT_INJECTION: (
            StructuredLogCode.SECURITY_DIRECT_PROMPT_INJECTION
        ),
        SecurityEventType.INDIRECT_CONTENT_INJECTION: (
            StructuredLogCode.SECURITY_INDIRECT_CONTENT_INJECTION
        ),
        SecurityEventType.TOOL_INJECTION: StructuredLogCode.SECURITY_TOOL_INJECTION,
        SecurityEventType.APPLICATION_INJECTION: (
            StructuredLogCode.SECURITY_APPLICATION_INJECTION
        ),
        SecurityEventType.AGENT_HANDOFF_VIOLATION: (
            StructuredLogCode.SECURITY_AGENT_HANDOFF_VIOLATION
        ),
        SecurityEventType.AUTHORITY_SMUGGLING: (
            StructuredLogCode.SECURITY_AUTHORITY_SMUGGLING
        ),
        SecurityEventType.SECRET_EXFILTRATION_ATTEMPT: (
            StructuredLogCode.SECURITY_SECRET_EXFILTRATION_ATTEMPT
        ),
        SecurityEventType.SECRET_EXPOSURE: (
            StructuredLogCode.SECURITY_SECRET_EXPOSURE
        ),
        SecurityEventType.HOSTILE_CONTENT_PROPAGATION: (
            StructuredLogCode.SECURITY_HOSTILE_CONTENT_PROPAGATION
        ),
        SecurityEventType.TRUST_BOUNDARY_VIOLATION: (
            StructuredLogCode.SECURITY_TRUST_BOUNDARY_VIOLATION
        ),
        SecurityEventType.INPUT_LIMIT_EXCEEDED: (
            StructuredLogCode.SECURITY_INPUT_LIMIT_EXCEEDED
        ),
    }
)
_DIRECTIVE_CODES: Final = MappingProxyType(
    {
        ExecutionDirectiveCode.CONTINUE: StructuredLogCode.RUNTIME_CONTINUE,
        ExecutionDirectiveCode.WAITING_GATE: StructuredLogCode.RUNTIME_WAITING_GATE,
        ExecutionDirectiveCode.CONDITION_REQUIRED: (
            StructuredLogCode.RUNTIME_CONDITION_REQUIRED
        ),
        ExecutionDirectiveCode.PRELAUNCH_DENIED: (
            StructuredLogCode.RUNTIME_PRELAUNCH_DENIED
        ),
        ExecutionDirectiveCode.RETRY_REQUIRED: (
            StructuredLogCode.RUNTIME_RETRY_REQUIRED
        ),
        ExecutionDirectiveCode.REPLAN_REQUIRED: (
            StructuredLogCode.RUNTIME_REPLAN_REQUIRED
        ),
        ExecutionDirectiveCode.ESCALATED: StructuredLogCode.RUNTIME_ESCALATED,
        ExecutionDirectiveCode.STOPPED: StructuredLogCode.RUNTIME_STOPPED,
        ExecutionDirectiveCode.PARTIAL_REQUIRES_DECISION: (
            StructuredLogCode.RUNTIME_PARTIAL_REQUIRES_DECISION
        ),
        ExecutionDirectiveCode.RECONCILIATION_REQUIRED: (
            StructuredLogCode.RUNTIME_RECONCILIATION_REQUIRED
        ),
        ExecutionDirectiveCode.READY_DEADLINE_EXPIRED: (
            StructuredLogCode.RUNTIME_READY_DEADLINE_EXPIRED
        ),
        ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED: (
            StructuredLogCode.RUNTIME_RUN_DEADLINE_EXCEEDED
        ),
    }
)

_WORKFLOW_LEVELS: Final = MappingProxyType(
    {
        WorkflowStatus.PLANNED: LogLevel.INFO,
        WorkflowStatus.RUNNING: LogLevel.INFO,
        WorkflowStatus.WAITING_GATE: LogLevel.INFO,
        WorkflowStatus.REPLANNING: LogLevel.WARNING,
        WorkflowStatus.SUCCEEDED: LogLevel.INFO,
        WorkflowStatus.PARTIAL: LogLevel.WARNING,
        WorkflowStatus.FAILED: LogLevel.ERROR,
        WorkflowStatus.CANCELLED: LogLevel.WARNING,
        WorkflowStatus.ESCALATED: LogLevel.WARNING,
    }
)
_SECURITY_LEVELS: Final = MappingProxyType(
    {
        SecuritySeverity.LOW: LogLevel.INFO,
        SecuritySeverity.MEDIUM: LogLevel.WARNING,
        SecuritySeverity.HIGH: LogLevel.ERROR,
        SecuritySeverity.CRITICAL: LogLevel.CRITICAL,
    }
)
_ERROR_LEVELS: Final = MappingProxyType(
    {
        ErrorSeverity.INFO: LogLevel.INFO,
        ErrorSeverity.WARNING: LogLevel.WARNING,
        ErrorSeverity.ERROR: LogLevel.ERROR,
        ErrorSeverity.CRITICAL: LogLevel.CRITICAL,
    }
)
_DIRECTIVE_LEVELS: Final = MappingProxyType(
    {
        ExecutionDirectiveCode.CONTINUE: LogLevel.DEBUG,
        ExecutionDirectiveCode.WAITING_GATE: LogLevel.INFO,
        ExecutionDirectiveCode.CONDITION_REQUIRED: LogLevel.INFO,
        ExecutionDirectiveCode.PRELAUNCH_DENIED: LogLevel.WARNING,
        ExecutionDirectiveCode.RETRY_REQUIRED: LogLevel.WARNING,
        ExecutionDirectiveCode.REPLAN_REQUIRED: LogLevel.WARNING,
        ExecutionDirectiveCode.ESCALATED: LogLevel.WARNING,
        ExecutionDirectiveCode.STOPPED: LogLevel.ERROR,
        ExecutionDirectiveCode.PARTIAL_REQUIRES_DECISION: LogLevel.WARNING,
        ExecutionDirectiveCode.RECONCILIATION_REQUIRED: LogLevel.WARNING,
        ExecutionDirectiveCode.READY_DEADLINE_EXPIRED: LogLevel.ERROR,
        ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED: LogLevel.ERROR,
    }
)


def workflow_observation_code(event_type: WorkflowEventType) -> ObservationCode:
    return _observation_code(_WORKFLOW_CODES, event_type, WorkflowEventType)


def security_observation_code(event_type: SecurityEventType) -> ObservationCode:
    return _observation_code(_SECURITY_CODES, event_type, SecurityEventType)


def error_observation_code() -> ObservationCode:
    return ObservationCode(StructuredLogCode.ERROR_ENVELOPE.value)


def directive_observation_code(code: ExecutionDirectiveCode) -> ObservationCode:
    return _observation_code(_DIRECTIVE_CODES, code, ExecutionDirectiveCode)


def workflow_log_level(status: WorkflowStatus) -> LogLevel:
    return _mapped_level(_WORKFLOW_LEVELS, status, WorkflowStatus)


def security_log_level(severity: SecuritySeverity) -> LogLevel:
    return _mapped_level(_SECURITY_LEVELS, severity, SecuritySeverity)


def error_log_level(severity: ErrorSeverity) -> LogLevel:
    return _mapped_level(_ERROR_LEVELS, severity, ErrorSeverity)


def directive_log_level(code: ExecutionDirectiveCode) -> LogLevel:
    return _mapped_level(_DIRECTIVE_LEVELS, code, ExecutionDirectiveCode)


def _observation_code[TSource: StrEnum](
    mapping: MappingProxyType[TSource, StructuredLogCode],
    value: TSource,
    expected_type: type[TSource],
) -> ObservationCode:
    if not isinstance(value, expected_type):
        raise TypeError(f"value must be a {expected_type.__name__}")
    return ObservationCode(mapping[value].value)


def _mapped_level[TSource: StrEnum](
    mapping: MappingProxyType[TSource, LogLevel],
    value: TSource,
    expected_type: type[TSource],
) -> LogLevel:
    if not isinstance(value, expected_type):
        raise TypeError(f"value must be a {expected_type.__name__}")
    return mapping[value]
