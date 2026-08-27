from __future__ import annotations

import pytest

from backend.agent_runtime.contracts import (
    ErrorSeverity,
    LogLevel,
    SecurityEventType,
    SecuritySeverity,
    WorkflowEventType,
    WorkflowStatus,
)
from backend.agent_runtime.observability import (
    StructuredLogCode,
    error_log_level,
    security_log_level,
    security_observation_code,
    workflow_log_level,
    workflow_observation_code,
)
from backend.agent_runtime.runtime.execution import ExecutionDirectiveCode


def test_structured_log_catalog_is_unique_and_covers_only_mapped_families() -> None:
    values = [item.value for item in StructuredLogCode]

    assert len(values) == len(set(values))
    assert {value.partition(".")[0] for value in values} == {
        "WORKFLOW",
        "SECURITY",
        "ERROR",
        "RUNTIME",
    }
    assert all(value == value.upper() for value in values)


def test_source_code_mappings_cover_every_closed_source_variant() -> None:
    assert {
        workflow_observation_code(item).value for item in WorkflowEventType
    } == {
        item.value for item in StructuredLogCode if item.name.startswith("WORKFLOW_")
    }
    assert {
        security_observation_code(item).value for item in SecurityEventType
    } == {
        item.value for item in StructuredLogCode if item.name.startswith("SECURITY_")
    }
    assert len(
        {
            item
            for item in StructuredLogCode
            if item.name.startswith("RUNTIME_")
        }
    ) == len(ExecutionDirectiveCode)


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        (SecuritySeverity.LOW, LogLevel.INFO),
        (SecuritySeverity.MEDIUM, LogLevel.WARNING),
        (SecuritySeverity.HIGH, LogLevel.ERROR),
        (SecuritySeverity.CRITICAL, LogLevel.CRITICAL),
    ],
)
def test_security_severity_mapping_is_explicit(
    severity: SecuritySeverity, expected: LogLevel
) -> None:
    assert security_log_level(severity) is expected


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        (ErrorSeverity.INFO, LogLevel.INFO),
        (ErrorSeverity.WARNING, LogLevel.WARNING),
        (ErrorSeverity.ERROR, LogLevel.ERROR),
        (ErrorSeverity.CRITICAL, LogLevel.CRITICAL),
    ],
)
def test_error_severity_mapping_is_explicit(
    severity: ErrorSeverity, expected: LogLevel
) -> None:
    assert error_log_level(severity) is expected


def test_workflow_level_mapping_is_exhaustive() -> None:
    assert {status: workflow_log_level(status) for status in WorkflowStatus} == {
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
