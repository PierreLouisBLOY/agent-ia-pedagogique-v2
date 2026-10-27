"""Closed OFF policy for one manual same-need CREATE after a retained UNKNOWN.

This contract evaluates a trusted, lock-held observation. It never grants an
effect, changes historical receipts, or treats a reservation as a billed cost.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    money,
    sha,
)

POLICY_SHA256 = "d1ac715fa05ae5acc96d987178737f4a7694063048e68060124ef065ae938a72"
OPERATION = "ONE_MANUAL_CREATE_REATTEMPT_OF_UNKNOWN"
PLAN_FIELDS = {"schema", "operation", "mode", "effect_authorized", "policy_sha256",
    "campaign_namespace_sha256", "original_lock_sha256", "frozen_inventory_sha256",
    "parent_unknown", "new_preparation_sha256", "context_sha256", "reference_set_sha256",
    "runtime_sha256", "saved_root_native_sha256", "source_manifest_sha256", "package_sha256",
    "historical_reserved_usd", "new_cost_bound_usd", "max_new_creates", "max_slots",
    "per_call_ceiling_usd", "cumulative_ceiling_usd", "retry", "fallback", "parallelism"}
PARENT_FIELDS = {"namespace_sha256", "slot_sha256", "request_sha256", "unknown_receipt_sha256"}
OBSERVATION_FIELDS = {"schema", "campaign_namespace_sha256", "original_lock_sha256",
    "frozen_inventory", "slots", "actual_billed_cost_status"}
INVENTORY_FIELDS = {"name", "sha256", "device", "inode"}
SLOT_FIELDS = {"namespace_sha256", "slot_sha256", "request_sha256", "classification",
    "reserved_usd", "terminal_receipt_sha256"}


def _hash(value: object) -> bool:
    return type(value) is str and digest(value)


def _amount(value: object) -> Decimal:
    if type(value) is not str:
        raise ValueError("P1_PILOT_MONEY_REQUIRED")
    return money(value)


def validate_off_plan(plan: Mapping[str, object]) -> None:
    """A policy adoption is not an operation grant or a live window."""
    closed(plan, PLAN_FIELDS, "P1_PILOT_PLAN_FIELDS")
    if not isinstance(plan["parent_unknown"], Mapping):
        raise ValueError("P1_PILOT_PARENT_FIELDS")
    parent = cast(Mapping[str, object], plan["parent_unknown"])
    closed(parent, PARENT_FIELDS, "P1_PILOT_PARENT_FIELDS")
    hashes = ("campaign_namespace_sha256", "original_lock_sha256", "frozen_inventory_sha256",
        "new_preparation_sha256", "context_sha256", "reference_set_sha256", "runtime_sha256",
        "saved_root_native_sha256", "source_manifest_sha256", "package_sha256")
    if (plan["schema"] != "P1-PILOT-SAME-NEED-OFF-1.0" or plan["operation"] != OPERATION
        or plan["mode"] != "OFF" or plan["effect_authorized"] is not False
        or plan["policy_sha256"] != POLICY_SHA256
        or any(not _hash(plan[key]) for key in hashes)
        or any(not _hash(parent[key]) for key in PARENT_FIELDS)
        or parent["namespace_sha256"] == plan["campaign_namespace_sha256"]
        or type(plan["max_new_creates"]) is not int or plan["max_new_creates"] != 1
        or type(plan["max_slots"]) is not int or plan["max_slots"] != 14
        or type(plan["retry"]) is not int or plan["retry"] != 0
        or plan["fallback"] != "NONE" or type(plan["parallelism"]) is not int
        or plan["parallelism"] != 1):
        raise ValueError("P1_PILOT_OFF_POLICY_REQUIRED")
    if (_amount(plan["historical_reserved_usd"]) != Decimal("0.2544660")
        or _amount(plan["per_call_ceiling_usd"]) != Decimal("0.1400000")
        or _amount(plan["cumulative_ceiling_usd"]) != Decimal("1.9600000")
        or not Decimal(0) < _amount(plan["new_cost_bound_usd"]) <= Decimal("0.1400000")):
        raise ValueError("P1_PILOT_BOUND_REQUIRED")


def assess_off(plan: Mapping[str, object], observation: Mapping[str, object]) -> dict[str, object]:
    """Evaluate the complete historical reserve exactly once, without reserving."""
    validate_off_plan(plan)
    closed(observation, OBSERVATION_FIELDS, "P1_PILOT_OBSERVATION_FIELDS")
    inventory = observation["frozen_inventory"]
    slots = observation["slots"]
    if (observation["schema"] != "P1-PILOT-HISTORICAL-OBSERVATION-1.0"
        or observation["campaign_namespace_sha256"] != plan["campaign_namespace_sha256"]
        or observation["original_lock_sha256"] != plan["original_lock_sha256"]
        or observation["actual_billed_cost_status"] != "NOT_ESTABLISHED"
        or not isinstance(inventory, list) or len(inventory) != 20
        or not isinstance(slots, list) or len(slots) != 3):
        raise ValueError("P1_PILOT_FROZEN_HISTORY_REQUIRED")
    names: set[str] = set()
    for item in inventory:
        if not isinstance(item, Mapping):
            raise ValueError("P1_PILOT_FROZEN_HISTORY_REQUIRED")
        closed(item, INVENTORY_FIELDS, "P1_PILOT_INVENTORY_FIELDS")
        name = item["name"]
        if (type(name) is not str or not name.endswith(".json") or not 1 <= len(name) <= 240
            or name in names or any(c in name for c in "/\\:\x00\r\n") or ".." in name
            or not _hash(item["sha256"])
            or any(type(item[k]) is not int or item[k] <= 0 for k in ("device", "inode"))):
            raise ValueError("P1_PILOT_FROZEN_HISTORY_REQUIRED")
        names.add(name)
    if sha(canonical(inventory)) != plan["frozen_inventory_sha256"]:
        raise ValueError("P1_PILOT_FROZEN_HISTORY_CHANGED")
    parent = cast(Mapping[str, object], plan["parent_unknown"])
    classes: set[str] = set()
    namespaces: set[str] = set()
    total = Decimal(0)
    for item in slots:
        if not isinstance(item, Mapping):
            raise ValueError("P1_PILOT_FROZEN_HISTORY_REQUIRED")
        closed(item, SLOT_FIELDS, "P1_PILOT_SLOT_FIELDS")
        if (any(not _hash(item[k]) for k in ("namespace_sha256", "slot_sha256",
                "request_sha256", "terminal_receipt_sha256"))
            or type(item["classification"]) is not str
            or item["classification"] not in {"UNKNOWN", "KNOWN_REJECTED", "CONSUMED"}
            or item["namespace_sha256"] in namespaces):
            raise ValueError("P1_PILOT_SLOT_CLASSIFICATION_REQUIRED")
        classes.add(str(item["classification"]))
        namespaces.add(str(item["namespace_sha256"]))
        total += _amount(item["reserved_usd"])
        if item["classification"] == "UNKNOWN" and any(item[k] != parent[v] for k, v in (
            ("namespace_sha256", "namespace_sha256"), ("slot_sha256", "slot_sha256"),
            ("request_sha256", "request_sha256"), ("terminal_receipt_sha256", "unknown_receipt_sha256"))):
            raise ValueError("P1_PILOT_PARENT_UNKNOWN_CHANGED")
    if classes != {"UNKNOWN", "KNOWN_REJECTED", "CONSUMED"}:
        raise ValueError("P1_PILOT_SLOT_CLASSIFICATION_REQUIRED")
    if total != _amount(plan["historical_reserved_usd"]):
        raise ValueError("P1_PILOT_HISTORICAL_CUMUL_CHANGED")
    bound = _amount(plan["new_cost_bound_usd"])
    if len(slots) + 1 > cast(int, plan["max_slots"]) or total + bound > _amount(plan["cumulative_ceiling_usd"]):
        raise ValueError("P1_PILOT_CUMUL_EXCEEDED")
    return {"schema": "P1-PILOT-SAME-NEED-OFF-RESULT-1.0", "state": "OFF_BOUNDED_NO_EFFECT",
        "parent_unknown_preserved": True, "historical_slots": 3, "historical_reserved_usd": str(total),
        "candidate_bound_usd": str(bound), "combined_reserved_ceiling_usd": str(total + bound),
        "bound_basis": "LOCAL_OFF_DECLARATION_NOT_PREFLIGHT",
        "actual_billed_cost_status": "NOT_ESTABLISHED", "effect_permitted": False,
        "windows_power_loss_durability": "NOT_ESTABLISHED",
        "new_slots": 0, "provider_calls": 0}
