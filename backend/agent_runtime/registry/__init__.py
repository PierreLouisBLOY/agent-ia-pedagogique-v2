"""Static agent and capability catalogues for the provider-neutral runtime."""

from backend.agent_runtime.registry.access_matrix import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    REQUEST_OR_ALLOW_BY_WORKFLOW,
    AccessMatrix,
    AccessMode,
    AgentCapabilityMatrixConfigurationError,
    AgentCapabilityRule,
)
from backend.agent_runtime.registry.agents import (
    BASELINE_AGENT_REGISTRY,
    AgentDescriptor,
    AgentRegistry,
    AgentRole,
    UnknownAgentError,
)
from backend.agent_runtime.registry.capabilities import (
    BASELINE_CAPABILITY_REGISTRY,
    CapabilityClass,
    CapabilityDescriptor,
    CapabilityExecutionRoute,
    CapabilityRegistry,
    CapabilityRisk,
    UnknownCapabilityError,
)
from backend.agent_runtime.registry.tools import (
    BASELINE_TOOL_REGISTRY,
    ToolDescriptor,
    ToolEffectClass,
    ToolRegistry,
    ToolRegistryConfigurationError,
    UnknownToolError,
)

__all__ = [
    "BASELINE_AGENT_CAPABILITY_MATRIX",
    "BASELINE_AGENT_REGISTRY",
    "BASELINE_CAPABILITY_REGISTRY",
    "BASELINE_TOOL_REGISTRY",
    "REQUEST_OR_ALLOW_BY_WORKFLOW",
    "AccessMatrix",
    "AccessMode",
    "AgentCapabilityMatrixConfigurationError",
    "AgentCapabilityRule",
    "AgentDescriptor",
    "AgentRegistry",
    "AgentRole",
    "CapabilityClass",
    "CapabilityDescriptor",
    "CapabilityExecutionRoute",
    "CapabilityRegistry",
    "CapabilityRisk",
    "ToolDescriptor",
    "ToolEffectClass",
    "ToolRegistry",
    "ToolRegistryConfigurationError",
    "UnknownAgentError",
    "UnknownCapabilityError",
    "UnknownToolError",
]
