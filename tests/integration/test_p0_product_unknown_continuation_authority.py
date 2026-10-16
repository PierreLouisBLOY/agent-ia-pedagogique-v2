"""Synthetic exact adoption and live-capability refusals on the native composition."""
import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from secrets import token_hex

import pytest

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical
from backend.infrastructure.composition.factories.p0_unknown_continuation import (
    P0UnknownContinuationComposition,
)
from tests.integration.test_p0_product_rejected_continuity_native import artifact
from tests.integration.test_p0_product_unknown_continuation_native import baseline, case, configured
from tests.integration.test_p0_product_unknown_off_native import facts

__all__ = ["baseline", "case"]


def preview(data):
    command = {"command_id": token_hex(16), **{k: data["prepared"][k] for k in ("preparation_ref", "preparation_sha256")}}
    shown = data["endpoint"].consent_execute("consent_preview", command)
    return {**command, "preview_sha256": shown["preview_sha256"], "transfer_accepted": True,
        "cost_bound_accepted": True}, shown


@pytest.mark.parametrize("flag", ["new_need_confirmed", "unknown_risk_acknowledged", "not_a_retry"])
def test_native_missing_exact_operation_authority_cannot_construct_writer(case, flag):
    before = facts(case[0]["root"])
    with pytest.raises(ValueError, match="EXACT_ADOPTION_REQUIRED"):
        configured(case, mutate_owner=lambda value: value.update({flag: False}))
    assert facts(case[0]["root"]) == before


def test_native_exactly_adopted_false_historical_result_still_refuses(case):
    base = case[0]
    original = base["acquired"]
    import json
    report = json.loads(Path(original["path"]).read_bytes())
    report["provider_calls"] = 1
    base["acquired"] = artifact(case[2], "SYNTHETIC-false-acquired-result.json", canonical(report))
    before = facts(base["root"])
    try:
        with pytest.raises(ValueError, match="ACQUIRED_RESULT_BINDING"):
            configured(case)
        assert facts(base["root"]) == before
    finally:
        base["acquired"] = original


def test_native_adopted_wrong_request_hash_never_previews_or_resolves(case):
    data = configured(case, mutate_intent=lambda value: value.update(request_sha256="0" * 64))
    before = facts(case[0]["root"])
    try:
        with pytest.raises(ValueError, match="NEW_PREPARATION_BINDING"):
            preview(data)
        assert facts(case[0]["root"]) == before
        assert data["resolver"].calls == data["transport"].calls == 0
    finally:
        data["comp"].close()


@pytest.mark.parametrize("fault", ["absent", "substituted", "expired"])
def test_native_reserved_slot_does_not_restore_capacity_or_transfer_live_pending(case, fault):
    data = configured(case)
    generation = data["comp"].generation
    before = facts(case[0]["root"])
    try:
        command, shown = preview(data)
        generation.accept(request=data["request"], consent=command, source_receipts=shown["source_receipts"])
        capability_key = next(iter(generation.pending_capabilities))
        if fault == "absent":
            generation.pending_capabilities.pop(capability_key)
        elif fault == "substituted":
            changed = copy.copy(generation.pending_capabilities[capability_key])
            # Mutate only this declared test double, not a genuine persisted grant.
            object.__setattr__(changed, "broker_identity", object())
            generation.pending_capabilities[capability_key] = changed
        else:
            generation.clock = lambda: datetime.now(UTC) + timedelta(days=7)
        with pytest.raises(ValueError):
            generation.generate(request=data["request"])
        preserved = facts(case[0]["root"])
        assert len(preserved) == len(before) + 1
        assert all(preserved[name] == value for name, value in before.items())
        assert data["resolver"].calls == data["transport"].calls == 0
        # Restarting the writer cannot reconstruct OwnPending from that slot.
        with pytest.raises(ValueError):
            P0UnknownContinuationComposition(**data["args"])
        assert facts(case[0]["root"]) == preserved
    finally:
        data["comp"].close()
