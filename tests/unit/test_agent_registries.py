from __future__ import annotations

from dataclasses import replace

import pytest

from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.registry import (
    BASELINE_AGENT_CAPABILITY_MATRIX,
    BASELINE_AGENT_REGISTRY,
    BASELINE_CAPABILITY_REGISTRY,
    AccessMatrix,
    AccessMode,
    AgentCapabilityMatrixConfigurationError,
    AgentRegistry,
    AgentRole,
    CapabilityClass,
    CapabilityExecutionRoute,
    CapabilityRegistry,
    CapabilityRisk,
    UnknownAgentError,
    UnknownCapabilityError,
)
from backend.core_contracts.capability import CapabilityId


def _capability(code: str) -> CapabilityId:
    return CapabilityId(code)


def test_agent_registry_has_exact_canonical_agents_names_and_roles() -> None:
    descriptors = BASELINE_AGENT_REGISTRY.all()

    assert tuple(item.agent_id for item in descriptors) == tuple(AgentId)
    assert tuple((item.canonical_name, item.role) for item in descriptors) == (
        ("AG-01 — Orchestrateur", AgentRole.ORCHESTRATOR),
        ("AG-02 — Evidence/Retrieval", AgentRole.EVIDENCE_RETRIEVAL),
        ("AG-03 — Generator/Transformer", AgentRole.GENERATOR_TRANSFORMER),
        ("AG-04 — Reviewer/Critic sémantique", AgentRole.REVIEWER_CRITIC),
    )


def test_ag01_is_the_only_orchestrator_and_no_validator_agent_exists() -> None:
    descriptors = BASELINE_AGENT_REGISTRY.all()

    assert [item.agent_id for item in descriptors if item.is_orchestrator] == [AgentId.AG_01]
    assert all("validator" not in item.canonical_name.casefold() for item in descriptors)
    assert {item.agent_id.value for item in descriptors} == {
        "AG-01",
        "AG-02",
        "AG-03",
        "AG-04",
    }


def test_primary_agent_capabilities_are_exact() -> None:
    expected = {
        AgentId.AG_01: tuple(_capability(f"CAP-O{i:02d}") for i in range(1, 7)),
        AgentId.AG_02: tuple(_capability(f"CAP-E{i:02d}") for i in range(1, 4)),
        AgentId.AG_03: tuple(_capability(f"CAP-G{i:02d}") for i in range(1, 4)),
        AgentId.AG_04: tuple(_capability(f"CAP-V{i:02d}") for i in range(1, 3)),
    }

    assert {
        item.agent_id: item.primary_capability_ids for item in BASELINE_AGENT_REGISTRY.all()
    } == expected


def test_agent_registry_rejects_duplicate_agent_id() -> None:
    descriptor = BASELINE_AGENT_REGISTRY.get(AgentId.AG_01)

    with pytest.raises(ValueError, match="duplicate AgentId"):
        AgentRegistry((descriptor, descriptor))


def test_agent_registry_rejects_unknown_agent_safely() -> None:
    registry = AgentRegistry((BASELINE_AGENT_REGISTRY.get(AgentId.AG_01),))

    assert not registry.contains(AgentId.AG_02)
    with pytest.raises(UnknownAgentError, match="unknown agent: AG-02"):
        registry.get(AgentId.AG_02)


def test_agent_registry_rejects_non_ag01_orchestrator() -> None:
    with pytest.raises(ValueError, match="AG-01 must be the only orchestrator"):
        replace(BASELINE_AGENT_REGISTRY.get(AgentId.AG_02), is_orchestrator=True)


EXPECTED_CAPABILITIES = {
    "CAP-R01": ("read_canonical_resource", CapabilityClass.READ, CapabilityRisk.R0),
    "CAP-R02": ("read_production", CapabilityClass.READ, CapabilityRisk.R0),
    "CAP-R03": ("read_metadata_status", CapabilityClass.READ, CapabilityRisk.R0),
    "CAP-E01": ("search_evidence", CapabilityClass.EVIDENCE, CapabilityRisk.R0),
    "CAP-E02": ("fetch_evidence_item", CapabilityClass.EVIDENCE, CapabilityRisk.R0),
    "CAP-E03": ("assess_evidence_coverage", CapabilityClass.EVIDENCE, CapabilityRisk.R0),
    "CAP-G01": ("generate_production", CapabilityClass.GENERATE_TRANSFORM, CapabilityRisk.R1),
    "CAP-G02": ("transform_production", CapabilityClass.GENERATE_TRANSFORM, CapabilityRisk.R1),
    "CAP-G03": ("correct_production", CapabilityClass.GENERATE_TRANSFORM, CapabilityRisk.R1),
    "CAP-V01": ("semantic_review", CapabilityClass.REVIEW, CapabilityRisk.R1),
    "CAP-V02": ("assess_findings", CapabilityClass.REVIEW, CapabilityRisk.R1),
    "CAP-A01": (
        "run_deterministic_validation",
        CapabilityClass.APPLICATION_ACTION,
        CapabilityRisk.R3,
    ),
    "CAP-A02": ("request_promotion", CapabilityClass.APPLICATION_ACTION, CapabilityRisk.R4),
    "CAP-A03": ("export_artifact", CapabilityClass.APPLICATION_ACTION, CapabilityRisk.R3),
    "CAP-T01": ("validate_schema", CapabilityClass.TECHNICAL_UTILITY, CapabilityRisk.R0),
    "CAP-T02": ("render_document", CapabilityClass.TECHNICAL_UTILITY, CapabilityRisk.R2),
    "CAP-T03": ("convert_format", CapabilityClass.TECHNICAL_UTILITY, CapabilityRisk.R2),
    "CAP-T04": ("estimate_token_cost", CapabilityClass.TECHNICAL_UTILITY, CapabilityRisk.R0),
    "CAP-O01": ("plan_workflow", CapabilityClass.ORCHESTRATION, CapabilityRisk.R0),
    "CAP-O02": ("route_capability", CapabilityClass.ORCHESTRATION, CapabilityRisk.R0),
    "CAP-O03": ("delegate_agent", CapabilityClass.ORCHESTRATION, CapabilityRisk.R0),
    "CAP-O04": ("join_results", CapabilityClass.ORCHESTRATION, CapabilityRisk.R0),
    "CAP-O05": ("request_gate", CapabilityClass.ORCHESTRATION, CapabilityRisk.R0),
    "CAP-O06": ("stop_or_replan", CapabilityClass.ORCHESTRATION, CapabilityRisk.R0),
}


def test_capability_registry_has_exact_ids_names_classes_and_risks() -> None:
    descriptors = BASELINE_CAPABILITY_REGISTRY.all()

    assert len(descriptors) == 24
    assert {
        item.capability_id.value: (
            item.canonical_name,
            item.capability_class,
            item.risk,
        )
        for item in descriptors
    } == EXPECTED_CAPABILITIES
    assert len({item.canonical_name for item in descriptors}) == 24


def test_capability_routes_and_agent_owners_are_exact() -> None:
    for descriptor in BASELINE_CAPABILITY_REGISTRY.all():
        prefix = descriptor.capability_id.value[4]
        if prefix == "E":
            assert (descriptor.execution_route, descriptor.owner_agent) == (
                CapabilityExecutionRoute.AGENT,
                AgentId.AG_02,
            )
        elif prefix == "G":
            assert (descriptor.execution_route, descriptor.owner_agent) == (
                CapabilityExecutionRoute.AGENT,
                AgentId.AG_03,
            )
        elif prefix == "V":
            assert (descriptor.execution_route, descriptor.owner_agent) == (
                CapabilityExecutionRoute.AGENT,
                AgentId.AG_04,
            )
        else:
            expected_route = {
                "R": CapabilityExecutionRoute.APPLICATION,
                "A": CapabilityExecutionRoute.APPLICATION,
                "T": CapabilityExecutionRoute.UTILITY,
                "O": CapabilityExecutionRoute.RUNTIME,
            }[prefix]
            assert descriptor.execution_route is expected_route
            assert descriptor.owner_agent is None

    assert len(BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_02)) == 3
    assert len(BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_03)) == 3
    assert len(BASELINE_CAPABILITY_REGISTRY.owned_by(AgentId.AG_04)) == 2


def test_capability_registry_rejects_duplicate_id_and_name() -> None:
    descriptor = BASELINE_CAPABILITY_REGISTRY.get(_capability("CAP-R01"))

    with pytest.raises(ValueError, match="duplicate CapabilityId"):
        CapabilityRegistry((descriptor, descriptor))
    with pytest.raises(ValueError, match="duplicate canonical_name"):
        CapabilityRegistry(
            (
                descriptor,
                replace(descriptor, capability_id=_capability("CAP-X01")),
            )
        )


def test_capability_registry_rejects_unknown_capability_safely() -> None:
    unknown = _capability("CAP-X99")

    assert not BASELINE_CAPABILITY_REGISTRY.contains(unknown)
    with pytest.raises(UnknownCapabilityError, match="unknown capability: CAP-X99"):
        BASELINE_CAPABILITY_REGISTRY.get(unknown)


def test_matrix_is_exhaustive_with_96_explicit_rules() -> None:
    rules = BASELINE_AGENT_CAPABILITY_MATRIX.all()

    assert len(rules) == 96
    assert len({(rule.agent_id, rule.capability_id) for rule in rules}) == 96
    assert all(
        len(BASELINE_AGENT_CAPABILITY_MATRIX.rules_for_agent(agent_id)) == 24
        for agent_id in AgentId
    )
    assert all(
        len(BASELINE_AGENT_CAPABILITY_MATRIX.rules_for_capability(descriptor.capability_id)) == 4
        for descriptor in BASELINE_CAPABILITY_REGISTRY.all()
    )


@pytest.mark.parametrize(
    ("prefix", "owner"), (("E", AgentId.AG_02), ("G", AgentId.AG_03), ("V", AgentId.AG_04))
)
def test_evidence_generation_review_separation_is_exact(prefix: str, owner: AgentId) -> None:
    capabilities = [
        descriptor.capability_id
        for descriptor in BASELINE_CAPABILITY_REGISTRY.all()
        if descriptor.capability_id.value.startswith(f"CAP-{prefix}")
    ]

    for capability_id in capabilities:
        assert (
            BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(AgentId.AG_01, capability_id).mode
            is AccessMode.DELEGATE
        )
        for agent_id in AgentId:
            if agent_id is AgentId.AG_01:
                continue
            expected = AccessMode.ALLOW if agent_id is owner else AccessMode.DENY
            assert (
                BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(agent_id, capability_id).mode is expected
            )


def test_application_actions_never_grant_specialists_and_promotion_needs_gate() -> None:
    for code in ("CAP-A01", "CAP-A02", "CAP-A03"):
        for agent_id in (AgentId.AG_02, AgentId.AG_03, AgentId.AG_04):
            assert (
                BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(agent_id, _capability(code)).mode
                is AccessMode.DENY
            )

    assert (
        BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(AgentId.AG_01, _capability("CAP-A02")).mode
        is AccessMode.REQUEST_GATE
    )


def test_orchestration_is_allowed_only_to_ag01() -> None:
    for index in range(1, 7):
        capability_id = _capability(f"CAP-O{index:02d}")
        assert (
            BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(AgentId.AG_01, capability_id).mode
            is AccessMode.ALLOW
        )
        assert all(
            BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(agent_id, capability_id).mode
            is AccessMode.DENY
            for agent_id in (AgentId.AG_02, AgentId.AG_03, AgentId.AG_04)
        )


def test_t02_t03_conditions_and_limits_are_exact() -> None:
    expected = {
        AgentId.AG_01: (
            AccessMode.CONDITIONAL,
            False,
            "request_or_allow_by_workflow",
        ),
        AgentId.AG_02: (AccessMode.DENY, False, "default"),
        AgentId.AG_03: (AccessMode.ALLOW, True, None),
        AgentId.AG_04: (AccessMode.DENY, False, "default"),
    }

    for code in ("CAP-T02", "CAP-T03"):
        assert {
            agent_id: (
                (
                    rule := BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(agent_id, _capability(code))
                ).mode,
                rule.limited,
                rule.condition,
            )
            for agent_id in AgentId
        } == expected


def test_t04_is_allowed_to_every_agent() -> None:
    assert all(
        BASELINE_AGENT_CAPABILITY_MATRIX.rule_for(agent_id, _capability("CAP-T04")).mode
        is AccessMode.ALLOW
        for agent_id in AgentId
    )


def test_matrix_refuses_a_missing_cell_instead_of_deriving_a_mode() -> None:
    rules = BASELINE_AGENT_CAPABILITY_MATRIX.all()[:-1]

    with pytest.raises(AgentCapabilityMatrixConfigurationError, match="1 missing, 0 unexpected"):
        AccessMatrix(
            rules,
            agent_ids=tuple(AgentId),
            capability_ids=tuple(item.capability_id for item in BASELINE_CAPABILITY_REGISTRY.all()),
        )
