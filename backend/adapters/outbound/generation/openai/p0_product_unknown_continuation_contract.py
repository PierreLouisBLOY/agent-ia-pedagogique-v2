"""Closed authority for one distinct operation; UNKNOWN preservation is not confirmation."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    money,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import mapping
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    BoundChainV2,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import descriptor

HISTORY_FIELDS = {"schema", "off_plan", "off_book", "off_adoption", "off_expected_owner_sha256",
    "off_result", "frozen_inventory", "policy"}
INTENT_FIELDS = {"schema", "preparation_sha256", "request_sha256", "request_bytes", "context_sha256",
    "reference_set_sha256", "old_intent_sha256", "new_intent_sha256", "old_objectives_sha256",
    "new_objectives_sha256", "cost_bound_usd"}
PLAN_FIELDS = {"schema", "history", "intent", "profile_envelopes", "profile_adoption", "issued_at_utc",
    "expires_at_utc", "max_new_operations", "operation", "retry", "fallback", "parallelism"}
COMPONENT_FIELDS = {"plan_sha256", "history_sha256", "intent_sha256", "source_manifest_sha256",
    "package_sha256", "profile_off_sha256", "profile_on_sha256"}
OPERATION = "ONE_DISTINCT_CREATE_AFTER_UNKNOWN"


@dataclass(frozen=True)
class UnknownContinuation:
    plan: Mapping[str, object]
    history: Mapping[str, object]
    intent: Mapping[str, object]
    historical_chain: BoundChainV2
    historical_manifest: Mapping[str, object]
    unknown_disposition: Mapping[str, object]
    current_chain: BoundChainV2


def validate_history(value: Mapping[str, object]) -> None:
    closed(value, HISTORY_FIELDS, "P1_UNKNOWN_HISTORY_FIELDS")
    if (value["schema"] != "P1-UNKNOWN-CONTINUITY-HISTORY-1.0"
        or value["policy"] != "PRESERVE_COUNT_NO_REPLAY" or not digest(value["off_expected_owner_sha256"])):
        raise ValueError("P1_UNKNOWN_HISTORY_POLICY")
    for key in ("off_plan", "off_book", "off_adoption", "off_result"):
        descriptor(value[key])
    rows = value["frozen_inventory"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1024:
        raise ValueError("P1_UNKNOWN_HISTORY_INVENTORY")
    names = set()
    for item in rows:
        row = mapping(item, "P1_UNKNOWN_HISTORY_ROW")
        closed(row, {"name", "sha256", "device", "inode"}, "P1_UNKNOWN_HISTORY_ROW_FIELDS")
        name = row["name"]
        if (type(name) is not str or not name.endswith(".json") or len(name) > 240
            or any(c in name for c in "/\\:\x00\r\n") or ".." in name or name in names
            or not digest(row["sha256"]) or any(type(row[k]) is not int or cast(int, row[k]) <= 0 for k in ("device", "inode"))):
            raise ValueError("P1_UNKNOWN_HISTORY_INVENTORY")
        names.add(name)


def validate_intent(value: Mapping[str, object]) -> None:
    closed(value, INTENT_FIELDS, "P1_UNKNOWN_INTENT_FIELDS")
    if (value["schema"] != "P1-UNKNOWN-CONTINUITY-INTENT-1.0"
        or any(not digest(value[k]) for k in INTENT_FIELDS if k.endswith("_sha256"))
        or type(value["request_bytes"]) is not int or not 0 < value["request_bytes"] < 250000
        or value["old_intent_sha256"] == value["new_intent_sha256"]
        or value["old_objectives_sha256"] == value["new_objectives_sha256"]
        or not 0 < money(value["cost_bound_usd"]) <= money("0.14")):
        raise ValueError("P1_UNKNOWN_DISTINCT_INTENT_REQUIRED")


def validate_plan(value: Mapping[str, object], *, now: datetime, root: Mapping[str, object]) -> None:
    closed(value, PLAN_FIELDS, "P1_UNKNOWN_OPERATION_FIELDS")
    if (value["schema"] != "P1-UNKNOWN-CONTINUITY-OPERATION-1.0" or value["operation"] != OPERATION
        or type(value["max_new_operations"]) is not int or value["max_new_operations"] != 1
        or type(value["retry"]) is not int or value["retry"] != 0 or value["fallback"] != "NONE"
        or type(value["parallelism"]) is not int or value["parallelism"] != 1
        or not utc(root["issued_at_utc"]) <= utc(value["issued_at_utc"]) <= now
            < utc(value["expires_at_utc"]) <= utc(root["expires_at_utc"])):
        raise ValueError("P1_UNKNOWN_OPERATION_POLICY")
    for key in ("history", "intent", "profile_adoption"):
        descriptor(value[key])
    pair = mapping(value["profile_envelopes"], "P1_UNKNOWN_PROFILE_PAIR")
    closed(pair, {"off", "on"}, "P1_UNKNOWN_PROFILE_PAIR")
    for desc in pair.values():
        descriptor(desc)


def validate_adoption(control: Mapping[str, object], book: Mapping[str, object], owner: Mapping[str, object],
    *, expected_owner_sha256: str, owner_raw_sha256: str, components: Mapping[str, object]) -> None:
    closed(control, {"schema", "book", "owner_evidence"}, "P1_UNKNOWN_CONTROL_FIELDS")
    closed(book, {"schema", "operation", "components"}, "P1_UNKNOWN_BOOK_FIELDS")
    closed(owner, {"schema", "operation", "book_sha256", "components", "new_need_confirmed",
        "unknown_risk_acknowledged", "not_a_retry"}, "P1_UNKNOWN_OWNER_FIELDS")
    closed(components, COMPONENT_FIELDS, "P1_UNKNOWN_COMPONENTS")
    if (control["schema"] != "P1-UNKNOWN-CONTINUITY-ADOPTION-1.0"
        or book["schema"] != "P1-UNKNOWN-CONTINUITY-BOOK-1.0"
        or owner["schema"] != "P1-UNKNOWN-CONTINUITY-OWNER-1.0"
        or book["operation"] != OPERATION or owner["operation"] != OPERATION
        or any(owner[k] is not True for k in ("new_need_confirmed", "unknown_risk_acknowledged", "not_a_retry"))
        or not digest(expected_owner_sha256) or owner_raw_sha256 != expected_owner_sha256
        or descriptor(control["owner_evidence"])["sha256"] != expected_owner_sha256
        or descriptor(control["book"])["sha256"] != sha(canonical(book))
        or owner["book_sha256"] != sha(canonical(book))
        or canonical(book["components"]) != canonical(components)
        or canonical(owner["components"]) != canonical(components)
        or any(not digest(v) or v == expected_owner_sha256 for v in components.values())):
        raise ValueError("P1_UNKNOWN_OPERATION_EXACT_ADOPTION_REQUIRED")
