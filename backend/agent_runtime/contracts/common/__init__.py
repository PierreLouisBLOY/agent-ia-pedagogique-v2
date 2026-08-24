"""Common metadata and identity contracts for agent runtime objects."""

from backend.agent_runtime.contracts.common.actor import ActorKind, ActorRef
from backend.agent_runtime.contracts.common.identities import AgentId
from backend.agent_runtime.contracts.common.metadata import ContractMeta
from backend.agent_runtime.contracts.common.references import ContractRef, require_contract_ref
from backend.agent_runtime.contracts.common.safe_data import freeze_agent_safe_mapping
from backend.agent_runtime.contracts.common.schema_version import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ContractSchemaVersion,
)

__all__ = [
    "AGENT_CONTRACT_SCHEMA_V1_0",
    "ActorKind",
    "ActorRef",
    "AgentId",
    "ContractMeta",
    "ContractRef",
    "ContractSchemaVersion",
    "freeze_agent_safe_mapping",
    "require_contract_ref",
]
