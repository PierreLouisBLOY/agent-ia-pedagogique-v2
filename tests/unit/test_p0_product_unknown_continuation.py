"""Declared synthetic operation authority and anti-replay data, no provider or runtime stores."""
import copy
from datetime import UTC, datetime, timedelta

import pytest

from backend.adapters.outbound.generation.openai import (
    p0_product_unknown_continuation_contract as C,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionView,
)
from backend.modules.work_orchestration.contracts.dto.p1_operation_intent import (
    distinct_operation,
    operation_projection,
)
from tests.unit.test_p0_product_unknown_off import descriptor
from tests.unit.test_p0_rich_course_content import rich_preparation

NOW = datetime(2026, 10, 16, tzinfo=UTC)


def history():
    return {"schema": "P1-UNKNOWN-CONTINUITY-HISTORY-1.0", **{k: descriptor(k + ".json")
        for k in ("off_plan", "off_book", "off_adoption", "off_result")}, "off_expected_owner_sha256": "a" * 64,
        "policy": "PRESERVE_COUNT_NO_REPLAY", "frozen_inventory": [
            {"name": "synthetic.json", "sha256": "b" * 64, "device": 1, "inode": 2}]}


def intent():
    return {**dict.fromkeys((k for k in C.INTENT_FIELDS if k.endswith("_sha256")), "a" * 64),
        "schema": "P1-UNKNOWN-CONTINUITY-INTENT-1.0", "request_bytes": 100,
        "new_intent_sha256": "b" * 64, "new_objectives_sha256": "c" * 64, "cost_bound_usd": "0.08"}


@pytest.mark.parametrize("change", ["extra", "bad_name", "duplicate", "bool_id", "zero_id", "bad_policy", "new_grant"])
def test_history_closed_preservation_contract_rejects_mutations(change):
    value = history()
    C.validate_history(value)
    if change == "extra":
        value["reset"] = False
    elif change == "bad_name":
        value["frozen_inventory"][0]["name"] = "../other.json"
    elif change == "duplicate":
        value["frozen_inventory"] *= 2
    elif change == "bool_id":
        value["frozen_inventory"][0]["inode"] = True
    elif change == "zero_id":
        value["frozen_inventory"][0]["device"] = 0
    elif change == "new_grant":
        value["grant"] = "SYNTHETIC_UNAUTHORIZED"
    else:
        value["policy"] = "REFUND"
    with pytest.raises(ValueError):
        C.validate_history(value)


@pytest.mark.parametrize("key,value", [("old_intent_sha256", "b" * 64), ("old_objectives_sha256", "c" * 64),
    ("request_bytes", True), ("request_bytes", 0), ("cost_bound_usd", "NaN"), ("cost_bound_usd", "0.1400001"),
    ("cost_bound_usd", "-0.1"), ("request_sha256", "bad"), ("extra", None)])
def test_intent_requires_new_objectives_exact_request_and_bounded_cost(key, value):
    data = intent()
    C.validate_intent(data)
    data[key] = value
    with pytest.raises(ValueError):
        C.validate_intent(data)


@pytest.mark.parametrize("change", ["ids", "title", "case", "spaces", "order", "chapter"])
def test_cosmetic_or_technical_changes_do_not_create_a_new_pedagogical_operation(change):
    _, _, old = rich_preparation()
    new = copy.deepcopy(old)
    if change == "ids":
        new["production_ref"], new["version_ref"] = "prod:new-synthetic", "ver:new-synthetic"
    elif change == "title":
        new["title"] = "SYNTHETIC NEW TITLE"
    elif change == "case":
        new["context"]["objectives"] = [v.upper() for v in old["context"]["objectives"]]
    elif change == "spaces":
        new["context"]["objectives"] = ["  " + v.replace(" ", "   ") + " " for v in old["context"]["objectives"]]
    elif change == "order":
        new["context"]["objectives"].reverse()
        new["references"].reverse()
    else:
        new["context"]["local_progression"]["chapter"] = "9"
    with pytest.raises(ValueError, match="REPLAY_REFUSED"):
        distinct_operation(old, new)


def test_distinct_objectives_only_yield_comparison_not_effect_authority_or_semantic_certification():
    _, _, old = rich_preparation()
    new = copy.deepcopy(old)
    new["context"]["objectives"] = ["Comparer une autre situation pédagogique synthétique indépendante"]
    compared = distinct_operation(old, new)
    assert compared["old_intent_sha256"] != compared["new_intent_sha256"]
    assert set(compared) == {"old_intent_sha256", "new_intent_sha256", "old_objectives_sha256", "new_objectives_sha256"}
    assert not {"authorized", "semantic_approval", "grant", "effect_permitted"} & compared.keys()
    assert operation_projection(old) == operation_projection(copy.deepcopy(old))


def adopted():
    components = dict.fromkeys(C.COMPONENT_FIELDS, "a" * 64)
    book = {"schema": "P1-UNKNOWN-CONTINUITY-BOOK-1.0", "operation": C.OPERATION, "components": components}
    owner = {"schema": "P1-UNKNOWN-CONTINUITY-OWNER-1.0", "operation": C.OPERATION,
        "book_sha256": C.sha(C.canonical(book)), "components": copy.deepcopy(components),
        "new_need_confirmed": True, "unknown_risk_acknowledged": True, "not_a_retry": True}
    pin = C.sha(C.canonical(owner))
    control = {"schema": "P1-UNKNOWN-CONTINUITY-ADOPTION-1.0", "book": descriptor("B.json", owner["book_sha256"]),
        "owner_evidence": descriptor("OWNER.json", pin)}
    return control, book, owner, components, pin


@pytest.mark.parametrize("change", ["missing_trusted_sha", "self_authorized", "retry", "risk", "need", "scope", "book", "component", "extra"])
def test_operation_requires_separate_trusted_human_adoption_and_all_exact_components(change):
    control, book, owner, components, pin = adopted()
    C.validate_adoption(control, book, owner, components=components, expected_owner_sha256=pin, owner_raw_sha256=pin)
    expected = pin
    if change in {"missing_trusted_sha", "self_authorized"}:
        expected = "" if change == "missing_trusted_sha" else "f" * 64
    elif change in {"retry", "risk", "need"}:
        owner[{"retry": "not_a_retry", "risk": "unknown_risk_acknowledged", "need": "new_need_confirmed"}[change]] = False
    elif change == "scope":
        owner["operation"] = "LOCAL_OFF_ONLY"
    elif change == "book":
        control["book"]["sha256"] = "b" * 64
    elif change == "component":
        owner["components"]["package_sha256"] = "b" * 64
    else:
        book["grant"] = "SYNTHETIC_NOT_ALLOWED"
    with pytest.raises(ValueError):
        C.validate_adoption(control, book, owner, components=components, expected_owner_sha256=expected, owner_raw_sha256=pin)


@pytest.mark.parametrize("change", ["expiry", "extension", "calls", "bool_calls", "retry", "parallel", "extra"])
def test_operation_plan_keeps_original_window_and_single_addition(change):
    root = {"issued_at_utc": (NOW - timedelta(days=1)).isoformat(), "expires_at_utc": (NOW + timedelta(days=1)).isoformat()}
    plan = {"schema": "P1-UNKNOWN-CONTINUITY-OPERATION-1.0", "history": descriptor("H.json"), "intent": descriptor("I.json"),
        "profile_adoption": descriptor("profiles.json"), "profile_envelopes": {"off": descriptor("off.json"), "on": descriptor("on.json")},
        "issued_at_utc": (NOW - timedelta(minutes=1)).isoformat(), "expires_at_utc": root["expires_at_utc"],
        "operation": C.OPERATION, "max_new_operations": 1, "retry": 0, "fallback": "NONE", "parallelism": 1}
    C.validate_plan(plan, now=NOW, root=root)
    key, value = {"expiry": ("expires_at_utc", NOW.isoformat()), "extension": ("expires_at_utc", (NOW + timedelta(days=2)).isoformat()),
        "calls": ("max_new_operations", 2), "bool_calls": ("max_new_operations", True), "retry": ("retry", 1),
        "parallel": ("parallelism", 2), "extra": ("quota_reset", False)}[change]
    plan[key] = value
    with pytest.raises(ValueError):
        C.validate_plan(plan, now=NOW, root=root)


@pytest.mark.parametrize("new_consumed,pending", [(0, 0), (0, 1), (1, 0)])
def test_operational_view_counts_only_confirmed_slots_and_preserves_unknown(new_consumed, pending):
    data = {"schema": "P0-UNKNOWN-CONTINUITY-SNAPSHOT-1.0", "state": "PRESERVED_HISTORY_NO_EFFECT_AUTHORITY",
        "timestamp_utc": NOW.isoformat(), "slots_reserved": 3 + new_consumed + pending,
        "consumed_count": 1 + new_consumed, "known_rejected_count": 1, "unknown_count": 1, "pending_count": pending,
        "reserved_budget_usd": "0.3", "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
        "actual_billed_cost_status": "NOT_ESTABLISHED", "effect_permitted": False, "course_qualification": "NOT_COMPLETED"}
    view = P1CampaignInspectionView(data).as_dict()
    assert view["unknown_count"] == 1 and view["pending_count"] == pending and not view["effect_permitted"]
    data["unknown_count"] = 0
    with pytest.raises(ValueError):
        P1CampaignInspectionView(data)
