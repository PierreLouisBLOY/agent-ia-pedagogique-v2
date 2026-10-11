"""Synthetic boundary witnesses; no true grant/SQL/secret/provider."""
import copy
import json
from datetime import UTC, datetime
from secrets import token_hex

import pytest

from backend.agent_runtime.contracts.common import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
)
from backend.agent_runtime.contracts.invocation import InvocationStatus
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant
from tests.integration.test_p0_creation_http import context
from tests.unit.test_p0_creation_contract import service

NOW = datetime(2026, 10, 11, 15, tzinfo=UTC)


def prepared():
    app = service(None)
    result = app.execute("prepare", {"command_id": token_hex(16), "context": context("BTS_CG_YEAR_2", "COURSE", None), "reference": {}})
    data = as_plain(app.prepared[result["preparation_ref"]])
    lineage = data["lineage"]
    meta = ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, lineage["source_run_id"], lineage["source_step_id"], None,
        CorrelationId(lineage["source_request_id"]), Instant(NOW), ActorRef(ActorKind.AGENT, "AG-02"), InvocationStatus.PLANNED)
    return data, meta


def test_snapshot_real_ag02_constructs_exact_untrusted_evidence():
    from backend.adapters.outbound.evidence import p0_prepared_snapshot as bridge
    data, meta = prepared()
    result = bridge.prepared_evidence_items(data, NOW, meta)
    assert len(result) == 1 and result[0].source_ref == data["references"][0]["source_ref"]
    assert result[0].excerpt_or_summary == data["evidence"][result[0].evidence_id]
    assert result[0].checksum_or_version == data["references"][0]["checksum_or_version"]
    assert result[0].authority == {"authority": "NONE"}


@pytest.mark.parametrize("mutation", ["text", "sha", "reference_extra", "reference_missing", "evidence_extra", "empty", "overlong", "duplicate"])
def test_snapshot_identity_and_payload_mutations_refuse(mutation):
    from backend.adapters.outbound.evidence import p0_prepared_snapshot as bridge
    data, meta = prepared()
    ref = data["references"][0]
    if mutation == "text":
        data["evidence"][ref["evidence_id"]] += " changed"
    elif mutation == "sha":
        ref["excerpt_sha256"] = "0" * 64
    elif mutation == "reference_extra":
        ref["authority"] = "OFFICIAL"
    elif mutation == "reference_missing":
        del ref["locator"]
    elif mutation == "evidence_extra":
        data["evidence"]["hidden"] = "unselected"
    elif mutation == "duplicate":
        data["references"].append(copy.deepcopy(ref))
    else:
        data["evidence"][ref["evidence_id"]] = "" if mutation == "empty" else "X" * 4001
    with pytest.raises(ValueError):
        bridge.prepared_evidence_items(data, NOW, meta)


@pytest.mark.parametrize("mutation", ["policy", "goal", "scope", "source", "locator", "candidate"])
def test_snapshot_query_and_content_port_substitution_refuse(mutation):
    from backend.adapters.outbound.evidence import p0_prepared_snapshot as bridge
    data, _ = prepared()
    snapshot = bridge.PreparedEvidenceSnapshot(data, NOW)
    query = bridge.RetrievalQuery("EXACT_PREPARED_REFERENCE_SET_ONLY", {}, snapshot.policy, {}, None, 1)
    if mutation in {"policy", "goal", "scope"}:
        values = dict(search_goal=query.search_goal, scope=query.scope, source_policy=query.source_policy,
            filters=query.filters, required_authority=query.required_authority, max_items=query.max_items)
        values[{"policy": "source_policy", "goal": "search_goal", "scope": "scope"}[mutation]] = {} if mutation == "policy" else ("new goal" if mutation == "goal" else {"more": True})
        with pytest.raises(ValueError):
            snapshot.search(query=bridge.RetrievalQuery(**values), channel=bridge.RetrievalChannel.STRUCTURED)
    else:
        candidate = snapshot.search(query=query, channel=bridge.RetrievalChannel.STRUCTURED).candidates[0]
        request = bridge.DocumentContentRequest("unknown" if mutation == "candidate" else candidate.candidate_id,
            "source:other" if mutation == "source" else candidate.source_ref, "chunk:other" if mutation == "locator" else candidate.locator, snapshot.policy)
        with pytest.raises(ValueError):
            snapshot.fetch(request=request)


def test_security_primitives_preserve_isolation_and_restrict_authority_injection():
    from backend.adapters.outbound.evidence import p0_prepared_snapshot as bridge
    from backend.agent_runtime.security import tool_application as security
    data, meta = prepared()
    labeled = security.label_untrusted_evidence_items(bridge.prepared_evidence_items(data, NOW, meta))
    assert labeled[0].content.label.trust_class.value == "untrusted"
    _, assessment = security.label_untrusted_application_inputs({"gate_decision": "ALLOW"}, content_ref="synthetic",
        forbidden_keys={"gate_decision"}, root_location="synthetic")
    assert assessment.disposition.value == "QUARANTINE"


def test_pure_http_intention_has_no_implicit_application_construction():
    from backend.adapters.inbound.api import p0_creation as api
    calls = []
    def forbidden(*_):
        raise AssertionError("NO_OTHER_OPERATION")
    endpoint = api.P0CreationEndpoint(forbidden, forbidden, [], nonce="SYNTHETIC")
    body = json.dumps({"command_id": token_hex(16), "intention": "Cours"}).encode()
    status, _, raw, _ = endpoint.respond("POST", "/api/v2/p0/intention", body, "SYNTHETIC")
    assert status == 409 and b"P0_INTENTION_NOT_ENABLED" in raw
    endpoint.intention_execute = lambda request: calls.append(request) or {"provider_calls": 0}
    status, _, raw, _ = endpoint.respond("POST", "/api/v2/p0/intention", body, "SYNTHETIC")
    assert status == 200 and len(calls) == 1 and json.loads(raw)["data"]["provider_calls"] == 0


def test_normal_agent_prototype_uses_ag02_and_approved_security_owner(monkeypatch):
    from backend.adapters.outbound.evidence import p0_prepared_snapshot as bridge
    actors = []
    original = bridge.EvidenceAgent.fetch_evidence_item
    def record(self, *, request):
        actors.append(request.request.meta.actor.actor_id)
        return original(self, request=request)
    monkeypatch.setattr(bridge.EvidenceAgent, "fetch_evidence_item", record)
    from backend.adapters.outbound.generation.openai import p0_normal_agents as normal
    data, _ = prepared()
    result = normal.agent_preparation(data, NOW)
    assert actors == ["AG-02"]
    assert result.labeled_evidence[0].evidence_item.source_ref == data["references"][0]["source_ref"]
    assert result.labeled_evidence[0].content.label.trust_class.value == "untrusted"
    assert result.request.evidence_refs == (data["references"][0]["evidence_id"],)


@pytest.mark.parametrize("count", [2, 8])
def test_ag02_snapshot_bounds_deduplicate_channels_and_preserve_every_source(count):
    import hashlib

    from backend.adapters.outbound.evidence import p0_prepared_snapshot as bridge
    data, meta = prepared()
    first = copy.deepcopy(data["references"][0])
    data["references"] = []
    data["evidence"] = {}
    for number in range(count):
        ref = dict(first, evidence_id=f"evidence:{number}", source_ref=f"source:{number}", locator=f"chunk:{number}")
        text = f"Synthetic distinct source {number}."
        ref["excerpt_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        data["references"].append(ref)
        data["evidence"][ref["evidence_id"]] = text
    materialized = bridge.prepared_evidence_items(data, NOW, meta)
    assert len(materialized) == count
    assert {item.evidence_id: item.excerpt_or_summary for item in materialized} == data["evidence"]
    assert all(item.authority == {"authority": "NONE"} for item in materialized)
