"""Declared synthetic metadata/adoption only; no provider or runtime store."""
import copy
from datetime import UTC, datetime

import pytest

from backend.adapters.outbound.generation.openai import p0_product_unknown_off_contract as C
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import OriginProof
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    BoundChainV2,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionView,
)
from backend.modules.work_orchestration.contracts.dto.p1_unknown_off_inspection import FIELDS
from tests.unit.test_p0_normal_policy import NOW, fixture, preflight


def descriptor(name, pin="a" * 64):
    return {"path": "C:/SYNTHETIC-ONLY/" + name, "sha256": pin}


def disposition():
    target = {k: "a" * 64 for k in C.TARGET_FIELDS if k.endswith("_sha256")}
    target.update(request_bytes=123, reserved_usd="0.08", command_id="b" * 32)
    return {"schema": "P0-UNKNOWN-OFF-DISPOSITION-1.0", "disposition": "UNKNOWN_PRESERVE_COUNT_NO_EFFECT",
        "target_attempt": target, "slot_sha256": "c" * 64, "file_sha256s": dict.fromkeys(C.UNKNOWN_FILES, "d" * 64),
        "owner_diagnostic": descriptor("owner.json"), "preserve_reservation": True,
        "no_grant_reuse": True, "no_runtime_mutation": True}


def metadata():
    data = {k: "a" * 64 for k in FIELDS if k.endswith("_sha256")}
    data.update(schema="P0-PRODUCT-UNKNOWN-OFF-OBSERVATION-1.0",
        state="OFF_RESERVATIONS_OBSERVED_NOT_EFFECT_AUTHORIZED", timestamp_utc=datetime.now(UTC).isoformat(),
        slots_reserved=3, consumed_count=1, known_rejected_count=1, unknown_count=1,
        reserved_budget_usd="0.2544660", financial_basis="RESERVATIONS_NOT_BILLED_COST",
        actual_billed_cost_status="NOT_ESTABLISHED", live_enabled=False, effect_permitted=False,
        provider_calls=0, ledger_mutations=0, course_qualification="NOT_COMPLETED")
    return data


def test_closed_disposition_and_view_preserve_unknown_without_effect_or_available_slot():
    C.disposition_target(disposition())
    view = P1CampaignInspectionView(metadata()).as_dict()
    assert view["unknown_count"] == 1 and view["slots_reserved"] == 3
    assert view["schema"] == "P1-CAMPAIGN-UNKNOWN-OFF-METADATA-1.0"
    assert not view["live_enabled"] and not view["effect_permitted"]
    assert not {"remaining_calls", "remaining_reserved_budget_usd", "path", "body", "grant"} & view.keys()


@pytest.mark.parametrize("key,value", [("live_enabled", True), ("effect_permitted", True),
    ("provider_calls", 1), ("ledger_mutations", True), ("unknown_count", 0), ("consumed_count", 2),
    ("slots_reserved", 2), ("course_qualification", "PASS"), ("actual_billed_cost_status", "ESTABLISHED"),
    ("reserved_budget_usd", "NaN"), ("reserved_budget_usd", "1.960001"), ("reserved_budget_usd", "0"),
    ("root_lock_sha256", "bad"), ("timestamp_utc", "2026-10-16"), ("body", "SYNTHETIC_PRIVATE_SENTINEL")])
def test_projection_refuses_effects_reclassification_cumul_and_private_fields(key, value):
    data = metadata()
    data[key] = value
    with pytest.raises(ValueError):
        P1CampaignInspectionView(data)


@pytest.mark.parametrize("mutation", ["extra", "false_preserve", "new_grant", "missing_unknown",
    "result", "bool_bytes", "bad_hash", "bad_command", "negative_reserve"])
def test_disposition_mutations_refuse(mutation):
    data = disposition()
    if mutation == "extra":
        data["on"] = True
    elif mutation == "false_preserve":
        data["preserve_reservation"] = False
    elif mutation == "new_grant":
        data["no_grant_reuse"] = False
    elif mutation == "missing_unknown":
        data["file_sha256s"].pop("UNKNOWN")
    elif mutation == "result":
        data["file_sha256s"]["RESULT"] = "e" * 64
    elif mutation == "bool_bytes":
        data["target_attempt"]["request_bytes"] = True
    elif mutation == "bad_hash":
        data["target_attempt"]["namespace_sha256"] = "z" * 64
    elif mutation == "bad_command":
        data["target_attempt"]["command_id"] = "short"
    else:
        data["target_attempt"]["reserved_usd"] = "-0.1"
    with pytest.raises(ValueError):
        C.disposition_target(data)


def adoption():
    components = dict.fromkeys(C.COMPONENT_FIELDS, "a" * 64)
    book = {"schema": "P0-UNKNOWN-OFF-BOOK-1.0", "operation": "LOCAL_OFF_ONLY", "components": components}
    owner = {"schema": "P0-UNKNOWN-OFF-OWNER-ADOPTION-1.0", "operation": "LOCAL_OFF_ONLY",
        "book_sha256": C.sha(C.canonical(book)), "components": copy.deepcopy(components)}
    owner_sha = C.sha(C.canonical(owner))
    control = {"schema": "P0-UNKNOWN-OFF-ADOPTION-1.0", "book": descriptor("book.json", owner["book_sha256"]),
        "owner_evidence": descriptor("capture.json", owner_sha)}
    return control, book, owner, components, owner_sha


def test_adoption_requires_independent_trusted_raw_human_hash_and_exact_closed_book():
    control, book, owner, components, pin = adoption()
    C.validate_adoption(control, book, owner, owner_raw_sha256=pin, expected_owner_sha256=pin, components=components)
    with pytest.raises(ValueError, match="EXACT_ADOPTION"):
        C.validate_adoption(control, book, owner, owner_raw_sha256=pin,
            expected_owner_sha256="f" * 64, components=components)


@pytest.mark.parametrize("mutation", ["on", "book", "capture", "component", "extra", "permission"])
def test_adoption_never_transfers_grant_or_authorizes_on(mutation):
    control, book, owner, components, pin = adoption()
    if mutation == "on":
        owner["operation"] = "ON"
    elif mutation == "book":
        owner["book_sha256"] = "b" * 64
    elif mutation == "capture":
        control["owner_evidence"]["sha256"] = "b" * 64
    elif mutation == "component":
        owner["components"]["package_sha256"] = "b" * 64
    elif mutation == "extra":
        book["grant"] = "SYNTHETIC_ONLY"
    else:
        components["permission_sha256"] = "b" * 64
    with pytest.raises(ValueError):
        C.validate_adoption(control, book, owner, owner_raw_sha256=pin, expected_owner_sha256=pin, components=components)


def retained_unknown():
    grant, _, _, raw, tariff, tokenizer = fixture()
    dispatch = {"context": {}, "references": [], "context_sha256": C.sha(C.canonical({}))}
    grant.update(context_sha256=dispatch["context_sha256"], reference_set_sha256=C.sha(C.canonical([])),
        preparation_sha256=C.sha(C.canonical(dispatch)))
    proof = preflight(raw, grant, tariff, tokenizer)
    permission = {"baseline_commit": grant["baseline_commit"], "per_call_ceiling_usd": "0.14",
        "cumulative_ceiling_usd": "1.96", "max_calls": 14,
        "issued_at_utc": grant["issued_at_utc"], "expires_at_utc": grant["expires_at_utc"]}
    origin = OriginProof(permission, {}, {}, {}, {}, "a" * 64)
    chain = BoundChainV2({"campaign_namespace_sha256": "b" * 64}, {}, (origin,), {}, {})
    record = {"schema": "P0-PRODUCT-BUDGET-SLOT-1.0", "permission_sha256": origin.permission_sha256,
        "grant": grant, "grant_sha256": C.sha(C.canonical(grant)), "preview_sha256": "c" * 64,
        "command_id": "d" * 32, "namespace_sha256": grant["namespace_sha256"],
        "request_sha256": grant["request_sha256"], "preflight_sha256": C.sha(C.canonical(proof)),
        "reserved_usd": proof["cost_bound_usd"]}
    files = {"DISPATCH": {"schema": "P0-NORMAL-DISPATCH-CAPTURE-1.0", "grant": grant,
        "grant_sha256": record["grant_sha256"], "dispatch": dispatch, "dispatch_sha256": C.sha(C.canonical(dispatch)),
        "request_sha256": grant["request_sha256"], "body": raw.decode(), "preflight": proof,
        "preflight_sha256": record["preflight_sha256"], "namespace_sha256": grant["namespace_sha256"]}}
    for state in C.UNKNOWN_ORDER:
        files[state] = {"schema": "P0-NORMAL-TECHNICAL-RECEIPT-1.0", "state": state,
            **{k: record[k] for k in ("grant_sha256", "request_sha256", "preflight_sha256", "namespace_sha256", "reserved_usd")},
            "timestamp_utc": NOW.isoformat(), "provider_attempts": 0 if state == "RESERVED" else 1,
            "response_status": None, "response_artifact_sha256": None, "usage": None,
            "observed_cost_status": "NOT_ESTABLISHED"}
    return chain, record, files, tariff


def repin(record, files):
    capture, grant = files["DISPATCH"], record["grant"]
    grant["request_sha256"] = C.sha(capture["body"].encode())
    grant["request_bytes"] = len(capture["body"].encode())
    capture["preflight"].update(request_sha256=grant["request_sha256"], request_bytes=grant["request_bytes"])
    record.update(request_sha256=grant["request_sha256"], grant_sha256=C.sha(C.canonical(grant)),
        preflight_sha256=C.sha(C.canonical(capture["preflight"])))
    capture.update(**{k: record[k] for k in ("grant_sha256", "request_sha256", "preflight_sha256")})
    for state in C.UNKNOWN_ORDER:
        files[state].update(**{k: record[k] for k in ("grant_sha256", "request_sha256", "preflight_sha256", "reserved_usd")})
    d = disposition()
    d.update(target_attempt={**{k: record[k] for k in C.TARGET_FIELDS - {"request_bytes"}},
        "request_bytes": grant["request_bytes"]}, slot_sha256=C.sha(C.canonical(record)),
        file_sha256s={s: C.sha(C.canonical(v)) for s, v in files.items()})
    return d


def test_retained_unknown_is_validated_without_response_recovery_or_state_promotion():
    chain, record, files, tariff = retained_unknown()
    d = repin(record, files)
    C.validate_unknown(chain, record, disposition=d, files=files, raw_hashes=d["file_sha256s"], tariff=tariff)


@pytest.mark.parametrize("mutation,code", [("low_cost", "COST_RECOMPUTATION"), ("wire_tools", "BODY_POLICY"),
    ("wire_model", "BODY_POLICY"), ("wire_output", "BODY_POLICY"), ("wire_extra", "BODY_FIELDS"),
    ("extra_event", "FILE_PINS"), ("attempts", "EVENT_BINDING"), ("response", "EVENT_BINDING"),
    ("usage", "EVENT_BINDING"), ("chronology", "EVENT_BINDING"), ("preflight_count", "FINANCIAL_BINDING")])
def test_rehashed_adopted_unknown_still_rejects_invalid_semantics(mutation, code):
    import json
    chain, record, files, tariff = retained_unknown()
    if mutation == "low_cost":
        files["DISPATCH"]["preflight"]["cost_bound_usd"] = record["reserved_usd"] = "0.00001"
    elif mutation.startswith("wire_"):
        wire = json.loads(files["DISPATCH"]["body"])
        wire[{"wire_tools": "tools", "wire_model": "model", "wire_output": "max_output_tokens", "wire_extra": "foreign"}[mutation]] = {
            "wire_tools": [{"type": "SYNTHETIC_FOREIGN_TOOL"}], "wire_model": "SYNTHETIC_FOREIGN_MODEL",
            "wire_output": 8192, "wire_extra": True}[mutation]
        files["DISPATCH"]["body"] = C.canonical(wire).decode()
    elif mutation == "extra_event":
        files["RESULT"] = {"schema": "SYNTHETIC_ONLY"}
    elif mutation == "attempts":
        files["UNKNOWN"]["provider_attempts"] = 2
    elif mutation == "response":
        files["UNKNOWN"]["response_status"] = "completed"
    elif mutation == "usage":
        files["UNKNOWN"]["usage"] = {"input_tokens": 1}
    elif mutation == "chronology":
        files["UNKNOWN"]["timestamp_utc"] = "2026-10-11T10:00:00+00:00"
    else:
        files["DISPATCH"]["preflight"]["count_calls"] = 1
    d = repin(record, files)
    with pytest.raises(ValueError, match=code):
        C.validate_unknown(chain, record, disposition=d, files=files, raw_hashes=d["file_sha256s"], tariff=tariff)
