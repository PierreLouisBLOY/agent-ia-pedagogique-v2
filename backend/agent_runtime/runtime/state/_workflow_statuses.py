from typing import Final

from backend.agent_runtime.contracts import WorkflowStatus

TERMINAL_WORKFLOW_STATUSES: Final = frozenset(
    {
        WorkflowStatus.SUCCEEDED,
        WorkflowStatus.PARTIAL,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.ESCALATED,
    }
)
