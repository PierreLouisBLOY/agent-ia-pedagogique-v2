"""Closed UNKNOWN preservation contract: observation only, never effect authority."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    BODY_FIELDS,
    TARIFF_FIELDS,
    canonical,
    closed,
    digest,
    money,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import decode
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    EVENT_FIELDS,
    mapping,
    validate_slot,
)
from backend.adapters.outbound.generation.openai.p0_product_policy import F1_FIELDS
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    CAPTURE_FIELDS,
    BoundChainV2,
    reservation_totals,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import descriptor

UNKNOWN_ORDER = ("RESERVED", "PROVIDER_ATTEMPTED", "UNKNOWN")
UNKNOWN_FILES = {*UNKNOWN_ORDER, "DISPATCH"}
TARGET_FIELDS = {"permission_sha256", "namespace_sha256", "request_sha256", "request_bytes",
    "reserved_usd", "grant_sha256", "preview_sha256", "command_id", "preflight_sha256"}
DISPOSITION_FIELDS = {"schema", "disposition", "target_attempt", "slot_sha256", "file_sha256s",
    "owner_diagnostic", "preserve_reservation", "no_grant_reuse", "no_runtime_mutation"}
MANIFEST_FIELDS = {"schema", "anchor", "historical_manifest", "unknown_disposition",
    "expected_slots", "expected_reserved_budget_usd"}
ANCHOR_FIELDS = {"schema", "root_permission_sha256", "campaign_namespace_sha256", "root_lock_sha256",
    "original_anchor", "prior_anchor", "orientation_adoption", "prior_design_review", "owner_diagnostic"}
COMPONENT_FIELDS = {"plan_sha256", "anchor_sha256", "manifest_sha256", "disposition_sha256",
    "source_manifest_sha256", "package_sha256"}


def disposition_target(disposition: Mapping[str, object]) -> Mapping[str, object]:
    closed(disposition, DISPOSITION_FIELDS, "P0_UNKNOWN_OFF_DISPOSITION_FIELDS")
    selected = mapping(disposition["target_attempt"], "P0_UNKNOWN_OFF_TARGET")
    closed(selected, TARGET_FIELDS, "P0_UNKNOWN_OFF_TARGET_FIELDS")
    if (disposition["schema"] != "P0-UNKNOWN-OFF-DISPOSITION-1.0"
        or disposition["disposition"] != "UNKNOWN_PRESERVE_COUNT_NO_EFFECT"
        or any(disposition[k] is not True for k in
            ("preserve_reservation", "no_grant_reuse", "no_runtime_mutation"))
        or not digest(disposition["slot_sha256"])
        or any(not digest(selected[k]) for k in TARGET_FIELDS if k.endswith("_sha256"))
        or type(selected["request_bytes"]) is not int or not 0 < selected["request_bytes"] < 250000
        or type(selected["command_id"]) is not str
        or re.fullmatch(r"[0-9a-f]{32}", str(selected["command_id"])) is None):
        raise ValueError("P0_UNKNOWN_OFF_DISPOSITION_POLICY")
    money(selected["reserved_usd"])
    descriptor(disposition["owner_diagnostic"])
    pins = mapping(disposition["file_sha256s"], "P0_UNKNOWN_OFF_FILE_PINS")
    closed(pins, UNKNOWN_FILES, "P0_UNKNOWN_OFF_FILE_PINS")
    if any(not digest(pin) for pin in pins.values()):
        raise ValueError("P0_UNKNOWN_OFF_FILE_PINS")
    return selected


def validate_unknown(
    chain: BoundChainV2, record: Mapping[str, object], *, disposition: Mapping[str, object],
    files: Mapping[str, Mapping[str, object]], raw_hashes: Mapping[str, str], tariff: Mapping[str, object],
) -> None:
    """Exact retained UNKNOWN bytes; no response reconstruction or parse."""
    selected = disposition_target(disposition)
    validate_slot(chain, record, file_name=str(chain.manifest["campaign_namespace_sha256"])
        + ".P1." + str(record["preview_sha256"]) + ".json")
    grant = mapping(record["grant"], "P0_UNKNOWN_OFF_GRANT")
    if (selected["permission_sha256"] != chain.current.permission_sha256
        or sha(canonical(record)) != disposition["slot_sha256"]
        or any(record[k] != selected[k] for k in TARGET_FIELDS - {"request_bytes", "reserved_usd"})
        or grant["request_bytes"] != selected["request_bytes"]
        or money(record["reserved_usd"]) != money(selected["reserved_usd"])):
        raise ValueError("P0_UNKNOWN_OFF_SLOT_BINDING")
    if set(files) != UNKNOWN_FILES or set(raw_hashes) != UNKNOWN_FILES:
        raise ValueError("P0_UNKNOWN_OFF_EXACT_EVENT_SET_REQUIRED")
    pins = mapping(disposition["file_sha256s"], "P0_UNKNOWN_OFF_FILE_PINS")
    if any(raw_hashes[k] != pins[k] or sha(canonical(files[k])) != pins[k] for k in UNKNOWN_FILES):
        raise ValueError("P0_UNKNOWN_OFF_HISTORICAL_BYTES_CHANGED")
    capture = files["DISPATCH"]
    closed(capture, CAPTURE_FIELDS, "P0_UNKNOWN_OFF_CAPTURE_FIELDS")
    dispatch = mapping(capture["dispatch"], "P0_UNKNOWN_OFF_DISPATCH")
    proof = mapping(capture["preflight"], "P0_UNKNOWN_OFF_PREFLIGHT")
    closed(proof, F1_FIELDS, "P0_UNKNOWN_OFF_PREFLIGHT_FIELDS")
    body = capture["body"]
    if (capture["schema"] != "P0-NORMAL-DISPATCH-CAPTURE-1.0" or not isinstance(body, str)
        or len(body.encode()) != selected["request_bytes"] or sha(body.encode()) != selected["request_sha256"]
        or canonical(capture["grant"]) != canonical(grant)
        or any(capture[k] != record[k] for k in
            ("grant_sha256", "request_sha256", "preflight_sha256", "namespace_sha256"))
        or sha(canonical(dispatch)) != capture["dispatch_sha256"]
        or sha(canonical(dispatch)) != grant["preparation_sha256"]
        or sha(canonical(proof)) != record["preflight_sha256"]
        or sha(canonical(dispatch.get("context"))) != grant["context_sha256"]
        or dispatch.get("context_sha256") != grant["context_sha256"]
        or sha(canonical(dispatch.get("references"))) != grant["reference_set_sha256"]):
        raise ValueError("P0_UNKNOWN_OFF_CAPTURE_BINDING")
    if (proof["schema"] != "P0-NORMAL-PREFLIGHT-1.0"
        or proof["request_sha256"] != selected["request_sha256"]
        or proof["request_bytes"] != selected["request_bytes"]
        or proof["tariff_sha256"] != grant["tariff_sha256"]
        or not digest(proof["tokenizer_sha256"])
        or money(proof["cost_bound_usd"]) != money(record["reserved_usd"])
        or money(proof["ceiling_usd"]) != money(grant["ceiling_usd"])
        or money(record["reserved_usd"]) > money(grant["ceiling_usd"])
        or proof["status"] != "LOCAL_POLICY_CHECKED"
        or type(proof["structural_reserve_tokens"]) is not int or proof["structural_reserve_tokens"] != 10000
        or type(proof["max_output_tokens"]) is not int or proof["max_output_tokens"] != 4096
        or type(proof["local_text_tokens"]) is not int or proof["local_text_tokens"] < 1
        or type(proof["input_upper_tokens"]) is not int
        or proof["input_upper_tokens"] != proof["local_text_tokens"] + 10000
        or proof["input_upper_tokens"] > 40000
        or type(proof["count_calls"]) is not int or proof["count_calls"] != 0
        or type(proof["retry"]) is not int or proof["retry"] != 0 or proof["fallback"] != "NONE"):
        raise ValueError("P0_UNKNOWN_OFF_FINANCIAL_BINDING")
    wire = decode(body.encode())
    closed(wire, BODY_FIELDS, "P0_UNKNOWN_OFF_BODY_FIELDS")
    form = mapping(mapping(wire["text"], "P0_UNKNOWN_OFF_FORMAT").get("format"), "P0_UNKNOWN_OFF_FORMAT")
    if (wire["model"] != grant["model"] or wire["reasoning"] != {"effort": "low"}
        or wire["service_tier"] != "default" or wire["tools"] != [] or wire["tool_choice"] != "none"
        or any(wire[k] is not False for k in ("background", "stream", "store"))
        or type(wire["max_output_tokens"]) is not int or wire["max_output_tokens"] != 4096
        or set(form) != {"name", "type", "strict", "schema"}
        or form["name"] != "p0_pedagogical_content" or form["type"] != "json_schema"
        or form["strict"] is not True or sha(canonical(form["schema"])) != grant["output_schema_sha256"]):
        raise ValueError("P0_UNKNOWN_OFF_HISTORICAL_BODY_POLICY")
    closed(tariff, TARIFF_FIELDS, "P0_UNKNOWN_OFF_TARIFF_FIELDS")
    if (tariff["schema"] != "P0-NORMAL-TARIFF-1.0" or tariff["model"] != grant["model"]
        or tariff["provider"] != "OPENAI" or tariff["tier"] != "default"
        or not digest(tariff["evidence_sha256"]) or not digest(tariff["owner_admission_sha256"])
        or money(tariff["input_multiplier"]) < 1
        or utc(tariff["retrieved_at_utc"]) > utc(grant["issued_at_utc"])
        or sha(canonical(tariff)) != grant["tariff_sha256"]):
        raise ValueError("P0_UNKNOWN_OFF_TARIFF_BINDING")
    expected_cost = (Decimal(proof["input_upper_tokens"]) * money(tariff["input_usd_per_million"])
        * money(tariff["input_multiplier"]) + Decimal(4096) * money(tariff["output_usd_per_million"])) / Decimal(1000000)
    if expected_cost != money(record["reserved_usd"]):
        raise ValueError("P0_UNKNOWN_OFF_COST_RECOMPUTATION")
    previous = utc(grant["issued_at_utc"])
    for state in UNKNOWN_ORDER:
        event = files[state]
        closed(event, EVENT_FIELDS, "P0_UNKNOWN_OFF_EVENT_FIELDS")
        timestamp = utc(event["timestamp_utc"])
        if (event["schema"] != "P0-NORMAL-TECHNICAL-RECEIPT-1.0" or event["state"] != state
            or any(event[k] != record[k] for k in
                ("grant_sha256", "request_sha256", "preflight_sha256", "namespace_sha256"))
            or money(event["reserved_usd"]) != money(record["reserved_usd"])
            or type(event["provider_attempts"]) is not int
            or event["provider_attempts"] != (0 if state == "RESERVED" else 1)
            or event["observed_cost_status"] != "NOT_ESTABLISHED"
            or any(event[k] is not None for k in ("response_status", "response_artifact_sha256", "usage"))
            or not previous <= timestamp < utc(grant["expires_at_utc"])):
            raise ValueError("P0_UNKNOWN_OFF_EVENT_BINDING")
        previous = timestamp


def validate_owner_diagnostic(
    value: Mapping[str, object], *, chain: BoundChainV2, disposition: Mapping[str, object],
) -> None:
    selected = disposition_target(disposition)
    flags = mapping(value.get("flags"), "P0_UNKNOWN_OFF_DIAGNOSTIC_FLAGS")
    true_flags = {"RESERVED", "PROVIDER_ATTEMPTED", "UNKNOWN", "DISPATCH"}
    false_flags = {"RESPONSE_CAPTURED", "PARSED", "CONSUMED", "PARSING_REJECTED", "RESULT"}
    closed(flags, true_flags | false_flags, "P0_UNKNOWN_OFF_DIAGNOSTIC_FLAGS")
    events = mapping(value.get("events"), "P0_UNKNOWN_OFF_DIAGNOSTIC_EVENTS")
    closed(events, set(UNKNOWN_ORDER), "P0_UNKNOWN_OFF_DIAGNOSTIC_EVENTS")
    pins = mapping(disposition["file_sha256s"], "P0_UNKNOWN_OFF_FILE_PINS")
    if (value.get("schema") != "LU-P1-OWNER-EXACT-C4-ATTEMPT-METADATA-1.0"
        or value.get("source_commit") != chain.current.permission["baseline_commit"]
        or value.get("campaign_namespace_sha256") != chain.manifest["campaign_namespace_sha256"]
        or value.get("original_lock_sha256") != chain.manifest["root_lock_sha256"]
        or any(value.get({"namespace_sha256": "slot_namespace_sha256"}.get(k, k)) != selected[k]
            for k in TARGET_FIELDS - {"reserved_usd", "preflight_sha256"})
        or any(flags[k] is not True for k in true_flags)
        or any(flags[k] is not False for k in false_flags)
        or any(mapping(events[k], "P0_UNKNOWN_OFF_DIAGNOSTIC_EVENT").get("receipt_sha256") != pins[k]
            for k in UNKNOWN_ORDER)
        or value.get("raw_output_text_disclosed") is not False
        or value.get("actual_billed_cost_status") != "NOT_ESTABLISHED"):
        raise ValueError("P0_UNKNOWN_OFF_DIAGNOSTIC_BINDING")


def validate_inventory(
    chain: BoundChainV2, manifest: Mapping[str, object], records: Sequence[Mapping[str, object]],
    classifications: Mapping[str, str],
) -> str:
    closed(manifest, MANIFEST_FIELDS, "P0_UNKNOWN_OFF_MANIFEST_FIELDS")
    expected = manifest["expected_slots"]
    if (manifest["schema"] != "P0-UNKNOWN-OFF-MANIFEST-1.0" or not isinstance(expected, list)
        or len(expected) != 3 or len(records) != 3 or len(classifications) != 3):
        raise ValueError("P0_UNKNOWN_OFF_EXACT_THREE_SLOTS_REQUIRED")
    observed = [{"namespace_sha256": r["namespace_sha256"], "slot_sha256": sha(canonical(r)),
        "classification": classifications[str(r["namespace_sha256"])]} for r in records]
    for item in expected:
        row = mapping(item, "P0_UNKNOWN_OFF_INVENTORY")
        closed(row, {"namespace_sha256", "slot_sha256", "classification"}, "P0_UNKNOWN_OFF_INVENTORY_FIELDS")
    if (sorted(canonical(r) for r in observed) != sorted(canonical(r) for r in expected)
        or set(classifications.values()) != {"CONSUMED", "KNOWN_REJECTED", "UNKNOWN"}):
        raise ValueError("P0_UNKNOWN_OFF_INVENTORY_BINDING")
    _, total, _ = reservation_totals(chain, records)
    if total != money(manifest["expected_reserved_budget_usd"]):
        raise ValueError("P0_UNKNOWN_OFF_CUMUL_CHANGED")
    return str(total)


def observation(chain: BoundChainV2, *, plan_sha256: str, disposition_sha256: str,
    reserved_budget_usd: str, now: datetime) -> dict[str, object]:
    return {"schema": "P0-PRODUCT-UNKNOWN-OFF-OBSERVATION-1.0",
        "state": "OFF_RESERVATIONS_OBSERVED_NOT_EFFECT_AUTHORIZED", "timestamp_utc": now.isoformat(),
        "inspection_plan_sha256": plan_sha256, "disposition_sha256": disposition_sha256,
        "root_permission_sha256": chain.root.permission_sha256,
        "origin_tip_permission_sha256": chain.current.permission_sha256,
        "campaign_namespace_sha256": chain.manifest["campaign_namespace_sha256"],
        "root_lock_sha256": chain.manifest["root_lock_sha256"], "slots_reserved": 3,
        "consumed_count": 1, "known_rejected_count": 1, "unknown_count": 1,
        "reserved_budget_usd": reserved_budget_usd, "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
        "actual_billed_cost_status": "NOT_ESTABLISHED", "live_enabled": False, "effect_permitted": False,
        "provider_calls": 0, "ledger_mutations": 0, "course_qualification": "NOT_COMPLETED"}


def validate_adoption(control: Mapping[str, object], book: Mapping[str, object],
    owner: Mapping[str, object], *, owner_raw_sha256: str, expected_owner_sha256: str,
    components: Mapping[str, object]) -> None:
    closed(control, {"schema", "book", "owner_evidence"}, "P0_UNKNOWN_OFF_ADOPTION_FIELDS")
    closed(book, {"schema", "operation", "components"}, "P0_UNKNOWN_OFF_BOOK_FIELDS")
    closed(owner, {"schema", "operation", "book_sha256", "components"}, "P0_UNKNOWN_OFF_OWNER_FIELDS")
    closed(components, COMPONENT_FIELDS, "P0_UNKNOWN_OFF_COMPONENTS")
    if (control["schema"] != "P0-UNKNOWN-OFF-ADOPTION-1.0"
        or book["schema"] != "P0-UNKNOWN-OFF-BOOK-1.0"
        or owner["schema"] != "P0-UNKNOWN-OFF-OWNER-ADOPTION-1.0"
        or book["operation"] != "LOCAL_OFF_ONLY" or owner["operation"] != "LOCAL_OFF_ONLY"
        or not digest(expected_owner_sha256) or owner_raw_sha256 != expected_owner_sha256
        or descriptor(control["owner_evidence"])["sha256"] != expected_owner_sha256
        or descriptor(control["book"])["sha256"] != sha(canonical(book))
        or owner["book_sha256"] != sha(canonical(book))
        or canonical(book["components"]) != canonical(components)
        or canonical(owner["components"]) != canonical(components)
        or any(not digest(v) for v in components.values())):
        raise ValueError("P0_UNKNOWN_OFF_EXACT_ADOPTION_REQUIRED")
    # No component or book can refer back to its adopting human capture/control.
    if expected_owner_sha256 in components.values():
        raise ValueError("P0_UNKNOWN_OFF_ADOPTION_CYCLE")
