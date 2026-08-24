from __future__ import annotations

from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry import (
    BASELINE_CAPABILITY_REGISTRY,
    REQUEST_OR_ALLOW_BY_WORKFLOW,
    AccessMatrix,
    AccessMode,
    AgentRegistry,
    CapabilityClass,
    CapabilityDescriptor,
    CapabilityExecutionRoute,
    CapabilityRegistry,
)
from backend.core_contracts.capability import CapabilityId

_AGENTS = tuple(AgentId)
_SPECIALISTS = (AgentId.AG_02, AgentId.AG_03, AgentId.AG_04)
_EXPECTED_CAPABILITY_IDS = frozenset(
    descriptor.capability_id.value for descriptor in BASELINE_CAPABILITY_REGISTRY.all()
)


class PolicyConfigurationError(ValueError):
    """Raised when the static authorization policy is internally inconsistent."""


def validate_policy_configuration(
    agent_registry: AgentRegistry,
    capability_registry: CapabilityRegistry,
    access_matrix: AccessMatrix,
) -> None:
    if not isinstance(agent_registry, AgentRegistry):
        raise TypeError("agent_registry must be an AgentRegistry")
    if not isinstance(capability_registry, CapabilityRegistry):
        raise TypeError("capability_registry must be a CapabilityRegistry")
    if not isinstance(access_matrix, AccessMatrix):
        raise TypeError("access_matrix must be an AccessMatrix")

    agents = agent_registry.all()
    capabilities = capability_registry.all()
    rules = access_matrix.all()
    _require(len(agents) == 4, "policy requires exactly 4 agents")
    _require(
        {descriptor.agent_id for descriptor in agents} == set(_AGENTS),
        "policy agent catalogue is not canonical",
    )
    _require(len(capabilities) == 24, "policy requires exactly 24 capabilities")
    _require(
        {descriptor.capability_id.value for descriptor in capabilities} == _EXPECTED_CAPABILITY_IDS,
        "policy capability catalogue is not canonical",
    )
    _require(len(rules) == 96, "policy requires exactly 96 matrix rules")

    for capability in capabilities:
        code = capability.capability_id.value
        prefix = code[4]
        expected_class = {
            "R": CapabilityClass.READ,
            "E": CapabilityClass.EVIDENCE,
            "G": CapabilityClass.GENERATE_TRANSFORM,
            "V": CapabilityClass.REVIEW,
            "A": CapabilityClass.APPLICATION_ACTION,
            "T": CapabilityClass.TECHNICAL_UTILITY,
            "O": CapabilityClass.ORCHESTRATION,
        }.get(prefix)
        _require(
            expected_class is not None and capability.capability_class is expected_class,
            f"{code} capability class is inconsistent",
        )
        if prefix in {"E", "G", "V"}:
            _validate_agent_route(access_matrix, capability)
        elif prefix == "R":
            _require(
                capability.execution_route is CapabilityExecutionRoute.APPLICATION,
                f"{code} must use APPLICATION route",
            )
            for agent_id in _AGENTS:
                rule = access_matrix.rule_for(agent_id, capability.capability_id)
                _require(rule.mode is AccessMode.REQUEST, f"{code} must be REQUEST")
                _require(
                    rule.limited is (agent_id is not AgentId.AG_01),
                    f"{code} limited flags are inconsistent",
                )
        elif prefix == "A":
            _validate_application_action(access_matrix, capability.capability_id)
            _require(
                capability.execution_route is CapabilityExecutionRoute.APPLICATION,
                f"{code} must use APPLICATION route",
            )
        elif prefix == "O":
            _require(
                capability.execution_route is CapabilityExecutionRoute.RUNTIME,
                f"{code} must use RUNTIME route",
            )
            _require_mode(access_matrix, AgentId.AG_01, capability.capability_id, AccessMode.ALLOW)
            for agent_id in _SPECIALISTS:
                _require_mode(access_matrix, agent_id, capability.capability_id, AccessMode.DENY)
        elif prefix == "T":
            _require(
                capability.execution_route is CapabilityExecutionRoute.UTILITY,
                f"{code} must use UTILITY route",
            )
            _validate_utility(access_matrix, capability.capability_id)
        else:
            raise PolicyConfigurationError(f"unsupported capability family: {code}")

    for capability in capabilities:
        if capability.execution_route is CapabilityExecutionRoute.APPLICATION:
            _require(
                all(
                    rule.mode is not AccessMode.ALLOW
                    for rule in access_matrix.rules_for_capability(capability.capability_id)
                ),
                f"{capability.capability_id.value} cannot grant direct APPLICATION ALLOW",
            )


def _validate_agent_route(
    access_matrix: AccessMatrix,
    capability: CapabilityDescriptor,
) -> None:
    code = capability.capability_id.value
    expected_owner = {
        "E": AgentId.AG_02,
        "G": AgentId.AG_03,
        "V": AgentId.AG_04,
    }[code[4]]
    _require(
        capability.execution_route is CapabilityExecutionRoute.AGENT,
        f"{code} must use AGENT route",
    )
    _require(capability.owner_agent is expected_owner, f"{code} owner is inconsistent")
    _require_mode(access_matrix, AgentId.AG_01, capability.capability_id, AccessMode.DELEGATE)
    for agent_id in _SPECIALISTS:
        expected_mode = AccessMode.ALLOW if agent_id is expected_owner else AccessMode.DENY
        _require_mode(access_matrix, agent_id, capability.capability_id, expected_mode)


def _validate_application_action(access_matrix: AccessMatrix, capability_id: CapabilityId) -> None:
    expected = AccessMode.REQUEST_GATE if capability_id.value == "CAP-A02" else AccessMode.REQUEST
    _require_mode(access_matrix, AgentId.AG_01, capability_id, expected)
    for agent_id in _SPECIALISTS:
        _require_mode(access_matrix, agent_id, capability_id, AccessMode.DENY)


def _validate_utility(access_matrix: AccessMatrix, capability_id: CapabilityId) -> None:
    code = capability_id.value
    if code == "CAP-T01":
        _require_mode(access_matrix, AgentId.AG_01, capability_id, AccessMode.ALLOW)
        for agent_id in _SPECIALISTS:
            rule = access_matrix.rule_for(agent_id, capability_id)
            _require(rule.mode is AccessMode.ALLOW and rule.limited, "T01 specialist rule invalid")
        return
    if code in {"CAP-T02", "CAP-T03"}:
        rule = access_matrix.rule_for(AgentId.AG_01, capability_id)
        _require(
            rule.mode is AccessMode.CONDITIONAL and rule.condition == REQUEST_OR_ALLOW_BY_WORKFLOW,
            f"{code} AG-01 conditional rule invalid",
        )
        for agent_id in (AgentId.AG_02, AgentId.AG_04):
            _require_mode(access_matrix, agent_id, capability_id, AccessMode.DENY)
        owner_rule = access_matrix.rule_for(AgentId.AG_03, capability_id)
        _require(
            owner_rule.mode is AccessMode.ALLOW and owner_rule.limited,
            f"{code} AG-03 rule invalid",
        )
        return
    if code == "CAP-T04":
        for agent_id in _AGENTS:
            _require_mode(access_matrix, agent_id, capability_id, AccessMode.ALLOW)
        return
    raise PolicyConfigurationError(f"unsupported utility capability: {code}")


def _require_mode(
    access_matrix: AccessMatrix,
    agent_id: AgentId,
    capability_id: CapabilityId,
    mode: AccessMode,
) -> None:
    rule = access_matrix.rule_for(agent_id, capability_id)
    _require(
        rule.mode is mode,
        f"{agent_id.value}/{capability_id.value} must be {mode.value}",
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PolicyConfigurationError(message)
