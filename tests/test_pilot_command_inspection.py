"""Application reads synthetic retained files and native LOCK without recovery."""
from __future__ import annotations

import copy
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    ENDPOINT,
    HASH_FIELDS,
    MODEL,
    canonical,
    sha,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
    P0ContinuityProductLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_reader import (
    ValidatedUnknownOff,
)
from backend.adapters.outbound.persistence import p0_pilot_incident as incident_module
from backend.infrastructure.composition.factories import (
    p0_pilot_command_inspection as composition_module,
)
from backend.infrastructure.composition.factories.p0_pilot_command_inspection import (
    P0PilotCommandInspectionComposition,
)
from backend.infrastructure.composition.factories.p0_pilot_on_demand_contract import (
    DOCUMENTS,
    RECOVERY_OPERATION,
    derive,
    projection,
)

NOW = datetime(2026, 10, 23, 0, tzinfo=UTC)


def fixture(tmp_path, monkeypatch):
    roots = {name: tmp_path / name for name in ("confirmation", "documents", "receipts", "config")}
    for root in roots.values():
        root.mkdir()
    body = b"SYNTHETIC_ONLY_NEVER_SENT"
    candidate = sha(body)
    monkeypatch.setattr(incident_module, "CANDIDATE", candidate)
    monkeypatch.setattr(composition_module, "CANDIDATE", candidate)
    campaign, namespace = "a" * 64, "b" * 64
    receipt = P0NormalReceipt(roots["receipts"], namespace)
    old_permission = {"permission_namespace_sha256": campaign,
        "receipt_root_sha256": receipt.root_sha256}
    original_sha = sha(canonical(old_permission))
    lock_raw = canonical({"permission_sha256": original_sha})
    lock_path = roots["receipts"] / f"{campaign}.P1.LOCK"
    lock_path.write_bytes(lock_raw)
    chain = SimpleNamespace(root=SimpleNamespace(permission_sha256=original_sha),
        current=SimpleNamespace(permission=old_permission, permission_sha256=original_sha,
            envelope={"profile": {"receipt_root": str(roots["receipts"])}}),
        manifest={"campaign_namespace_sha256": campaign, "root_lock_sha256": sha(lock_raw)})
    historical = cast(ValidatedUnknownOff, SimpleNamespace(chain=chain))

    def publish(root, name, value):
        path = root / name
        raw = canonical(value)
        path.write_bytes(raw)
        return {"path": str(path), "sha256": sha(raw)}

    parent_command = incident_module.COMMAND
    prior_pin = publish(roots["documents"], f"p0-derived.{parent_command}.permission.json", old_permission)
    parent_pending = {"schema": "P1-PILOT-CONFIRMATION-PENDING-1.0",
        "command_id": parent_command, "recipe_sha256": "c" * 64,
        "normal_preview_sha256": "d" * 64, "permission_sha256": prior_pin["sha256"],
        "stable_preview_sha256": "e" * 64,
        "issued_at_utc": (NOW - timedelta(hours=3)).isoformat(),
        "expires_at_utc": (NOW - timedelta(hours=2)).isoformat(),
        **{key + "_sha256": "1" * 64 for key in ("decision", "envelope", "authority", "effect")},
        "transfer_accepted": True, "cost_bound_accepted": True,
        "double_execution_cost_risk_accepted": True}
    parent_pending_pin = publish(roots["confirmation"],
        f"p0-confirmation.{'c' * 64}.{parent_command}.PENDING.json", parent_pending)
    parent_slot = {"command_id": parent_command, "preview_sha256": "d" * 64,
        "permission_sha256": prior_pin["sha256"], "request_sha256": candidate,
        "namespace_sha256": "e" * 64, "reserved_usd": "0.1237945",
        "grant_sha256": "f" * 64, "preflight_sha256": "1" * 64}
    parent_slot_pin = publish(roots["receipts"], f"{campaign}.P1.{'d' * 64}.json", parent_slot)
    common = {key: parent_slot[key] for key in ("namespace_sha256", "grant_sha256", "preflight_sha256")}
    parent_reserved_pin = publish(roots["receipts"], f"{'e' * 64}.RESERVED.json",
        {**common, "schema": "P0-NORMAL-TECHNICAL-RECEIPT-1.0", "state": "RESERVED",
            "reserved_usd": "0.1237945"})
    parent_dispatch_pin = publish(roots["receipts"], f"{'e' * 64}.DISPATCH.json",
        {**common, "schema": "P0-NORMAL-DISPATCH-CAPTURE-1.0", "request_sha256": candidate,
            "body": body.decode(), "preflight": {"cost_bound_usd": "0.1237945"}})
    sources = {"pending": parent_pending_pin["sha256"], "slot": parent_slot_pin["sha256"],
        "reserved": parent_reserved_pin["sha256"], "dispatch": parent_dispatch_pin["sha256"]}
    parent = incident_module.P0PilotIncidentDisposition(confirmation_root=roots["confirmation"],
        receipt_root=roots["receipts"], documents_root=roots["documents"], sources=sources)
    incident = {"sources": sources,
        "disposition": {"path": str(parent.path), "sha256": sha(canonical(parent.proposed()))}}
    normal = {"schema": "P0-NORMAL-PROFILE-1.0", "receipt_root": str(roots["receipts"])}
    normal_desc = publish(roots["config"], "normal.json", normal)
    permission = {key: "2" * 64 for key in HASH_FIELDS}
    permission.update(permission_namespace_sha256=campaign, receipt_root_sha256=receipt.root_sha256,
        baseline_commit="1" * 40, profile_sha256=normal_desc["sha256"],
        owner_decision_sha256="3" * 64, issued_at_utc="2000-01-01T00:00:00+00:00",
        expires_at_utc="2000-01-01T01:00:00+00:00", source_admission_manifest_sha256="4" * 64,
        institutional_catalog_sha256="5" * 64)
    effect = {"request_sha256": candidate, "preparation_sha256": "6" * 64,
        "context_sha256": "7" * 64, "reference_set_sha256": "8" * 64,
        "parent_unknown_request_sha256": incident_module.PARENT,
        "approved_cost_bound_usd": "0.1237945", "incident": incident,
        "normal_profile": {}, "authority": {}}
    for key in ("request_sha256", "preparation_sha256", "context_sha256", "reference_set_sha256"):
        permission[key] = effect[key]
    # The grant namespace is an operation identity, not the campaign prefix.
    permission.pop("namespace_sha256")
    templates = {"permission": permission,
        "decision": {"profile_sha256": normal_desc["sha256"], "permission_policy_sha256": "9" * 64},
        "envelope": {"profile": normal, "permission": {}, "decision": {}},
        "authority": {"operation": RECOVERY_OPERATION, "permission_sha256": "a" * 64,
            "issued_at_utc": "2000-01-01T00:00:00+00:00", "expires_at_utc": "2000-01-01T01:00:00+00:00"},
        "effect": effect}
    recipe = {"schema": "P1-PILOT-CONFIRMATION-RECIPE-1.0", "operation": RECOVERY_OPERATION,
        "template_projection_sha256": sha(canonical(projection(templates))),
        "normal_profile_sha256": normal_desc["sha256"],
        **{key: effect[key] for key in ("request_sha256", "preparation_sha256", "context_sha256",
            "reference_set_sha256", "parent_unknown_request_sha256")},
        **{key: permission[key] for key in ("tariff_sha256", "tokenizer_manifest_sha256",
            "source_admission_manifest_sha256", "institutional_catalog_sha256")},
        "financial_admission_sha256": "b" * 64, "approved_cost_bound_usd": "0.1237945",
        "duration_seconds": 3600, "max_calls": 1, "retry": 0, "fallback": "NONE",
        "incident_disposition_sha256": incident["disposition"]["sha256"],
        "incident_command_id": parent_command}
    profile = {"schema": "P1-PILOT-ON-DEMAND-RECOVERY-1.0", "status": "OWNER_ADOPTED_EXACT_STABLE_PROFILE",
        "recipe": publish(roots["config"], "recipe.json", recipe), "normal_profile": normal_desc,
        "templates": {key: publish(roots["config"], key + ".json", templates[key]) for key in DOCUMENTS},
        "incident": incident, "confirmation_root": str(roots["confirmation"]),
        "documents_root": str(roots["documents"]), "candidate_scope_sha256": "c" * 64,
        "read_scope_sha256": "d" * 64, "financial_admission": {}, "frozen_inventory": {},
        "historical_diagnostics": {}}
    profile_desc = publish(roots["config"], "startup.json", profile)
    command = "a" * 32
    paths = {key: roots["documents"] / f"p0-derived.{command}.{key}.json" for key in DOCUMENTS}
    docs = derive(recipe, templates, normal, at=NOW, paths=paths)
    docs_desc = {key: publish(roots["documents"], paths[key].name, docs[key]) for key in DOCUMENTS}
    pending = {"schema": "P1-PILOT-CONFIRMATION-PENDING-1.0", "recipe_sha256": sha(canonical(recipe)),
        "command_id": command, "stable_preview_sha256": "e" * 64, "normal_preview_sha256": "f" * 64,
        "issued_at_utc": docs["authority"]["issued_at_utc"], "expires_at_utc": docs["authority"]["expires_at_utc"],
        **{key + "_sha256": docs_desc[key]["sha256"] for key in DOCUMENTS},
        "transfer_accepted": True, "cost_bound_accepted": True, "double_execution_cost_risk_accepted": True}
    pending_desc = publish(roots["confirmation"],
        f"p0-confirmation.{pending['recipe_sha256']}.{command}.PENDING.json", pending)
    grant = {key: "2" * 64 for key in HASH_FIELDS}
    grant.update({key: docs["permission"][key] for key in HASH_FIELDS & docs["permission"].keys()})
    grant.update(schema="P0-NORMAL-CREATE-GRANT-1.0", operation="CREATE", baseline_commit="1" * 40,
        request_bytes=len(body), namespace_sha256=namespace,
        issued_at_utc=(NOW + timedelta(seconds=1)).isoformat(),
        expires_at_utc=pending["expires_at_utc"], provider="OPENAI", model=MODEL, endpoint=ENDPOINT,
        reasoning="low", tier="default", max_output_tokens=4096, max_calls=1, count_calls=0,
        review_calls=0, modify_calls=0, retry=0, fallback="NONE", parallelism=1,
        ceiling_usd="0.1237945", live_authorized=True, transfer_authorized=True)
    proof = {"cost_bound_usd": "0.1237945", "request_sha256": candidate, "request_bytes": len(body)}
    slot = {"schema": "P0-PRODUCT-BUDGET-SLOT-1.0", "command_id": command,
        "preview_sha256": pending["normal_preview_sha256"], "permission_sha256": pending["permission_sha256"],
        "grant": grant, "grant_sha256": sha(canonical(grant)), "namespace_sha256": namespace,
        "request_sha256": candidate, "preflight_sha256": sha(canonical(proof)), "reserved_usd": "0.1237945"}
    slot_desc = publish(roots["receipts"], f"{campaign}.P1.{pending['normal_preview_sha256']}.json", slot)
    receipt.reserve(grant=grant, dispatch={"synthetic": True}, body=body, preflight=proof)
    composition = P0PilotCommandInspectionComposition(profile_path=Path(profile_desc["path"]),
        expected_sha256=profile_desc["sha256"], historical_loader=lambda: historical,
        clock=lambda: NOW)
    native_lock = P0ContinuityProductLedger(root=roots["receipts"], permission=old_permission,
        chain_loader=lambda: cast(object, chain), broker_identity=object(), clock=lambda: NOW)
    return SimpleNamespace(composition=composition, roots=roots, pending=pending,
        pending_path=Path(pending_desc["path"]), slot_path=Path(slot_desc["path"]),
        lock=native_lock, lock_path=lock_path, command=command)


def snapshot(root):
    files = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    if output := os.environ.get("V2_309_SYNTHETIC_FINGERPRINTS"):
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"case": root.name, "files": len(files),
                "snapshot_sha256": sha(canonical({key: sha(raw) for key, raw in files.items()}))}) + "\n")
    return files


def test_pending_reserved_dispatch_read_through_application_without_change(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert result["command_id"] == case.command
    assert result["right_status"] == "CONSUMED_AT_PENDING_NO_NEW_RIGHT"
    assert result["provider_departure_status"] == "NOT_ESTABLISHED"
    assert result["actual_billed_cost_status"] == "NOT_ESTABLISHED"
    assert result["reserved_usd"] == "0.1237945"
    assert {row["state"] for row in result["receipts"]} == {"RESERVED", "DISPATCH"}
    assert result["parent_406a"]["command_id"] == incident_module.COMMAND
    assert result["provider_calls"] == result["ledger_mutations"] == 0
    assert "SYNTHETIC_ONLY_NEVER_SENT" not in str(result)
    assert str(tmp_path) not in str(result)
    assert snapshot(tmp_path) == before
    assert case.composition.inspect() == result


def test_changed_pending_document_link_is_refused_without_write(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    changed = copy.deepcopy(case.pending)
    changed["permission_sha256"] = "0" * 64
    case.pending_path.write_bytes(canonical(changed))
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="AF_MAPPING_CORRUPTION"):
        case.composition.inspect()
    assert snapshot(tmp_path) == before


def test_busy_original_lock_is_refused_without_write(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    before = snapshot(tmp_path)
    with case.lock.locked():
        with pytest.raises(ValueError, match="AF_CONCURRENCY"):
            case.composition.inspect()
    assert snapshot(tmp_path) == before


def test_missing_original_lock_is_never_created(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    case.lock_path.unlink()
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="AF_MAPPING_CORRUPTION"):
        case.composition.inspect()
    assert not case.lock_path.exists()
    assert snapshot(tmp_path) == before


def test_revocation_is_observed_without_clearing_pending_or_creating_right(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    path = case.roots["confirmation"] / f"p0-confirmation.{case.pending['recipe_sha256']}.REVOKED.json"
    path.write_bytes(canonical({"schema": "P1-PILOT-REVOKED-1.0",
        "recipe_sha256": case.pending["recipe_sha256"], "revoked_at_utc": NOW.isoformat(),
        "operator": "SYNTHETIC_OWNER"}))
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert {row["state"] for row in result["confirmation_receipts"]} == {"PENDING", "REVOKED"}
    assert result["right_status"] == "CONSUMED_AT_PENDING_NO_NEW_RIGHT"
    assert snapshot(tmp_path) == before


def test_expired_no_slot_retains_consumed_pending_without_zero_cost_claim(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    slot = json.loads(case.slot_path.read_bytes())
    case.slot_path.unlink()
    for state in ("RESERVED", "DISPATCH"):
        (case.roots["receipts"] / f"{slot['namespace_sha256']}.{state}.json").unlink()
    path = case.roots["confirmation"] / (
        f"p0-confirmation.{case.pending['recipe_sha256']}.{case.command}.EXPIRED_NO_SLOT.json")
    path.write_bytes(canonical({"schema": "P1-PILOT-CONFIRMATION-EXPIRED-NO-SLOT-1.0",
        "recipe_sha256": case.pending["recipe_sha256"], "command_id": case.command,
        "pending_sha256": sha(case.pending_path.read_bytes()),
        "expired_at_utc": (NOW + timedelta(hours=1)).isoformat(), "state": "EXPIRED_NO_SLOT"}))
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert {row["state"] for row in result["confirmation_receipts"]} == {"PENDING", "EXPIRED_NO_SLOT"}
    assert result["reserved_usd"] is None
    assert result["right_status"] == "CONSUMED_AT_PENDING_NO_NEW_RIGHT"
    assert result["actual_billed_cost_status"] == "NOT_ESTABLISHED"
    assert snapshot(tmp_path) == before


def test_incomplete_result_is_observed_without_success_or_recovery(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    slot = json.loads(case.slot_path.read_bytes())
    capture = json.loads((case.roots["receipts"] / f"{slot['namespace_sha256']}.DISPATCH.json").read_bytes())
    result_path = case.roots["receipts"] / f"{slot['namespace_sha256']}.RESULT.json"
    result_path.write_bytes(canonical({"schema": "P0-NORMAL-CONFIRMED-RESULT-1.0",
        "grant_sha256": slot["grant_sha256"], "request_sha256": slot["request_sha256"],
        "dispatch_sha256": capture["dispatch_sha256"], "response_status": "incomplete",
        "output_text": None, "usage": {key: None for key in ("input_tokens", "cached_input_tokens",
            "output_tokens", "reasoning_tokens", "total_tokens", "cache_write_input_tokens")}}))
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert result["response_artifact_present"] is True
    assert result["response_status"] == "incomplete"
    assert result["right_status"] == "CONSUMED_AT_PENDING_NO_NEW_RIGHT"
    assert result["actual_billed_cost_status"] == "NOT_ESTABLISHED"
    assert snapshot(tmp_path) == before
