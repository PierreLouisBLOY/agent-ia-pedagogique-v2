"""Common metadata and identity contracts for agent runtime objects."""

from backend.agent_runtime.contracts.common.actor import ActorKind, ActorRef
from backend.agent_runtime.contracts.common.identities import AgentId
from backend.agent_runtime.contracts.common.metadata import ContractMeta
from backend.agent_runtime.contracts.common.references import ContractRef, require_contract_ref
from backend.agent_runtime.contracts.common.safe_data import (
    AGENT_SAFE_DATA_LIMITS,
    ERROR_SAFE_DATA_LIMITS,
    SECURITY_EVENT_DATA_LIMITS,
    freeze_agent_safe_mapping,
    require_agent_safe_ref,
    require_agent_safe_text,
    require_agent_safe_value,
)
from backend.agent_runtime.contracts.common.schema_version import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ContractSchemaVersion,
)

__all__ = [
    "AGENT_CONTRACT_SCHEMA_V1_0",
    "AGENT_SAFE_DATA_LIMITS",
    "ActorKind",
    "ActorRef",
    "AgentId",
    "ContractMeta",
    "ContractRef",
    "ContractSchemaVersion",
    "ERROR_SAFE_DATA_LIMITS",
    "SECURITY_EVENT_DATA_LIMITS",
    "freeze_agent_safe_mapping",
    "require_agent_safe_ref",
    "require_agent_safe_text",
    "require_agent_safe_value",
    "require_contract_ref",
]
