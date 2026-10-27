"""Closed pilot command metadata; observation creates no operational right."""
from __future__ import annotations

import re

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    _hash,
    _money,
    _stamp,
)

FIELDS = {"schema", "state", "timestamp_utc", "inspection_profile_sha256",
    "recipe_sha256", "command_id", "request_sha256", "preparation_sha256",
    "context_sha256", "reference_set_sha256", "parent_unknown_request_sha256",
    "pending_sha256", "stable_preview_sha256", "normal_preview_sha256",
    "issued_at_utc", "expires_at_utc", "derived_document_sha256s", "confirmation_receipts",
    "slot_sha256", "namespace_sha256", "reserved_usd", "receipts",
    "parent_406a", "right_status", "provider_departure_status",
    "response_artifact_present", "response_status", "actual_billed_cost_status", "financial_basis",
    "reservation_scope", "live_enabled", "effect_permitted", "provider_calls",
    "ledger_mutations"}
DOCUMENTS = {"permission", "decision", "envelope", "authority", "effect"}
RECEIPTS = {"RESERVED", "DISPATCH", "PROVIDER_ATTEMPTED", "RESULT",
    "RESPONSE_CAPTURED", "PARSED", "CONSUMED", "UNKNOWN", "PARSING_REJECTED"}


def pilot_command_projection(value: object) -> dict[str, object]:
    retained = isinstance(value, dict) and value.get("schema") == "P0-PILOT-COMMAND-INSPECTION-1.1"
    data = object_data(value, FIELDS | ({"right_id", "parent_2f1e", "response_metadata", "failure_evidence"} if retained else set()))
    absent = retained and data["state"] == "NO_PENDING_OBSERVED_NO_REPLAY"
    fixed = {"schema": "P0-PILOT-COMMAND-INSPECTION-1.1" if retained else "P0-PILOT-COMMAND-INSPECTION-1.0",
        "state": "NO_PENDING_OBSERVED_NO_REPLAY" if absent else "RETAINED_PENDING_OBSERVED_NO_REPLAY",
        "right_status": "NOT_ESTABLISHED_NO_NEW_RIGHT" if absent else "CONSUMED_AT_PENDING_NO_NEW_RIGHT",
        "actual_billed_cost_status": "NOT_ESTABLISHED",
        "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
        "reservation_scope": ("THIS_CHILD_406A_2F1E_NOT_CAMPAIGN_TOTAL" if retained
            else "THIS_CHILD_AND_406A_ONLY_NOT_CAMPAIGN_TOTAL"),
        "live_enabled": False, "effect_permitted": False, "provider_calls": 0,
        "ledger_mutations": 0}
    if any(type(data[key]) is not type(expected) or data[key] != expected
            for key, expected in fixed.items()):
        raise ValueError("P1_PILOT_INSPECTION_STATE")
    absent_fields = {"pending_sha256", "stable_preview_sha256", "normal_preview_sha256",
        "issued_at_utc", "expires_at_utc"}
    if absent and (any(data[key] is not None for key in absent_fields)
            or data["derived_document_sha256s"] != {} or data["receipts"] != []
            or data["slot_sha256"] is not None or data["response_artifact_present"]
            or data["provider_departure_status"] != "NOT_ESTABLISHED"):
        raise ValueError("P1_PILOT_INSPECTION_ABSENCE")
    for key in FIELDS - (absent_fields if absent else set()):
        if key.endswith("_sha256") and (key not in {"slot_sha256", "namespace_sha256"}
                or data[key] is not None):
            _hash(data[key])
    if (type(data["command_id"]) is not str
            or re.fullmatch(r"[0-9a-f]{32}", str(data["command_id"])) is None
            or type(data["response_artifact_present"]) is not bool
            or data["provider_departure_status"] not in {
                "NOT_ESTABLISHED", "ATTEMPT_MARKER_OBSERVED_NOT_REMOTE_RECEIPT",
                "RESPONSE_ARTIFACT_OBSERVED"}):
        raise ValueError("P1_PILOT_INSPECTION_IDENTITY")
    for key in (("timestamp_utc",) if absent else ("timestamp_utc", "issued_at_utc", "expires_at_utc")):
        _stamp(data[key])
    if not absent and _stamp(data["issued_at_utc"]) >= _stamp(data["expires_at_utc"]):
        raise ValueError("P1_PILOT_INSPECTION_WINDOW")
    docs = object_data(data["derived_document_sha256s"], set() if absent else DOCUMENTS)
    for pin in docs.values():
        _hash(pin)
    if data["reserved_usd"] is not None:
        _money(data["reserved_usd"], positive=True)
    if (data["slot_sha256"] is None) != (data["namespace_sha256"] is None):
        raise ValueError("P1_PILOT_INSPECTION_SLOT")
    if (data["slot_sha256"] is None) != (data["reserved_usd"] is None):
        raise ValueError("P1_PILOT_INSPECTION_SLOT")
    receipts = data["receipts"]
    if type(receipts) is not list or len(receipts) > len(RECEIPTS):
        raise ValueError("P1_PILOT_INSPECTION_RECEIPTS")
    seen = set()
    for receipt_value in receipts:
        row = object_data(receipt_value, {"state", "sha256", "timestamp_utc"})
        if row["state"] not in RECEIPTS or row["state"] in seen:
            raise ValueError("P1_PILOT_INSPECTION_RECEIPTS")
        seen.add(row["state"])
        _hash(row["sha256"])
        if row["timestamp_utc"] is not None:
            _stamp(row["timestamp_utc"])
    if data["response_artifact_present"] != ("RESULT" in seen):
        raise ValueError("P1_PILOT_INSPECTION_RESPONSE")
    if (data["response_status"] not in {None, "completed", "incomplete", "failed", "refused"}
            or data["response_artifact_present"] != (data["response_status"] is not None)):
        raise ValueError("P1_PILOT_INSPECTION_RESPONSE")
    confirmations = data["confirmation_receipts"]
    if type(confirmations) is not list or not (0 if absent else 1) <= len(confirmations) <= (1 if absent else 3):
        raise ValueError("P1_PILOT_INSPECTION_CONFIRMATIONS")
    confirmation_states = set()
    for confirmation in confirmations:
        row = object_data(confirmation, {"state", "sha256", "timestamp_utc"})
        if row["state"] not in ({"REVOKED"} if absent else {"PENDING", "EXPIRED_NO_SLOT", "REVOKED"}) or row["state"] in confirmation_states:
            raise ValueError("P1_PILOT_INSPECTION_CONFIRMATIONS")
        confirmation_states.add(row["state"])
        _hash(row["sha256"])
        _stamp(row["timestamp_utc"])
        if row["state"] == "PENDING" and row["sha256"] != data["pending_sha256"]:
            raise ValueError("P1_PILOT_INSPECTION_CONFIRMATIONS")
    if not absent and "PENDING" not in confirmation_states:
        raise ValueError("P1_PILOT_INSPECTION_CONFIRMATIONS")
    parent = object_data(data["parent_406a"], {"command_id", "state",
        "pending_sha256", "slot_sha256", "reserved_sha256", "dispatch_sha256",
        "reserved_usd", "actual_billed_cost_status"})
    if (parent["command_id"] != "406a9f51b4de4121ba91f9b410a9de4c"
            or parent["state"] != "RETAINED_SEPARATE_OUTCOME_UNKNOWN"
            or parent["actual_billed_cost_status"] != "NOT_ESTABLISHED"):
        raise ValueError("P1_PILOT_INSPECTION_PARENT")
    for key in ("pending_sha256", "slot_sha256", "reserved_sha256", "dispatch_sha256"):
        _hash(parent[key])
    _money(parent["reserved_usd"], positive=True)
    if retained:
        _retained(data)
    return {**data, "schema": "P1-PILOT-COMMAND-METADATA-1.1" if retained else "P1-PILOT-COMMAND-METADATA-1.0"}


def _retained(data: dict[str, object]) -> None:
    _failure_evidence(data)
    if data["right_id"] != "0d219dc79af0b34f1cba40adc6e9405e1da02bff084e6a5472ae5bfdfd61eab6":
        raise ValueError("P1_PILOT_INSPECTION_RIGHT")
    child = object_data(data["parent_2f1e"], {"command_id", "state", "pending_sha256",
        "slot_sha256", "reserved_usd", "actual_billed_cost_status", "disposition_sha256"})
    if (child["command_id"] != "2f1ef780598e469fafc94f9f4ba142c6"
            or data["command_id"] in {child["command_id"], "406a9f51b4de4121ba91f9b410a9de4c"}
            or child["state"] != "RETAINED_SEPARATE_OUTCOME_UNKNOWN"
            or child["actual_billed_cost_status"] != "NOT_ESTABLISHED"):
        raise ValueError("P1_PILOT_INSPECTION_PARENT")
    for key in ("pending_sha256", "slot_sha256"):
        _hash(child[key])
    if child["disposition_sha256"] is not None:
        _hash(child["disposition_sha256"])
    if data["pending_sha256"] is not None and child["disposition_sha256"] is None:
        raise ValueError("P1_PILOT_INSPECTION_PARENT")
    _money(child["reserved_usd"], positive=True)
    metadata = data["response_metadata"]
    if (metadata is not None) != data["response_artifact_present"]:
        raise ValueError("P1_PILOT_INSPECTION_RESPONSE")
    if metadata is None:
        return
    result = object_data(metadata, {"result_sha256", "output_text_sha256", "output_text_bytes", "usage"})
    _hash(result["result_sha256"])
    rows = data["receipts"]
    if not isinstance(rows, list) or not any(isinstance(row, dict)
            and row.get("state") == "RESULT" and row.get("sha256") == result["result_sha256"] for row in rows):
        raise ValueError("P1_PILOT_INSPECTION_RESPONSE")
    if (result["output_text_sha256"] is None) != (result["output_text_bytes"] is None):
        raise ValueError("P1_PILOT_INSPECTION_RESPONSE")
    if result["output_text_sha256"] is not None:
        _hash(result["output_text_sha256"])
        if type(result["output_text_bytes"]) is not int or result["output_text_bytes"] < 0:
            raise ValueError("P1_PILOT_INSPECTION_RESPONSE")
    usage = object_data(result["usage"], {"input_tokens", "cached_input_tokens", "output_tokens",
        "reasoning_tokens", "total_tokens", "cache_write_input_tokens"})
    if any(value is not None and (type(value) is not int or value < 0) for value in usage.values()):
        raise ValueError("P1_PILOT_INSPECTION_USAGE")


def _failure_evidence(data: dict[str, object]) -> None:
    evidence = object_data(data["failure_evidence"], {"state", "sha256", "document"})
    if evidence["state"] in {"NOT_OBSERVED_WITHOUT_SLOT", "ABSENT_IN_LINKED_NAMESPACE",
            "PRESENT_NOT_QUALIFIABLE_WITHOUT_DISPATCH"}:
        if evidence["document"] is not None:
            raise ValueError("P1_PILOT_INSPECTION_DIAGNOSTIC")
        if evidence["state"] == "PRESENT_NOT_QUALIFIABLE_WITHOUT_DISPATCH":
            _hash(evidence["sha256"])
        elif evidence["sha256"] is not None:
            raise ValueError("P1_PILOT_INSPECTION_DIAGNOSTIC")
        if (evidence["state"] == "NOT_OBSERVED_WITHOUT_SLOT") != (data["slot_sha256"] is None):
            raise ValueError("P1_PILOT_INSPECTION_DIAGNOSTIC")
        return
    if evidence["state"] != "VERIFIED" or data["slot_sha256"] is None:
        raise ValueError("P1_PILOT_INSPECTION_DIAGNOSTIC")
    _hash(evidence["sha256"])
    doc = object_data(evidence["document"], {"schema", "timestamp_utc", "namespace_sha256",
        "grant_sha256", "request_sha256", "preflight_sha256", "provider_attempts",
        "stage", "code_source", "technical_code", "outcome_marker", "marker_recorded"})
    if fingerprint(doc) != evidence["sha256"]:
        raise ValueError("P1_PILOT_INSPECTION_DIAGNOSTIC")
    if (doc["schema"] != "P0-NORMAL-FAILURE-DIAGNOSTIC-1.0"
            or doc["namespace_sha256"] != data["namespace_sha256"]
            or doc["request_sha256"] != data["request_sha256"]
            or type(doc["provider_attempts"]) is not int or doc["provider_attempts"] not in {0, 1}
            or type(doc["marker_recorded"]) is not bool
            or doc["outcome_marker"] not in {"UNKNOWN", "PARSING_REJECTED", "UNCONFIRMED"}
            or doc["stage"] not in {"CREDENTIAL_RESOLVE", "IDENTITY_RECHECK", "TRANSPORT_BUILD",
                "PREFLIGHT_RECHECK", "ATTEMPT_PUBLISH", "TRANSPORT_CREATE", "RESPONSE_METADATA",
                "RESULT_PUBLISH", "RESPONSE_CAPTURE_PUBLISH", "RESPONSE_VALIDATE", "CAPTURE_CONFIRM",
                "CONTENT_PARSE", "GUARD_AND_BIND", "PARSED_PUBLISH", "CONSUMED_PUBLISH"}):
        raise ValueError("P1_PILOT_INSPECTION_DIAGNOSTIC")
    _stamp(doc["timestamp_utc"])
    for key in ("namespace_sha256", "grant_sha256", "request_sha256", "preflight_sha256"):
        _hash(doc[key])
    before_transport = {"CREDENTIAL_RESOLVE", "IDENTITY_RECHECK", "TRANSPORT_BUILD",
        "PREFLIGHT_RECHECK", "ATTEMPT_PUBLISH"}
    before_capture = before_transport | {"TRANSPORT_CREATE", "RESPONSE_METADATA",
        "RESULT_PUBLISH", "RESPONSE_CAPTURE_PUBLISH"}
    marker = ("UNKNOWN" if doc["stage"] in before_capture else "UNCONFIRMED"
        if doc["stage"] in {"PARSED_PUBLISH", "CONSUMED_PUBLISH"} else "PARSING_REJECTED")
    if (doc["provider_attempts"] != (0 if doc["stage"] in before_transport else 1)
            or doc["outcome_marker"] != marker
            or marker == "UNCONFIRMED" and doc["marker_recorded"] is not False):
        raise ValueError("P1_PILOT_INSPECTION_DIAGNOSTIC")
    source, code = doc["code_source"], doc["technical_code"]
    if source is None and code is None:
        return
    if source == "OS_ERRNO" and type(code) is int and 0 <= code < 2**31:
        return
    codes = {
        "OPENAI_TRANSPORT": {"INVALID_REQUEST", "AUTHENTICATION", "PERMISSION", "BILLING",
            "RATE_LIMIT", "NOT_FOUND", "TIMEOUT", "CONNECTION", "SERVER", "REFUSED", "UNAVAILABLE"},
        "LOCAL_FILESYSTEM": {"RELATIVE_PATH", "NETWORK_PATH", "NON_LOCAL_ROOT",
            "OUTSIDE_ALLOWED_ROOT", "PATH_RESOLUTION_FAILED", "PATH_REDIRECTION_FORBIDDEN",
            "PATH_CHANGED", "PATH_COLLISION", "FILE_REQUIRED", "DESTINATION_EXISTS",
            "PERMISSION_HARDENING_FAILED", "PERMISSION_EXCESSIVE", "FILE_TOO_LARGE",
            "ATOMIC_PUBLICATION_FAILED"},
        "LOCAL_POLICY": {"P0_NORMAL_PREFLIGHT_CHANGED", "P0_NORMAL_RESPONSE_REJECTED",
            "P0_NORMAL_INTRINSIC_BINDING", "P0_NORMAL_RECEIPT_ROOT_BINDING",
            "P0_RICH_COURSE_NOTION_UNKNOWN", "P0_RECEIPT_SIZE", "P0_RECEIPT_ALREADY_USED",
            "P0_RECOVERY_OUTCOME_UNKNOWN"},
    }
    if type(source) is str and source in codes and type(code) is str and code in codes[source]:
        return
    raise ValueError("P1_PILOT_INSPECTION_DIAGNOSTIC")
