"""Declared native failure doubles; no real P1 bindings, credentials or provider."""
import errno
import json
from dataclasses import replace
from secrets import token_hex

import pytest

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.openai.contracts import (
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from tests.integration.test_p0_product_unknown_continuation_native import (
    baseline,
    case,
    configured,
)
from tests.integration.test_p0_product_unknown_off_native import facts

__all__ = ["baseline", "case"]
CANARY = "SYNTHETIC_PRIVATE_EXCEPTION_AUTHORIZATION_PASSAGE_BODY"


def consent(data):
    prepared, endpoint = data["prepared"], data["endpoint"]
    command = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"]}
    shown = endpoint.consent_execute("consent_preview", command)
    return {**command, "preview_sha256": shown["preview_sha256"],
        "transfer_accepted": True, "cost_bound_accepted": True}


@pytest.mark.parametrize("point,stage", [
    ("transport", "TRANSPORT_CREATE"), ("metadata", "RESPONSE_METADATA"),
    ("RESULT", "RESULT_PUBLISH"), ("diagnostic", None), ("CONSUMED", "CONSUMED_PUBLISH"),
])
def test_native_failed_addition_keeps_slot_and_never_resends(case, monkeypatch, capsys, caplog, point, stage):
    data = configured(case)
    root = case[0]["root"]
    before = facts(root)
    historical = {row["namespace_sha256"] for row in case[0]["records"]}
    try:
        command = consent(data)
        if point in {"transport", "diagnostic"}:
            error = OpenAITransportError(OpenAITransportErrorCode.CONNECTION)
            error.args = (CANARY,)
            data["transport"].failure = error
        elif point == "metadata":
            data["transport"].response = replace(data["transport"].response, usage=None)
        else:
            original = P0NormalReceipt.publish

            def fail_result(self, name, value):
                if self.namespace not in historical and name == point:
                    raise OSError(errno.EIO, CANARY)
                return original(self, name, value)

            monkeypatch.setattr(P0NormalReceipt, "publish", fail_result)
        if point == "diagnostic":
            def fail_diagnostic(self, value):
                raise OSError(errno.EIO, CANARY)
            monkeypatch.setattr(P0NormalReceipt, "publish_failure_diagnostic", fail_diagnostic)

        endpoint = data["endpoint"]
        status, _, raw, _ = endpoint.respond("POST", "/api/v2/p0/consent-generate", canonical(command), "SYNTHETIC")
        assert status in {409, 500}
        assert CANARY not in raw.decode() + str(capsys.readouterr()) + caplog.text
        assert data["transport"].calls == data["resolver"].calls == 1
        slots = [json.loads(p.read_bytes()) for p in root.glob(data["comp"]._ledger().prefix + "*.json")]
        added = [r for r in slots if r["namespace_sha256"] not in historical]
        assert len(slots) == 4 and len(added) == 1
        receipt = P0NormalReceipt(root, added[0]["namespace_sha256"])
        assert receipt.exists("RESERVED") and not receipt.exists("CONSUMED")
        assert receipt.exists("UNKNOWN") is (point != "CONSUMED")
        assert not receipt.exists("PARSING_REJECTED")
        proof = receipt.read("DISPATCH")["preflight"]
        diagnostic = receipt.read_failure_diagnostic(grant=added[0]["grant"], preflight=proof)
        if stage is None:
            assert diagnostic is None
        else:
            assert diagnostic["stage"] == stage and CANARY not in json.dumps(diagnostic)
        preserved = facts(root)
        # Even a fresh preview/command cannot turn the retained fourth slot into capacity.
        with pytest.raises(ValueError):
            consent(data)
        with pytest.raises(ValueError):
            endpoint.consent_execute("consent_generate", command)
        assert facts(root) == preserved
        assert all(preserved[name] == value for name, value in before.items())
        assert data["transport"].calls == data["resolver"].calls == 1
    finally:
        data["comp"].close()


def test_native_history_mutation_omission_replacement_and_orphan_refuse_before_secret(case):
    data = configured(case)
    root, tmp = case[0]["root"], case[2]
    before = facts(root)
    path = root / (case[0]["selected"]["namespace_sha256"] + ".UNKNOWN.json")
    try:
        raw = path.read_bytes()
        path.write_bytes(raw + b"\n")
        with pytest.raises(ValueError, match="FROZEN_HISTORY_CHANGED"):
            consent(data)
        path.write_bytes(raw)
        parked = tmp / "SYNTHETIC-original-UNKNOWN-retained.bin"
        path.rename(parked)
        try:
            with pytest.raises(ValueError, match="FROZEN_HISTORY_CHANGED"):
                consent(data)
            path.write_bytes(raw)
            with pytest.raises(ValueError, match="FROZEN_HISTORY_CHANGED"):
                consent(data)
            path.rename(tmp / "SYNTHETIC-replacement-retained.bin")
        finally:
            parked.rename(path)
        orphan = root / ("f" * 64 + ".RESERVED.json")
        orphan.write_bytes(canonical({"SYNTHETIC_ORPHAN": True}))
        try:
            with pytest.raises(ValueError):
                consent(data)
        finally:
            orphan.rename(tmp / "SYNTHETIC-orphan-retained.bin")
        assert facts(root) == before
        assert data["transport"].calls == data["resolver"].calls == 0
    finally:
        data["comp"].close()


def test_native_lock_contention_and_missing_fresh_consent_never_reserve(case):
    data = configured(case)
    root = case[0]["root"]
    before = facts(root)
    try:
        with data["comp"]._ledger().locked():
            with pytest.raises(ValueError, match="CONCURRENT_DISPATCH"):
                consent(data)
        command = consent(data)
        with pytest.raises(ValueError, match="CONSENT_REQUIRED"):
            data["endpoint"].consent_execute("consent_generate", {**command, "transfer_accepted": False})
        assert facts(root) == before
        assert data["resolver"].calls == data["transport"].calls == 0
    finally:
        data["comp"].close()
