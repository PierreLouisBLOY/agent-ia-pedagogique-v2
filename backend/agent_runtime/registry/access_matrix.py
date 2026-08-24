from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry.agents import (
    BASELINE_AGENT_REGISTRY,
    UnknownAgentError,
)
from backend.agent_runtime.registry.capabilities import (
    BASELINE_CAPABILITY_REGISTRY,
    UnknownCapabilityError,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel._strings import require_non_empty


class AccessMode(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUEST = "REQUEST"
    DELEGATE = "DELEGATE"
    REQUEST_GATE = "REQUEST_GATE"
    CONDITIONAL = "CONDITIONAL"


@dataclass(frozen=True, slots=True)
class AgentCapabilityRule:
    agent_id: AgentId
    capability_id: CapabilityId
    mode: AccessMode
    limited: bool = False
    condition: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        if not isinstance(self.capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if not isinstance(self.mode, AccessMode):
            raise TypeError("mode must be an AccessMode")
        if not isinstance(self.limited, bool):
            raise TypeError("limited must be a bool")
        if self.condition is not None:
            require_non_empty(self.condition, "condition")


class AgentCapabilityMatrixConfigurationError(ValueError):
    """Raised when a static matrix has duplicates, missing cells, or foreign cells."""


@dataclass(frozen=True, slots=True)
class AccessMatrix:
    _rules: tuple[AgentCapabilityRule, ...]
    _agent_ids: tuple[AgentId, ...]
    _capability_ids: tuple[CapabilityId, ...]

    def __init__(
        self,
        rules: Iterable[AgentCapabilityRule],
        *,
        agent_ids: Iterable[AgentId],
        capability_ids: Iterable[CapabilityId],
    ) -> None:
        normalized_rules = tuple(rules)
        normalized_agents = tuple(agent_ids)
        normalized_capabilities = tuple(capability_ids)
        if any(not isinstance(item, AgentCapabilityRule) for item in normalized_rules):
            raise TypeError("rules must contain AgentCapabilityRule values")
        if any(not isinstance(item, AgentId) for item in normalized_agents):
            raise TypeError("agent_ids must contain AgentId values")
        if any(not isinstance(item, CapabilityId) for item in normalized_capabilities):
            raise TypeError("capability_ids must contain CapabilityId values")
        if len(set(normalized_agents)) != len(normalized_agents):
            raise AgentCapabilityMatrixConfigurationError("duplicate AgentId in matrix scope")
        if len(set(normalized_capabilities)) != len(normalized_capabilities):
            raise AgentCapabilityMatrixConfigurationError("duplicate CapabilityId in matrix scope")

        keys = tuple((rule.agent_id, rule.capability_id) for rule in normalized_rules)
        if len(set(keys)) != len(keys):
            raise AgentCapabilityMatrixConfigurationError("duplicate matrix cell")
        expected_keys = {
            (agent_id, capability_id)
            for agent_id in normalized_agents
            for capability_id in normalized_capabilities
        }
        actual_keys = set(keys)
        missing = expected_keys - actual_keys
        unexpected = actual_keys - expected_keys
        if missing or unexpected:
            raise AgentCapabilityMatrixConfigurationError(
                f"matrix must be exhaustive: {len(missing)} missing, {len(unexpected)} unexpected"
            )

        object.__setattr__(self, "_rules", normalized_rules)
        object.__setattr__(self, "_agent_ids", normalized_agents)
        object.__setattr__(self, "_capability_ids", normalized_capabilities)
        object.__setattr__(
            self,
            "_by_key",
            MappingProxyType(
                {(rule.agent_id, rule.capability_id): rule for rule in normalized_rules}
            ),
        )

    _by_key: MappingProxyType[tuple[AgentId, CapabilityId], AgentCapabilityRule]

    def rule_for(self, agent_id: AgentId, capability_id: CapabilityId) -> AgentCapabilityRule:
        self._require_agent(agent_id)
        self._require_capability(capability_id)
        try:
            return self._by_key[(agent_id, capability_id)]
        except KeyError as error:
            raise AgentCapabilityMatrixConfigurationError("matrix cell is missing") from error

    def rules_for_agent(self, agent_id: AgentId) -> tuple[AgentCapabilityRule, ...]:
        self._require_agent(agent_id)
        return tuple(rule for rule in self._rules if rule.agent_id is agent_id)

    def rules_for_capability(self, capability_id: CapabilityId) -> tuple[AgentCapabilityRule, ...]:
        self._require_capability(capability_id)
        return tuple(rule for rule in self._rules if rule.capability_id == capability_id)

    def all(self) -> tuple[AgentCapabilityRule, ...]:
        return self._rules

    def _require_agent(self, agent_id: AgentId) -> None:
        if not isinstance(agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        if agent_id not in self._agent_ids:
            raise UnknownAgentError(agent_id)

    def _require_capability(self, capability_id: CapabilityId) -> None:
        if not isinstance(capability_id, CapabilityId):
            raise TypeError("capability_id must be a CapabilityId")
        if capability_id not in self._capability_ids:
            raise UnknownCapabilityError(capability_id)


def _rule(
    agent_id: AgentId,
    capability_code: str,
    mode: AccessMode,
    *,
    limited: bool = False,
    condition: str | None = None,
) -> AgentCapabilityRule:
    return AgentCapabilityRule(
        agent_id=agent_id,
        capability_id=CapabilityId(capability_code),
        mode=mode,
        limited=limited,
        condition=condition,
    )


def _baseline_rules() -> tuple[AgentCapabilityRule, ...]:
    rules: list[AgentCapabilityRule] = []
    agents = tuple(AgentId)

    for code in ("CAP-R01", "CAP-R02", "CAP-R03"):
        rules.append(_rule(AgentId.AG_01, code, AccessMode.REQUEST))
        rules.extend(
            _rule(agent_id, code, AccessMode.REQUEST, limited=True) for agent_id in agents[1:]
        )

    for code in ("CAP-E01", "CAP-E02", "CAP-E03"):
        rules.extend(
            (
                _rule(AgentId.AG_01, code, AccessMode.DELEGATE),
                _rule(AgentId.AG_02, code, AccessMode.ALLOW),
                _rule(AgentId.AG_03, code, AccessMode.DENY, condition="direct_call"),
                _rule(AgentId.AG_04, code, AccessMode.DENY, condition="direct_call"),
            )
        )

    for code in ("CAP-G01", "CAP-G02", "CAP-G03"):
        rules.extend(
            (
                _rule(AgentId.AG_01, code, AccessMode.DELEGATE),
                _rule(AgentId.AG_02, code, AccessMode.DENY),
                _rule(AgentId.AG_03, code, AccessMode.ALLOW),
                _rule(AgentId.AG_04, code, AccessMode.DENY),
            )
        )

    for code in ("CAP-V01", "CAP-V02"):
        rules.extend(
            (
                _rule(AgentId.AG_01, code, AccessMode.DELEGATE),
                _rule(AgentId.AG_02, code, AccessMode.DENY),
                _rule(AgentId.AG_03, code, AccessMode.DENY),
                _rule(AgentId.AG_04, code, AccessMode.ALLOW),
            )
        )

    application_modes = {
        "CAP-A01": AccessMode.REQUEST,
        "CAP-A02": AccessMode.REQUEST_GATE,
        "CAP-A03": AccessMode.REQUEST,
    }
    for code, mode in application_modes.items():
        rules.append(_rule(AgentId.AG_01, code, mode))
        rules.extend(_rule(agent_id, code, AccessMode.DENY) for agent_id in agents[1:])

    rules.append(_rule(AgentId.AG_01, "CAP-T01", AccessMode.ALLOW))
    rules.extend(
        _rule(agent_id, "CAP-T01", AccessMode.ALLOW, limited=True) for agent_id in agents[1:]
    )

    for code in ("CAP-T02", "CAP-T03"):
        rules.extend(
            (
                _rule(
                    AgentId.AG_01,
                    code,
                    AccessMode.CONDITIONAL,
                    condition="request_or_allow_by_workflow",
                ),
                _rule(AgentId.AG_02, code, AccessMode.DENY, condition="default"),
                _rule(AgentId.AG_03, code, AccessMode.ALLOW, limited=True),
                _rule(AgentId.AG_04, code, AccessMode.DENY, condition="default"),
            )
        )

    rules.extend(_rule(agent_id, "CAP-T04", AccessMode.ALLOW) for agent_id in agents)

    for code in ("CAP-O01", "CAP-O02", "CAP-O03", "CAP-O04", "CAP-O05", "CAP-O06"):
        rules.append(_rule(AgentId.AG_01, code, AccessMode.ALLOW))
        rules.extend(_rule(agent_id, code, AccessMode.DENY) for agent_id in agents[1:])

    return tuple(rules)


BASELINE_AGENT_CAPABILITY_MATRIX: Final = AccessMatrix(
    _baseline_rules(),
    agent_ids=tuple(item.agent_id for item in BASELINE_AGENT_REGISTRY.all()),
    capability_ids=tuple(item.capability_id for item in BASELINE_CAPABILITY_REGISTRY.all()),
)
