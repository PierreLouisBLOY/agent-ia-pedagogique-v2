"""Synthetic histories only; real Application reader, derivation and native LOCK."""
import copy
import json
from datetime import timedelta
from pathlib import Path

import pytest
from test_pilot_command_inspection import NOW, fixture, snapshot

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.persistence import p0_pilot_retained_child as child_module
from backend.infrastructure.composition.factories.p0_pilot_command_inspection import (
    P0PilotCommandInspectionComposition,
)
from backend.infrastructure.composition.factories.p0_pilot_on_demand_contract import (
    DOCUMENTS,
    RETAINED_OPERATION,
    derive,
    projection,
)


def retained(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    config = case.roots["config"]
    profile = json.loads((config / "startup.json").read_bytes())
    old = case.composition._validate()
    old.parent.path.write_bytes(canonical(old.parent.proposed()))
    child_command = child_module.CHILD_COMMAND
    past = NOW - timedelta(hours=3)
    monkeypatch.setattr(child_module, "OBSERVED_END", (NOW - timedelta(hours=1)).isoformat())
    child_recipe = child_module.CHILD_RECIPE
    slot = json.loads(case.slot_path.read_bytes())
    grant = copy.deepcopy(slot["grant"])
    grant.update(namespace_sha256="9" * 64, issued_at_utc=past.isoformat(),
        expires_at_utc=(past + timedelta(hours=1)).isoformat())
    pnd = copy.deepcopy(case.pending)
    pnd.update(command_id=child_command, recipe_sha256=child_recipe,
        normal_preview_sha256="8" * 64, issued_at_utc=grant["issued_at_utc"],
        expires_at_utc=grant["expires_at_utc"])
    for kind in DOCUMENTS:
        doc = json.loads((case.roots["documents"] / f"p0-derived.{case.command}.{kind}.json").read_bytes())
        if kind == "authority":
            doc["parent_unknown_request_sha256"] = old.recipe["parent_unknown_request_sha256"]
        raw = canonical(doc)
        pnd[kind + "_sha256"] = sha(raw)
        (case.roots["documents"] / f"p0-derived.{child_command}.{kind}.json").write_bytes(raw)
    old_pending = case.roots["confirmation"] / f"p0-confirmation.{child_recipe}.{child_command}.PENDING.json"
    old_pending.write_bytes(canonical(pnd))
    child_slot = {**slot, "command_id": child_command, "preview_sha256": pnd["normal_preview_sha256"],
        "permission_sha256": pnd["permission_sha256"], "grant": grant,
        "grant_sha256": sha(canonical(grant)), "namespace_sha256": grant["namespace_sha256"]}
    campaign = json.loads((config / "permission.json").read_bytes())["permission_namespace_sha256"]
    child_slot_path = case.roots["receipts"] / f"{campaign}.P1.{pnd['normal_preview_sha256']}.json"
    child_slot_path.write_bytes(canonical(child_slot))
    sources = {"pending": sha(old_pending.read_bytes()), "slot": sha(child_slot_path.read_bytes())}
    monkeypatch.setattr(child_module, "CHILD_SOURCES", sources)
    monkeypatch.setattr(child_module, "PARENT_DISPOSITION", old.parent.expected_sha256)
    child = child_module.P0PilotRetainedChildDisposition(parent=old.parent, sources=sources)
    child.expected_sha256 = sha(canonical(child.proposed()))
    child.path.write_bytes(canonical(child.proposed()))
    profile["incident"]["retained_child"] = {
        "disposition": {"path": str(child.path), "sha256": child.expected_sha256}, "sources": sources}
    templates = {key: json.loads((config / (key + ".json")).read_bytes()) for key in DOCUMENTS}
    templates["effect"].update(schema="P1-PILOT-RETAINED-CHILD-EFFECT-STARTUP-1.0",
        incident=profile["incident"])
    templates["authority"]["operation"] = RETAINED_OPERATION
    recipe = dict(old.recipe)
    recipe.update(schema="P1-PILOT-CONFIRMATION-RECIPE-1.1", operation=RETAINED_OPERATION,
        right_id=child_module.RIGHT_ID, incident_command_id=child_command,
        incident_disposition_sha256=child.expected_sha256,
        prior_incident_disposition_sha256=old.parent.expected_sha256,
        template_projection_sha256=sha(canonical(projection(templates))))
    recipe_path = config / "recipe.json"
    recipe_path.write_bytes(canonical(recipe))
    profile["recipe"]["sha256"] = sha(recipe_path.read_bytes())
    for key in DOCUMENTS:
        path = config / (key + ".json")
        path.write_bytes(canonical(templates[key]))
        profile["templates"][key]["sha256"] = sha(path.read_bytes())
    profile["schema"] = "P1-PILOT-ON-DEMAND-RETAINED-CHILD-1.0"
    case.pending_path.unlink()
    case.pending.update(schema="P1-PILOT-CONFIRMATION-PENDING-1.1",
        recipe_sha256=sha(canonical(recipe)), right_id=child_module.RIGHT_ID)
    case.pending_path = case.roots["confirmation"] / (
        f"p0-confirmation.{case.pending['recipe_sha256']}.{case.command}.PENDING.json")
    normal = json.loads((config / "normal.json").read_bytes())
    paths = {key: case.roots["documents"] / f"p0-derived.{case.command}.{key}.json" for key in DOCUMENTS}
    docs = derive(recipe, templates, normal, at=NOW, paths=paths)
    for key in DOCUMENTS:
        paths[key].write_bytes(canonical(docs[key]))
        case.pending[key + "_sha256"] = sha(paths[key].read_bytes())
    case.pending_path.write_bytes(canonical(case.pending))
    case.profile = profile
    case.config = config
    case.child = child
    case.historical = case.composition._historical
    case.composition = recompose(case)
    return case


def recompose(case, *, command=None):
    path = case.config / "startup.json"
    path.write_bytes(canonical(case.profile))
    return P0PilotCommandInspectionComposition(profile_path=path,
        expected_sha256=sha(path.read_bytes()), historical_loader=case.historical,
        clock=lambda: NOW, command_id=command or case.command)


def test_retained_read_is_closed_readonly_and_does_not_count_receipts_as_more_slots(tmp_path, monkeypatch):
    case = retained(tmp_path, monkeypatch)
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert result["schema"] == "P1-PILOT-COMMAND-METADATA-1.1"
    assert result["command_id"] == case.command
    assert result["right_id"] == child_module.RIGHT_ID
    assert result["right_status"] == "CONSUMED_AT_PENDING_NO_NEW_RIGHT"
    assert result["parent_2f1e"]["command_id"] == child_module.CHILD_COMMAND
    assert "reserved_sha256" not in result["parent_2f1e"]
    assert result["reserved_usd"] == "0.1237945"
    assert {x["state"] for x in result["receipts"]} == {"RESERVED", "DISPATCH"}
    assert result["provider_departure_status"] == "NOT_ESTABLISHED"
    assert result["response_metadata"] is None
    assert result["provider_calls"] == result["ledger_mutations"] == 0
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("status", ["completed", "incomplete", "failed", "refused"])
def test_linked_response_is_observed_without_recovery_or_output_disclosure(tmp_path, monkeypatch, status):
    case = retained(tmp_path, monkeypatch)
    slot = json.loads(case.slot_path.read_bytes())
    capture = json.loads((case.roots["receipts"] / f"{slot['namespace_sha256']}.DISPATCH.json").read_bytes())
    path = case.roots["receipts"] / f"{slot['namespace_sha256']}.RESULT.json"
    output = "SYNTHETIC PRIVATE RESULT NEVER SENT"
    path.write_bytes(canonical({"schema": "P0-NORMAL-CONFIRMED-RESULT-1.0",
        "grant_sha256": slot["grant_sha256"], "request_sha256": slot["request_sha256"],
        "dispatch_sha256": capture["dispatch_sha256"], "response_status": status,
        "output_text": output, "usage": {key: 0 for key in ("input_tokens", "cached_input_tokens",
            "output_tokens", "reasoning_tokens", "total_tokens", "cache_write_input_tokens")}}))
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert result["provider_departure_status"] == "RESPONSE_ARTIFACT_OBSERVED"
    assert result["response_metadata"]["result_sha256"] == sha(path.read_bytes())
    assert result["response_metadata"]["output_text_sha256"] == sha(output.encode())
    assert result["response_status"] == status
    assert output not in str(result)
    assert result["actual_billed_cost_status"] == "NOT_ESTABLISHED"
    assert snapshot(tmp_path) == before


def test_no_pending_does_not_imply_new_right_or_non_send(tmp_path, monkeypatch):
    case = retained(tmp_path, monkeypatch)
    case.pending_path.unlink()
    case.child.path.unlink()  # May not have been published before a local exception.
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert result["state"] == "NO_PENDING_OBSERVED_NO_REPLAY"
    assert result["command_id"] == case.command
    assert result["right_status"] == "NOT_ESTABLISHED_NO_NEW_RIGHT"
    assert result["pending_sha256"] is result["issued_at_utc"] is result["reserved_usd"] is None
    assert result["parent_2f1e"]["disposition_sha256"] is None
    assert result["provider_departure_status"] == "NOT_ESTABLISHED"
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("kind", ["missing_right", "wrong_right", "wrong_recipe", "wrong_branch", "wrong_command", "legacy_schema", "downgrade"])
def test_divergent_pending_never_becomes_absence_or_success(tmp_path, monkeypatch, kind):
    case = retained(tmp_path, monkeypatch)
    changed = dict(case.pending)
    if kind == "missing_right":
        changed.pop("right_id")
    elif kind == "wrong_right":
        changed["right_id"] = "0" * 64
    elif kind in {"wrong_recipe", "wrong_branch"}:
        changed["recipe_sha256"] = "9" * 64
        if kind == "wrong_branch":
            case.pending_path.unlink()
            case.pending_path = case.roots["confirmation"] / (
                f"p0-confirmation.{'9' * 64}.{case.command}.PENDING.json")
    elif kind == "wrong_command":
        changed["command_id"] = "9" * 32
    else:
        changed["schema"] = "P1-PILOT-CONFIRMATION-PENDING-1.0"
        if kind == "downgrade":
            changed.pop("right_id")
    case.pending_path.write_bytes(canonical(changed))
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="AF_MAPPING_CORRUPTION"):
        case.composition.inspect()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("code", ["P0_NORMAL_PREFLIGHT_CHANGED", None])
def test_existing_failure_diagnostic_is_read_only_and_cause_bounded(tmp_path, monkeypatch, code):
    case = retained(tmp_path, monkeypatch)
    slot = json.loads(case.slot_path.read_bytes())
    path = case.roots["receipts"] / f"p0-diagnostic.{slot['namespace_sha256']}.json"
    document = {"schema": "P0-NORMAL-FAILURE-DIAGNOSTIC-1.0",
        "namespace_sha256": slot["namespace_sha256"], "grant_sha256": slot["grant_sha256"],
        "request_sha256": slot["request_sha256"], "preflight_sha256": slot["preflight_sha256"],
        "timestamp_utc": NOW.isoformat(), "provider_attempts": 0,
        "stage": "PREFLIGHT_RECHECK", "code_source": "LOCAL_POLICY" if code else None,
        "technical_code": code, "outcome_marker": "UNKNOWN", "marker_recorded": False}
    path.write_bytes(canonical(document))
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert result["failure_evidence"] == {
        "state": "VERIFIED", "sha256": sha(path.read_bytes()), "document": document}
    assert result["provider_departure_status"] == "NOT_ESTABLISHED"
    assert snapshot(tmp_path) == before
    from backend.modules.work_orchestration.contracts.dto.p1_pilot_command_inspection import (
        pilot_command_projection,
    )
    projected = {**result, "schema": "P0-PILOT-COMMAND-INSPECTION-1.1"}
    for source, code_value, stage, attempts, marker in (
            ("LOCAL_POLICY", "ARBITRARY_UPPERCASE_TEXT", "PREFLIGHT_RECHECK", 0, "UNKNOWN"),
            ("OPENAI_TRANSPORT", "ARBITRARY_UPPERCASE_TEXT", "PREFLIGHT_RECHECK", 0, "UNKNOWN"),
            ("LOCAL_FILESYSTEM", "ARBITRARY_UPPERCASE_TEXT", "PREFLIGHT_RECHECK", 0, "UNKNOWN"),
            (None, None, "PREFLIGHT_RECHECK", 1, "UNKNOWN"),
            (None, None, "CONTENT_PARSE", 1, "UNKNOWN")):
        bad = copy.deepcopy(projected)
        diag = bad["failure_evidence"]["document"]
        diag.update(code_source=source, technical_code=code_value, stage=stage,
            provider_attempts=attempts, outcome_marker=marker)
        bad["failure_evidence"]["sha256"] = sha(canonical(diag))
        with pytest.raises(ValueError, match="P1_PILOT_INSPECTION_DIAGNOSTIC"):
            pilot_command_projection(bad)


@pytest.mark.parametrize("change", ["expiry_appears", "disposition_disappears", "unqualified_diag_changes"])
def test_late_change_of_presence_or_pin_is_refused(tmp_path, monkeypatch, change):
    case = retained(tmp_path, monkeypatch)
    slot = json.loads(case.slot_path.read_bytes())
    diagnostic_path = case.roots["receipts"] / f"p0-diagnostic.{slot['namespace_sha256']}.json"
    if change == "unqualified_diag_changes":
        (case.roots["receipts"] / f"{slot['namespace_sha256']}.DISPATCH.json").unlink()
        diagnostic_path.write_bytes(canonical({}))
    from backend.adapters.outbound.persistence.p0_pilot_command_reader import P0PilotCommandReader
    original = P0PilotCommandReader._parents
    changed = False

    def mutate_after_read(reader, loaded, **kwargs):
        nonlocal changed
        result = original(reader, loaded, **kwargs)
        if not changed:
            changed = True
            if change == "expiry_appears":
                path = case.roots["confirmation"] / (
                    f"p0-confirmation.{case.pending['recipe_sha256']}.{case.command}.EXPIRED_NO_SLOT.json")
                path.write_bytes(canonical({"schema": "P1-PILOT-CONFIRMATION-EXPIRED-NO-SLOT-1.0",
                    "recipe_sha256": case.pending["recipe_sha256"], "command_id": case.command,
                    "pending_sha256": sha(case.pending_path.read_bytes()),
                    "expired_at_utc": (NOW + timedelta(hours=1)).isoformat(), "state": "EXPIRED_NO_SLOT"}))
            elif change == "disposition_disappears":
                case.child.path.unlink()
            else:
                diagnostic_path.write_bytes(canonical({"changed": True}))
        return result
    monkeypatch.setattr(P0PilotCommandReader, "_parents", mutate_after_read)
    with pytest.raises(ValueError):
        case.composition.inspect()
    assert changed


def test_malformed_legacy_diagnostic_remains_outside_legacy_scope(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    slot = json.loads(case.slot_path.read_bytes())
    (case.roots["receipts"] / f"p0-diagnostic.{slot['namespace_sha256']}.json").write_bytes(b"not-json")
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert result["schema"] == "P1-PILOT-COMMAND-METADATA-1.0"
    assert "failure_evidence" not in result
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("kind", ["status", "schema", "sha", "source", "target", "lineage", "command", "missing_command"])
def test_composition_refuses_non_adopted_or_wrong_bindings(tmp_path, monkeypatch, kind):
    case = retained(tmp_path, monkeypatch)
    if kind == "status":
        case.profile["status"] = "CANDIDATE"
    elif kind == "schema":
        case.profile["schema"] = "P1-PILOT-ON-DEMAND-RECOVERY-1.0"
    elif kind == "sha":
        case.profile["normal_profile"]["sha256"] = "0" * 64
    elif kind == "source":
        case.profile["incident"]["retained_child"]["sources"]["slot"] = "0" * 64
    elif kind == "target":
        case.profile["confirmation_root"] = str(tmp_path)
    elif kind == "lineage":
        case.profile["incident"]["retained_child"]["disposition"]["sha256"] = "0" * 64
    before = snapshot(tmp_path)
    def composition():
        if kind in {"command", "missing_command"}:
            return P0PilotCommandInspectionComposition(
                profile_path=case.config / "startup.json",
                expected_sha256=sha((case.config / "startup.json").read_bytes()),
                historical_loader=case.historical,
                command_id="invalid" if kind == "command" else None)
        return recompose(case)
    with pytest.raises(ValueError):
        composition()
    # recompose only writes the synthetic selected profile; inspection never writes.
    if kind in {"command", "missing_command"}:
        assert snapshot(tmp_path) == before


def test_other_command_with_same_right_is_refused(tmp_path, monkeypatch):
    case = retained(tmp_path, monkeypatch)
    other = recompose(case, command="1" * 32)
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="AF_MAPPING_CORRUPTION"):
        other.inspect()
    assert snapshot(tmp_path) == before


def test_retained_revocation_is_observed_without_mutation(tmp_path, monkeypatch):
    case = retained(tmp_path, monkeypatch)
    path = case.roots["confirmation"] / f"p0-confirmation.{child_module.RIGHT_ID}.REVOKED.json"
    path.write_bytes(canonical({"schema": "P1-PILOT-REVOKED-1.0",
        "recipe_sha256": case.pending["recipe_sha256"], "right_id": child_module.RIGHT_ID,
        "revoked_at_utc": NOW.isoformat(), "operator": "SYNTHETIC_OWNER"}))
    before = snapshot(tmp_path)
    result = case.composition.inspect()
    assert {x["state"] for x in result["confirmation_receipts"]} == {"PENDING", "REVOKED"}
    assert snapshot(tmp_path) == before


def test_real_modules_and_no_effect_entry_points(tmp_path, monkeypatch):
    case = retained(tmp_path, monkeypatch)
    import backend.adapters.outbound.persistence.p0_pilot_command_reader as reader
    from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
    from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
    from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
        P0ContinuityProductLedger,
    )
    from backend.adapters.outbound.persistence.p0_pilot_confirmation import P0PilotConfirmationStore
    from backend.adapters.outbound.persistence.p0_pilot_incident import P0PilotIncidentDisposition
    from backend.infrastructure.composition.factories import (
        p0_normal_profile,
        p0_pilot_on_demand_finalizer,
    )
    from backend.infrastructure.composition.factories.p0_pilot_on_demand_finalizer import (
        P0PilotOnDemandFinalizer,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Effect or secret port called by inspection")
    for cls, method in ((P0PilotConfirmationStore, "begin"), (P0PilotConfirmationStore, "revoke"),
            (P0PilotConfirmationStore, "_publish"), (P0PilotIncidentDisposition, "publish"),
            (P0PilotOnDemandFinalizer, "execute"), (P0NormalReceipt, "reserve"),
            (P0NormalReceipt, "publish"), (P0ContinuityProductLedger, "reserve"),
            (NormalP0GenerationAdapter, "generate"), (NormalP0GenerationAdapter, "recover_confirmed")):
        monkeypatch.setattr(cls, method, forbidden)
    monkeypatch.setattr(p0_normal_profile, "require_openai_environment_key", forbidden)
    monkeypatch.setattr(p0_pilot_on_demand_finalizer, "require_openai_environment_key", forbidden)
    assert Path(reader.__file__).resolve() == (
        Path(__file__).resolve().parents[1]
        / "backend/adapters/outbound/persistence/p0_pilot_command_reader.py"
    )
    before = snapshot(tmp_path)
    case.composition.inspect()
    assert snapshot(tmp_path) == before
