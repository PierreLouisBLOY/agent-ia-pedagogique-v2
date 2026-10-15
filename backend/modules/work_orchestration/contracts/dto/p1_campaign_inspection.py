"""Closed readonly P1 metadata; no paths, payloads or provider authority in a view."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from backend.core_contracts.outcome import ApplicationFailureKind
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping
from backend.shared_kernel._value_safety import require_safe_structured_value

REQUEST_FIELDS = {"contract_id", "inspection_ref", "expected_plan_or_profile_sha256"}
OBSERVATION_FIELDS = {"schema", "state", "timestamp_utc", "observed_evidence", "observed_evidence_sha256",
    "campaign_namespace_sha256", "root_permission_sha256", "observed_slots_reserved", "observed_reserved_budget_usd",
    "consumed_count", "known_rejected_count", "financial_basis", "live_enabled", "provider_calls", "ledger_mutations",
    "inspection_plan_sha256"}
SNAPSHOT_FIELDS = {"schema", "state", "timestamp_utc", "root_permission_sha256", "current_permission_sha256",
    "campaign_namespace_sha256", "slots_reserved", "reserved_budget_usd", "remaining_calls",
    "remaining_reserved_budget_usd", "financial_basis", "live_enabled", "known_rejected_count", "consumed_count",
    "disposition_sha256", "inspection_scope", "historic_transport_scope", "course_qualification",
    "current_context_contract_scope", "observation_plan_sha256"}
EVENTS = ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSING_REJECTED")
USAGE_FIELDS = {"input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "cache_write_input_tokens"}
EVIDENCE_FIELDS = {"schema", "observation_state", "campaign_namespace_sha256", "root_permission_sha256",
    "origin_permission_sha256", "namespace_sha256", "request_sha256", "request_bytes", "reserved_usd", "slot_sha256",
    "grant_sha256", "preview_sha256", "command_id", "dispatch_capture_sha256", "dispatch_payload_sha256",
    "preflight_sha256", "result_sha256", "output_text_sha256", "response_status", "provider_attempts", "event_sha256s",
    "event_timestamps", "usage", "disposition", "local_rejection_code", "owner_orientation_adoption", "owner_diagnostic",
    "transport_metadata_scope", "qualification", "timestamp_utc", "inspection_plan_sha256"}
TRANSPORT_SCOPE = "NOT_RETAINED_TIER_AND_INCOMPLETE_REASON"


def _hash(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("P1_INSPECTION_HASH")
    return value


def _count(value: object, maximum: int | None = None) -> int:
    if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
        raise ValueError("P1_INSPECTION_COUNT")
    return value


def _stamp(value: object) -> datetime:
    if type(value) is not str or len(value) > 64:
        raise ValueError("P1_INSPECTION_TIMESTAMP")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("P1_INSPECTION_TIMESTAMP") from error
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("P1_INSPECTION_TIMESTAMP")
    return stamp


def _money(value: object, *, positive: bool = False) -> Decimal:
    if type(value) is not str or re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,18})?", value) is None:
        raise ValueError("P1_INSPECTION_RESERVATION")
    amount = Decimal(value)
    if not amount.is_finite() or (positive and amount <= 0):
        raise ValueError("P1_INSPECTION_RESERVATION")
    return amount


def _label(value: object) -> None:
    if type(value) is not str or not value.strip() or len(value) > 256:
        raise ValueError("P1_INSPECTION_SCOPE")


def _evidence(value: object) -> dict[str, object]:
    data = object_data(value, EVIDENCE_FIELDS)
    fixed = {"schema": "P0-PRODUCT-KNOWN-REJECTED-EVIDENCE-1.0", "observation_state": "OBSERVED_NOT_ADOPTED",
        "response_status": "completed", "disposition": "TENTATIVE_CAPTUREE_REJETEE_A_CONSERVER_ET_COMPTER",
        "local_rejection_code": "P0_RICH_COURSE_NOTION_UNKNOWN", "transport_metadata_scope": TRANSPORT_SCOPE,
        "qualification": "REJECTED_NOT_CONSUMED"}
    if any(data[key] != expected for key, expected in fixed.items()) or _count(data["provider_attempts"]) != 1:
        raise ValueError("P1_INSPECTION_EVIDENCE_STATE")
    for key in EVIDENCE_FIELDS:
        if key.endswith("_sha256"):
            _hash(data[key])
    if (_count(data["request_bytes"]) == 0 or type(data["command_id"]) is not str
            or re.fullmatch(r"[0-9a-f]{32}", data["command_id"]) is None):
        raise ValueError("P1_INSPECTION_EVIDENCE_IDENTITY")
    _money(data["reserved_usd"], positive=True)
    _stamp(data["timestamp_utc"])
    pins = object_data(data["event_sha256s"], set(EVENTS))
    for pin in pins.values():
        _hash(pin)
    times = object_data(data["event_timestamps"], set(EVENTS))
    stamps = [_stamp(times[state]) for state in EVENTS]
    if stamps != sorted(stamps):
        raise ValueError("P1_INSPECTION_EVENT_ORDER")
    usage = object_data(data["usage"], USAGE_FIELDS)
    for item in usage.values():
        if item is not None:
            _count(item)
    input_count, output_count = usage["input_tokens"], usage["output_tokens"]
    cached, written, reasoning, total = (usage[k] for k in ("cached_input_tokens", "cache_write_input_tokens", "reasoning_tokens", "total_tokens"))
    if type(output_count) is int and output_count > 4096:
        raise ValueError("P1_INSPECTION_USAGE")
    if type(input_count) is int:
        if any(type(v) is int and v > input_count for v in (cached, written)):
            raise ValueError("P1_INSPECTION_USAGE")
    if type(reasoning) is int and type(output_count) is int and reasoning > output_count:
        raise ValueError("P1_INSPECTION_USAGE")
    if type(input_count) is int and type(output_count) is int and type(total) is int and total != input_count + output_count:
        raise ValueError("P1_INSPECTION_USAGE")
    for key in ("owner_orientation_adoption", "owner_diagnostic"):
        descriptor = object_data(data[key], {"path", "sha256"})
        _hash(descriptor["sha256"])
        path = descriptor["path"]
        if type(path) is not str or not path or len(path) > 4096 or any(c in path for c in "\x00\r\n"):
            raise ValueError("P1_INSPECTION_DESCRIPTOR")
    return data


def _observation(value: object) -> dict[str, object]:
    data = object_data(value, OBSERVATION_FIELDS)
    if (data["schema"] != "P0-PRODUCT-REJECTED-OBSERVATION-1.0" or data["state"] != "OBSERVED_NOT_ADOPTED"
            or data["financial_basis"] != "RESERVATIONS_NOT_BILLED_COST" or data["live_enabled"] is not False
            or _count(data["provider_calls"]) != 0 or _count(data["ledger_mutations"]) != 0
            or _count(data["known_rejected_count"]) != 1):
        raise ValueError("P1_INSPECTION_BOOTSTRAP_STATE")
    _stamp(data["timestamp_utc"])
    for key in OBSERVATION_FIELDS:
        if key.endswith("_sha256"):
            _hash(data[key])
    slots = _count(data["observed_slots_reserved"], 14)
    if _count(data["consumed_count"], 14) + 1 != slots:
        raise ValueError("P1_INSPECTION_BOOTSTRAP_COUNT")
    evidence = _evidence(data["observed_evidence"])
    if (fingerprint(evidence) != data["observed_evidence_sha256"]
            or any(data[key] != evidence[key] for key in ("root_permission_sha256", "campaign_namespace_sha256", "inspection_plan_sha256"))
            or _money(data["observed_reserved_budget_usd"], positive=True) < _money(evidence["reserved_usd"], positive=True)):
        raise ValueError("P1_INSPECTION_FULL_EVIDENCE_BINDING")
    projected = object_data(as_plain(evidence))
    projected["schema"] = "P1-KNOWN-REJECTED-EVIDENCE-METADATA-1.0"
    for key in ("owner_orientation_adoption", "owner_diagnostic"):
        descriptor = object_data(evidence[key], {"path", "sha256"})
        projected[key] = {"ref": "p1-evidence:" + _hash(descriptor["sha256"]), "sha256": descriptor["sha256"]}
    result = object_data(as_plain(data))
    result.update(schema="P1-CAMPAIGN-INSPECTION-OBSERVATION-1.0", observed_evidence=projected,
        evidence_hash_basis="UNDERLYING_FULL_EVIDENCE_RAW_BYTES")
    return result


def _snapshot(value: object) -> dict[str, object]:
    data = object_data(value, SNAPSHOT_FIELDS)
    if (data["schema"] != "P0-PRODUCT-CAMPAIGN-SNAPSHOT-2.0" or data["state"] != "CURRENT_RESERVATIONS_RECONCILED"
            or data["financial_basis"] != "RESERVATIONS_NOT_BILLED_COST" or data["course_qualification"] != "NOT_COMPLETED"
            or data["historic_transport_scope"] != TRANSPORT_SCOPE or type(data["live_enabled"]) is not bool
            or _count(data["known_rejected_count"]) != 1):
        raise ValueError("P1_INSPECTION_SNAPSHOT_STATE")
    _stamp(data["timestamp_utc"])
    for key in SNAPSHOT_FIELDS:
        if key.endswith("_sha256"):
            _hash(data[key])
    slots = _count(data["slots_reserved"], 14)
    if _count(data["consumed_count"], 14) + 1 > slots:
        raise ValueError("P1_INSPECTION_SNAPSHOT_COUNT")
    if _count(data["remaining_calls"], 14) + slots > 14:
        raise ValueError("P1_INSPECTION_SNAPSHOT_COUNT")
    _money(data["reserved_budget_usd"], positive=True)
    _money(data["remaining_reserved_budget_usd"])
    for key in ("inspection_scope", "current_context_contract_scope"):
        _label(data[key])
    return object_data(as_plain(data))


@dataclass(frozen=True, slots=True)
class P1CampaignInspectionRequest:
    inspection_ref: str
    expected_plan_or_profile_sha256: str
    contract_id: str = "P1-CAMPAIGN-INSPECTION-REQUEST-1.0"

    def __post_init__(self) -> None:
        if (type(self.contract_id) is not str or self.contract_id != "P1-CAMPAIGN-INSPECTION-REQUEST-1.0" or type(self.inspection_ref) is not str
                or re.fullmatch(r"p1-inspection:[A-Za-z0-9._:-]{1,180}", self.inspection_ref) is None):
            raise ValueError("P1_INSPECTION_REQUEST")
        _hash(self.expected_plan_or_profile_sha256)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> P1CampaignInspectionRequest:
        data = object_data(value, REQUEST_FIELDS)
        if any(type(v) is not str for v in data.values()):
            raise ValueError("P1_INSPECTION_REQUEST")
        return cls(inspection_ref=str(data["inspection_ref"]), expected_plan_or_profile_sha256=str(data["expected_plan_or_profile_sha256"]),
            contract_id=str(data["contract_id"]))

    def as_dict(self) -> dict[str, object]:
        return {"contract_id": self.contract_id, "inspection_ref": self.inspection_ref,
            "expected_plan_or_profile_sha256": self.expected_plan_or_profile_sha256}


@dataclass(frozen=True, slots=True)
class P1CampaignInspectionView:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        data = object_data(self.data)
        schema = data.get("schema")
        if schema == "P0-PRODUCT-UNKNOWN-OFF-OBSERVATION-1.0":
            from backend.modules.work_orchestration.contracts.dto.p1_unknown_off_inspection import (
                unknown_off_projection,
            )
            result = unknown_off_projection(data)
        else:
            result = _observation(data) if schema == "P0-PRODUCT-REJECTED-OBSERVATION-1.0" else _snapshot(data)
        require_safe_structured_value(result, root_location="p1_inspection_view")
        object.__setattr__(self, "data", freeze_safe_mapping(result))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> P1CampaignInspectionView:
        return cls(value)

    def as_dict(self) -> dict[str, object]:
        return object_data(as_plain(self.data))


class P1CampaignInspectionReader(Protocol):
    def inspect(self, *, inspection_ref: str, expected_plan_or_profile_sha256: str) -> Mapping[str, object]: ...


class P1CampaignInspectionPortError(Exception):
    def __init__(self, kind: ApplicationFailureKind) -> None:
        if type(kind) is not ApplicationFailureKind or kind not in {ApplicationFailureKind.AF_MAPPING_CORRUPTION, ApplicationFailureKind.AF_CONCURRENCY,
                ApplicationFailureKind.AF_PORT_UNAVAILABLE, ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN}:
            raise ValueError("P1_INSPECTION_FAILURE_KIND")
        self.kind = kind
        super().__init__(kind.value)
