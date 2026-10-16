"""Operational budget projection through the existing Application view, not effect authority."""
from __future__ import annotations

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    _count,
    _money,
    _stamp,
)

FIELDS = {"schema", "state", "timestamp_utc", "slots_reserved", "consumed_count", "known_rejected_count",
    "unknown_count", "pending_count", "reserved_budget_usd", "financial_basis", "actual_billed_cost_status",
    "effect_permitted", "course_qualification"}


def operational_projection(value: object) -> dict[str, object]:
    data = object_data(value, FIELDS)
    if (data["schema"] != "P0-UNKNOWN-CONTINUITY-SNAPSHOT-1.0"
        or data["state"] != "PRESERVED_HISTORY_NO_EFFECT_AUTHORITY"
        or data["effect_permitted"] is not False or data["course_qualification"] != "NOT_COMPLETED"
        or data["financial_basis"] != "RESERVATIONS_NOT_BILLED_COST"
        or data["actual_billed_cost_status"] != "NOT_ESTABLISHED"
        or _count(data["known_rejected_count"]) != 1 or _count(data["unknown_count"]) != 1):
        raise ValueError("P1_UNKNOWN_OPERATIONAL_PROJECTION")
    count, consumed, pending = (_count(data[k]) for k in ("slots_reserved", "consumed_count", "pending_count"))
    if count not in {3, 4} or consumed not in {1, 2} or pending not in {0, 1} or consumed + pending + 2 != count:
        raise ValueError("P1_UNKNOWN_OPERATIONAL_PROJECTION_COUNTS")
    _stamp(data["timestamp_utc"])
    if _money(data["reserved_budget_usd"], positive=True) > _money("1.96"):
        raise ValueError("P1_UNKNOWN_OPERATIONAL_PROJECTION_BUDGET")
    return {**data, "schema": "P1-UNKNOWN-CONTINUITY-METADATA-1.0"}
