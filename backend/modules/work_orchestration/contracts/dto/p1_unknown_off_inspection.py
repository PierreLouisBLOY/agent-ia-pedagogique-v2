"""Closed metadata projection for OFF UNKNOWN preservation, no authority."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data

FIELDS = {"schema", "state", "timestamp_utc", "inspection_plan_sha256", "disposition_sha256",
    "root_permission_sha256", "origin_tip_permission_sha256", "campaign_namespace_sha256",
    "root_lock_sha256", "slots_reserved", "consumed_count", "known_rejected_count", "unknown_count",
    "reserved_budget_usd", "financial_basis", "actual_billed_cost_status", "live_enabled",
    "effect_permitted", "provider_calls", "ledger_mutations", "course_qualification"}


def unknown_off_projection(value: object) -> dict[str, object]:
    data = object_data(value, FIELDS)
    fixed = {"schema": "P0-PRODUCT-UNKNOWN-OFF-OBSERVATION-1.0",
        "state": "OFF_RESERVATIONS_OBSERVED_NOT_EFFECT_AUTHORIZED", "slots_reserved": 3,
        "consumed_count": 1, "known_rejected_count": 1, "unknown_count": 1,
        "financial_basis": "RESERVATIONS_NOT_BILLED_COST", "actual_billed_cost_status": "NOT_ESTABLISHED",
        "live_enabled": False, "effect_permitted": False, "provider_calls": 0, "ledger_mutations": 0,
        "course_qualification": "NOT_COMPLETED"}
    if any(type(data[k]) is not type(v) or data[k] != v for k, v in fixed.items()):
        raise ValueError("P1_UNKNOWN_OFF_STATE")
    for key in FIELDS:
        if key.endswith("_sha256") and (type(data[key]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", str(data[key])) is None):
            raise ValueError("P1_UNKNOWN_OFF_HASH")
    timestamp = data["timestamp_utc"]
    if type(timestamp) is not str or len(timestamp) > 64:
        raise ValueError("P1_UNKNOWN_OFF_TIMESTAMP")
    stamp = datetime.fromisoformat(timestamp)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("P1_UNKNOWN_OFF_TIMESTAMP")
    amount = data["reserved_budget_usd"]
    if (type(amount) is not str or re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,18})?", amount) is None
        or not 0 < Decimal(amount) <= Decimal("1.96")):
        raise ValueError("P1_UNKNOWN_OFF_CUMUL")
    return {**data, "schema": "P1-CAMPAIGN-UNKNOWN-OFF-METADATA-1.0"}
