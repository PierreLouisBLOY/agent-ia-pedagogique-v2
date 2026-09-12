"""Synthetic end-to-end local publication; the HTTP adapter is invoked without sockets."""
import json
from dataclasses import replace

import pytest

from backend.infrastructure.composition.factories.r3_review_modify import build_r3
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import encoded
from backend.modules.validation_control.contracts.dto.editorial_scope import verify_editorial_scope
from tests.support.r3_fakes import command, harness, run
from tests.unit.test_r3_editorial_corrections import (
    BASELINE,
    CONTRACT_HASH,
    local_command,
    prepared,
    review_for,
)


def editorial_harness():
    conv, original, jobs, prod = harness()
    assert run(conv, original, "assessment-preparations", prod)[0]["state"] == "SUCCEEDED"
    parent = conv.store.r3_bundle(prod.production_ref, prod.version_ref)
    payload = review_for(parent)
    del payload["review_ref"]
    payload.update(overall_assessment="Synthetic editorial observations", coverage=[],
                   limitations=[], evidence_refs_used=[], created_at="2026-01-01T00:00:00+00:00")
    jobs.dispatch = lambda request: payload
    receipt, _ = run(conv, original, "reviews", prod)
    assert receipt["state"] == "SUCCEEDED"
    review = original.service.assessment(prod.production_ref, prod.version_ref)["reviews"][0]
    _, plan, evidence = prepared(parent=parent, review=review, conversation_id=prod.conversation_id)
    enabled = {"value": True}
    local = build_r3(conv, editorial_plan=plan, editorial_evidence=evidence,
                     editorial_authenticate=lambda e: enabled["value"] and e is evidence,
                     editorial_baseline=BASELINE, editorial_contract_sha256=CONTRACT_HASH)
    cmd = local_command(prod.conversation_id, conv.service.snapshot()["revision"], parent, plan)
    return conv, local, jobs, prod, parent, plan, evidence, enabled, cmd


def test_inbound_atomic_publication_replay_revalidation_and_no_review_inheritance():
    conv, local, jobs, prod, parent, plan, evidence, enabled, cmd = editorial_harness()
    before = local.service.assessment(prod.production_ref, prod.version_ref)
    status, raw = local.endpoint.post("modifications", encoded(cmd.body), "synthetic")
    result = json.loads(raw)["data"]
    assert status == 202 and result["state"] == "SUCCEEDED"
    child = conv.store.r3_bundle(prod.production_ref, result["version_ref"])
    scope = conv.store.r3_editorial_scope(prod.production_ref, child.version_ref)
    assert verify_editorial_scope(scope, parent=parent, candidate=child.data)
    assert plan.sha256 in conv.store._r3_consumed_editorial_plans
    assert len(conv.store._versions) == len(conv.store._r3_bundles) == 2
    assert len(conv.store._r3_editorial_scopes) == 1
    assert len(jobs.requests) == 2  # Initial synthetic fixtures only, no local job dispatch.
    assert child.data["lineage"]["source_capability"] is None
    assert conv.store.r3_bundle(prod.production_ref, prod.version_ref).sha256 == parent.sha256
    after = local.service.assessment(prod.production_ref, child.version_ref)
    assert after["review_status"] == "REVIEW_NOT_RUN" and after["reviews"] == []
    assert after["badge"] == "NON VALIDÉE"
    assert len(after["validations"][0]["checks"]) == 16
    assert after["validations"][0]["checks"][15]["status"] == "WARNING"
    assert "editorial_scope" not in after and "receipt" not in repr(after)
    assert local.service.assessment(prod.production_ref, prod.version_ref)["reviews"] == before["reviews"]
    assert local.service.execute(cmd) == result
    conflict = local_command(prod.conversation_id, cmd.body["expected_revision"], parent, plan,
                             command_id=cmd.command_id, review_sha256="f"*64)
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        local.service.execute(conflict)
    child_view = conv.store.read_version(conversation_id=prod.conversation_id,
        production_ref=prod.production_ref, version_ref=child.version_ref)
    checked, _ = run(conv, local, "validations", child_view)
    assert checked["validation"]["overall_status"] == "WARNING"
    assert checked["validation"]["checks"][13]["status"] == "PASS"
    enabled["value"] = False
    checked, _ = run(conv, local, "validations", child_view)
    assert checked["validation"]["checks"][13]["status"] == "FAIL"
    local.service.close()
    assert not verify_editorial_scope(scope, parent=parent, candidate=child.data)
    assert not conv.store._r3_editorial_scopes and not conv.store._r3_consumed_editorial_plans


@pytest.mark.parametrize("fault", [
    "default", "revoked", "baseline", "contract", "review", "plan", "revision",
    "evidence_copy", "foreign_session", "raising_verifier",
])
def test_preconditions_fail_before_reservation(fault):
    conv, local, jobs, prod, parent, plan, evidence, enabled, cmd = editorial_harness()
    if fault == "default":
        local = build_r3(conv)
    elif fault == "revoked":
        enabled["value"] = False
    elif fault in {"baseline", "contract"}:
        local = build_r3(conv, editorial_plan=plan, editorial_evidence=evidence,
            editorial_authenticate=lambda e: e is evidence,
            editorial_baseline="e"*40 if fault == "baseline" else BASELINE,
            editorial_contract_sha256="e"*64 if fault == "contract" else CONTRACT_HASH)
    elif fault == "review":
        conv.store._r3_reviews.clear()
    elif fault in {"evidence_copy", "foreign_session", "raising_verifier"}:
        injected = replace(evidence)
        if fault == "foreign_session":
            injected = replace(evidence, conversation_id="conv:" + "0"*32)
        def verifier(value):
            if fault == "raising_verifier":
                raise RuntimeError("PRIVATE_MARKER")
            return value is evidence
        local = build_r3(conv, editorial_plan=plan, editorial_evidence=injected,
            editorial_authenticate=verifier, editorial_baseline=BASELINE,
            editorial_contract_sha256=CONTRACT_HASH)
    elif fault == "plan":
        cmd = local_command(prod.conversation_id, cmd.body["expected_revision"], parent, plan, plan_sha256="e"*64)
    else:
        cmd = local_command(prod.conversation_id, 1, parent, plan)
    before = (len(conv.store._r3_operations), len(conv.store._versions), conv.service.snapshot()["revision"])
    with pytest.raises(ValueError):
        local.service.execute(cmd)
    assert before == (len(conv.store._r3_operations), len(conv.store._versions), conv.service.snapshot()["revision"])
    assert not conv.store._r3_editorial_scopes and not conv.store._r3_consumed_editorial_plans
    assert len(jobs.requests) == 2


@pytest.mark.parametrize("fault", ["assembler", "before_commit", "forged_scope", "after_commit"])
def test_failure_boundaries_never_publish_partial_state(monkeypatch, fault):
    conv, local, jobs, prod, parent, plan, evidence, enabled, cmd = editorial_harness()
    complete = conv.store.r3_complete
    if fault == "assembler":
        local.service._calculate_locators = lambda *args: ()
    else:
        def inject(op, result, **kwargs):
            if result["state"] == "SUCCEEDED":
                if fault == "before_commit":
                    raise ValueError("SYNTHETIC_PRIVATE_MARKER")
                if fault == "forged_scope":
                    kwargs["editorial_scope"] = replace(kwargs["editorial_scope"])
                complete(op, result, **kwargs)
                if fault == "after_commit":
                    raise ValueError("SYNTHETIC_PRIVATE_MARKER")
            else:
                complete(op, result, **kwargs)
        monkeypatch.setattr(conv.store, "r3_complete", inject)
    result = local.service.execute(cmd)
    success = fault == "after_commit"
    assert result["state"] == ("SUCCEEDED" if success else "FAILED_OUTPUT")
    assert len(conv.store._versions) == len(conv.store._r3_bundles) == (2 if success else 1)
    assert len(conv.store._r3_editorial_scopes) == len(conv.store._r3_consumed_editorial_plans) == int(success)
    assert conv.store.r3_bundle(prod.production_ref, prod.version_ref).sha256 == parent.sha256
    assert local.service.execute(cmd) == result  # No automatic retry after any result.
    assert len(jobs.requests) == 2
    assert "SYNTHETIC_PRIVATE_MARKER" not in repr(local.service.diagnostic(result["operation_ref"]))


def test_concurrent_different_commands_cas_and_single_child():
    from concurrent.futures import ThreadPoolExecutor
    conv, local, jobs, prod, parent, plan, evidence, enabled, cmd = editorial_harness()
    second = local_command(prod.conversation_id, cmd.body["expected_revision"], parent, plan)
    def execute(candidate):
        try:
            return local.service.execute(candidate)["state"]
        except ValueError as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(execute, (cmd, second)))
    assert results.count("SUCCEEDED") == 1
    assert len(conv.store._versions) == len(conv.store._r3_bundles) == 2
    assert len(conv.store._r3_consumed_editorial_plans) == 1
    assert len(jobs.requests) == 2


def test_harden_uses_exact_local_successor_without_relabeling_its_origin():
    from tests.support.r3_fakes import ImmediateJobs
    conv, local, jobs, prod, parent, plan, evidence, enabled, cmd = editorial_harness()
    result = local.service.execute(cmd)
    child = conv.store.r3_bundle(prod.production_ref, result["version_ref"])
    child_view = conv.store.read_version(conversation_id=prod.conversation_id,
        production_ref=prod.production_ref, version_ref=child.version_ref)
    fake = ImmediateJobs()
    local.service._jobs = fake  # Synthetic port; no production provider binding.
    result, _ = run(conv, local, "modifications", child_view)
    assert result["state"] == "SUCCEEDED"
    assert fake.requests[0].revision.base.sha256 == child.sha256
    successor = conv.store.r3_bundle(prod.production_ref, result["version_ref"])
    assert successor.data["lineage"]["parent_bundle_sha256"] == child.sha256
    assert successor.data["lineage"]["source_capability"] == "CAP-G02"
    assert child.data["lineage"]["source_capability"] is None
    assert local.service.assessment(prod.production_ref, successor.version_ref)["reviews"] == []
    with pytest.raises(ValueError):
        local.service.execute(command(conv, local, "modifications", prod))


@pytest.mark.parametrize("fault", ["capacity", "revoked_during_completion", "consumed"])
def test_limits_and_one_plan_identity_remain_closed(monkeypatch, fault):
    conv, local, jobs, prod, parent, plan, evidence, enabled, cmd = editorial_harness()
    if fault == "capacity":
        conv.store._versions.update({("synthetic-extra", str(i)): prod for i in range(2)})
        before = conv.service.snapshot()["revision"]
        with pytest.raises(ValueError, match="SESSION_CAPACITY_REACHED"):
            local.service.execute(cmd)
        assert conv.service.snapshot()["revision"] == before
    elif fault == "revoked_during_completion":
        complete = conv.store.r3_complete
        def revoke(op, result, **kwargs):
            enabled["value"] = False
            return complete(op, result, **kwargs)
        monkeypatch.setattr(conv.store, "r3_complete", revoke)
        assert local.service.execute(cmd)["state"] == "FAILED_OUTPUT"
        assert len(conv.store._versions) == 1
    else:
        conv.store._r3_consumed_editorial_plans.add(plan.sha256)  # Exact replay attack.
        assert local.service.execute(cmd)["state"] == "FAILED_OUTPUT"
        assert len(conv.store._versions) == 1
    assert not conv.store._r3_editorial_scopes
    assert len(jobs.requests) == 2


@pytest.mark.parametrize("failure", [False, True])
def test_no_external_or_job_effect_with_refusal_sentinels(monkeypatch, failure):
    import os
    import socket
    import sqlite3
    import urllib.request

    from backend.infrastructure.config.secrets.provider import EnvironmentProviderSecretResolver

    conv, local, jobs, prod, parent, plan, evidence, enabled, cmd = editorial_harness()
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append("forbidden_effect")
        raise AssertionError("NO_EXTERNAL_EFFECT_ALLOWED")
    for name in ("authorize", "start", "poll"):
        monkeypatch.setattr(local.service._jobs, name, forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(EnvironmentProviderSecretResolver, "resolve", forbidden)
    if failure:
        local.service._calculate_locators = lambda *args: ()
    result = local.service.execute(cmd)
    assert result["state"] == ("FAILED_OUTPUT" if failure else "SUCCEEDED")
    assert attempts == []


@pytest.mark.parametrize("limit", ["commands", "reports", "r2_lease"])
def test_existing_session_limits_and_r2_lease_not_bypassed(limit):
    conv, local, jobs, prod, parent, plan, evidence, enabled, cmd = editorial_harness()
    if limit == "commands":
        conv.store._r3_commands.update({str(i): ("synthetic", "synthetic") for i in range(64)})
    elif limit == "reports":
        key = (prod.production_ref, prod.version_ref)
        existing = conv.store._r3_validations[key][0]
        conv.store._r3_validations[key] = (existing,) * 8
        cmd = command(conv, local, "validations", prod)
    else:
        state = conv.store._state
        from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
        view = as_plain(state.view)
        view["active_generation"] = {"state": "IN_PROGRESS"}
        conv.store._state = replace(state, view=view)
    before = conv.service.snapshot()["revision"]
    with pytest.raises(ValueError, match="SESSION_CAPACITY_REACHED|GENERATION_IN_PROGRESS"):
        local.service.execute(cmd)
    assert conv.service.snapshot()["revision"] == before
    assert len(conv.store._versions) == 1 and not conv.store._r3_editorial_scopes
