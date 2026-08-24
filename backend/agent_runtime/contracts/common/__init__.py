"""Common metadata and identity contracts for agent runtime objects."""

from backend.agent_runtime.contracts.common.actor import ActorKind, ActorRef
from backend.agent_runtime.contracts.common.identities import AgentId
from backend.agent_runtime.contracts.common.metadata import ContractMeta
from backend.agent_runtime.contracts.common.safe_data import freeze_agent_safe_mapping

__all__ = [
    "ActorKind",
    "ActorRef",
    "AgentId",
    "ContractMeta",
    "freeze_agent_safe_mapping",
]
