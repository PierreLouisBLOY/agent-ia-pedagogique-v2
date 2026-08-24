"""Canonical, provider-neutral workflow topology catalogue."""

from backend.agent_runtime.orchestration.workflows.catalog import (
    BASELINE_WORKFLOW_CATALOG,
    BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS,
    UnknownWorkflowError,
    WorkflowCatalog,
)
from backend.agent_runtime.orchestration.workflows.model import (
    WorkflowGateProfile,
    WorkflowKind,
    WorkflowOrderingConstraint,
    WorkflowParallelProfile,
    WorkflowResponsibility,
    WorkflowResponsibilityDescriptor,
    WorkflowRevisionProfile,
    WorkflowTopologyDescriptor,
)

__all__ = [
    "BASELINE_WORKFLOW_CATALOG",
    "BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS",
    "UnknownWorkflowError",
    "WorkflowCatalog",
    "WorkflowGateProfile",
    "WorkflowKind",
    "WorkflowOrderingConstraint",
    "WorkflowParallelProfile",
    "WorkflowResponsibility",
    "WorkflowResponsibilityDescriptor",
    "WorkflowRevisionProfile",
    "WorkflowTopologyDescriptor",
]
