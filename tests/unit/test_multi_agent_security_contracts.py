from dataclasses import fields, replace

import pytest

from backend.agent_runtime.contracts import (
    ActorKind,
    ActorRef,
    AgentId,
    AgentResult,
    AgentResultStatus,
    DelegationEnvelope,
    DelegationResult,
    PermissionScope,
)
from backend.core_contracts.capability import CapabilityId
from tests.support.multi_agent_security_fixtures import delegation, meta, result, step


def test_agent_result_producer_is_canonical_and_derived_from_meta_actor() -> None:
    produced = AgentResult[object](
        meta=meta(AgentResultStatus.SUCCEEDED, AgentId.AG_03),
        invocation_id="invocation-e",
    )
    assert produced.producer_agent is AgentId.AG_03
    with pytest.raises(ValueError, match="canonical agent"):
        AgentResult[object](
            meta=replace(
                produced.meta,
                actor=ActorRef(ActorKind.AGENT, "AG-99"),
            ),
            invocation_id="invocation-e",
        )


def test_delegation_envelope_is_owned_by_ag01_exact_capability_and_depth_one() -> None:
    canonical = delegation()
    assert canonical.source_agent is AgentId.AG_01
    assert canonical.delegation_depth == 1
    assert canonical.permission_scope.capability_ids == (
        canonical.source_step.capability_id,
    )
    assert canonical.permission_scope.delegable is False

    with pytest.raises(ValueError, match="source_agent"):
        replace(canonical, source_agent=AgentId.AG_02)
    with pytest.raises(ValueError, match="depth"):
        replace(canonical, delegation_depth=2)
    with pytest.raises(ValueError, match="redelegable"):
        replace(
            canonical,
            permission_scope=replace(canonical.permission_scope, delegable=True),
        )


def test_specialists_cannot_change_target_capability_or_child_principal() -> None:
    with pytest.raises(ValueError, match="executor"):
        DelegationEnvelope(
            "delegation-e",
            step(AgentId.AG_03),
            AgentId.AG_02,
            {},
            (),
            {},
            PermissionScope(
                principal=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
                capability_ids=(CapabilityId("CAP-G01"),),
            ),
        )
    with pytest.raises(ValueError, match="exactly the delegated capability"):
        replace(
            delegation(AgentId.AG_04),
            permission_scope=PermissionScope(
                principal=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
                capability_ids=(CapabilityId("CAP-G01"),),
            ),
        )
    with pytest.raises(ValueError, match="principal"):
        replace(
            delegation(),
            permission_scope=PermissionScope(
                principal=ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
                capability_ids=(CapabilityId("CAP-G01"),),
            ),
        )


def test_delegation_result_separates_direct_and_delegated_results() -> None:
    delegated = result()
    direct = DelegationResult(
        delegation_id="direct-result-e",
        source_agent=AgentId.AG_03,
        agent_result=delegated.agent_result,
    )
    assert delegated.is_delegated is True
    assert direct.is_delegated is False


def test_delegation_result_refuses_producer_spoof_and_wrong_identity() -> None:
    delegated = delegation()
    ag04_result = AgentResult[object](
        meta=meta(AgentResultStatus.SUCCEEDED, AgentId.AG_04),
        invocation_id="invocation-e",
    )
    with pytest.raises(ValueError, match="producer"):
        DelegationResult(
            delegated.delegation_id,
            AgentId.AG_03,
            ag04_result,
            delegated,
        )
    with pytest.raises(ValueError, match="delegation_id"):
        replace(result(delegated), delegation_id="other-delegation")


def test_succeeded_status_has_no_domain_validation_or_gate_semantics() -> None:
    result_fields = {item.name for item in fields(AgentResult)}
    assert "domain_validated" not in result_fields
    assert "gate_decision" not in result_fields
    assert "promotion_allowed" not in result_fields
