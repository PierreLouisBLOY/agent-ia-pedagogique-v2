from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.agent_runtime.contracts import LogLevel
from backend.agent_runtime.observability import (
    directive_log_level,
    structured_log_from_execution_directive,
)
from backend.agent_runtime.runtime.execution import (
    ExecutionDirective,
    ExecutionDirectiveCode,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (ExecutionDirectiveCode.CONTINUE, LogLevel.DEBUG),
        (ExecutionDirectiveCode.WAITING_GATE, LogLevel.INFO),
        (ExecutionDirectiveCode.CONDITION_REQUIRED, LogLevel.INFO),
        (ExecutionDirectiveCode.PRELAUNCH_DENIED, LogLevel.WARNING),
        (ExecutionDirectiveCode.RETRY_REQUIRED, LogLevel.WARNING),
        (ExecutionDirectiveCode.REPLAN_REQUIRED, LogLevel.WARNING),
        (ExecutionDirectiveCode.ESCALATED, LogLevel.WARNING),
        (ExecutionDirectiveCode.STOPPED, LogLevel.ERROR),
        (ExecutionDirectiveCode.PARTIAL_REQUIRES_DECISION, LogLevel.WARNING),
        (ExecutionDirectiveCode.RECONCILIATION_REQUIRED, LogLevel.WARNING),
        (ExecutionDirectiveCode.READY_DEADLINE_EXPIRED, LogLevel.ERROR),
        (ExecutionDirectiveCode.RUN_DEADLINE_EXCEEDED, LogLevel.ERROR),
    ],
)
def test_directive_level_mapping_is_explicit_and_exhaustive(
    code: ExecutionDirectiveCode, expected: LogLevel
) -> None:
    assert directive_log_level(code) is expected


def test_directive_mapper_uses_only_allowlisted_control_facts() -> None:
    directive = ExecutionDirective(
        code=ExecutionDirectiveCode.RETRY_REQUIRED,
        step_id="step-01",
        reason_code="TRANSIENT_FAILURE",
    )

    record = structured_log_from_execution_directive(
        directive,
        correlation_id=CorrelationId("correlation-01"),
        run_id="run-01",
        occurred_at=NOW,
        record_id="log:directive:01",
    )

    assert record.level is LogLevel.WARNING
    assert record.code.value == "RUNTIME.RETRY_REQUIRED"
    assert record.step_id == "step-01"
    assert record.attributes == {
        "directive_code": "RETRY_REQUIRED",
        "reason_code": "TRANSIENT_FAILURE",
    }
    assert "step_id" not in record.attributes


def test_continue_directive_has_no_synthetic_reason() -> None:
    record = structured_log_from_execution_directive(
        ExecutionDirective(ExecutionDirectiveCode.CONTINUE, step_id="step-01"),
        correlation_id=CorrelationId("correlation-01"),
        run_id="run-01",
        occurred_at=NOW,
        record_id="log:directive:02",
    )

    assert record.attributes == {"directive_code": "CONTINUE"}
