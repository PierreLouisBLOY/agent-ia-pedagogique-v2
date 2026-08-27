from __future__ import annotations

from enum import StrEnum

from backend.agent_runtime.contracts.observability.log import ObservationCode


class SpanCode(StrEnum):
    """Closed technical operation catalog for future runtime instrumentation."""

    RUNTIME_CYCLE = "RUNTIME.CYCLE"
    RUNTIME_STEP = "RUNTIME.STEP"
    ROUTING_PRELAUNCH = "ROUTING.PRELAUNCH"
    AGENT_INVOCATION = "AGENT.INVOCATION"
    TOOL_CALL = "TOOL.CALL"
    APPLICATION_CALL = "APPLICATION.CALL"
    GATE_EVALUATION = "GATE.EVALUATION"
    RECOVERY_CYCLE = "RECOVERY.CYCLE"
    RECOVERY_RECONCILIATION = "RECOVERY.RECONCILIATION"
    RECOVERY_RETRY = "RECOVERY.RETRY"


def span_observation_code(code: SpanCode) -> ObservationCode:
    if not isinstance(code, SpanCode):
        raise TypeError("code must be a SpanCode")
    return ObservationCode(code.value)
