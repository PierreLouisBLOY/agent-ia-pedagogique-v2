"""325 finite authority through actual normal launcher, SDK adapters and R4."""

from datetime import timedelta
from decimal import Decimal

import pytest

from tests import finite_chain_325_fixture as x
from tests.test_normal_on_323a import call, terminal


def parent(port, control):
    status, metadata = call(port, "GET", "/api/v2/p0")
    assert status == 200, metadata
    view = control.seed
    status, reopened = call(
        port, "GET", "/api/v2/p0/versions/" + view["production_ref"] + "/" + view["version_ref"]
    )
    assert status == 200 and reopened["data"]["bundle_sha256"] == view["bundle_sha256"], reopened
    return metadata["data"]["transport_nonce"], view


def preview(port, nonce, view, *, direction="V2_TO_AI"):
    request = {
        "command_id": "a" * 32,
        "production_ref": view["production_ref"],
        "version_ref": view["version_ref"],
        "bundle_sha256": view["bundle_sha256"],
        "direction": direction,
        "objective": "Clarifier le titre",
        "evidence_query": None,
    }
    status, result = call(port, "POST", "/api/v2/p0/codesign-preview", request, nonce)
    assert status == 200, result
    shown = result["data"]
    command = {
        **request,
        "command_id": "b" * 32,
        "preview_sha256": shown["preview_sha256"],
        "evidence_query": shown["evidence_query"],
        "transfer_accepted": True,
        "cost_bound_accepted": True,
    }
    return shown, command


@pytest.mark.parametrize("direction", ("V2_TO_AI", "AI_TO_V2"))
@pytest.mark.parametrize("correction", (False, True))
def test_normal_launcher_finite_exact_roles_saved_reopen_and_word(
    tmp_path, monkeypatch, direction, correction
):
    control = x.Control(correction=correction)
    with x.running(tmp_path / "SYNTHETIC325", monkeypatch, control) as (port, config):
        nonce, view = parent(port, control)
        shown, command = preview(port, nonce, view, direction=direction)
        assert (
            shown["authority"] == "NONE" and shown["first_request_bytes"] > 0 and control.calls == 1
        )
        control.entered.clear()
        control.release.clear()
        assert call(port, "POST", "/api/v2/p0/codesign-consent", command, nonce)[0] == 202
        assert control.entered.wait(120), (
            call(port, "GET", "/api/v2/p0/commands/" + command["command_id"]),
            control.diagnostics,
        )
        status, following = call(port, "GET", "/api/v2/p0/commands/" + command["command_id"])
        assert status == 200 and following["data"]["state"] == "LOCAL_COMMAND_RUNNING", following
        assert following["data"]["phase"] == "PROPOSE_TRANSPORT_ENTERED"
        repeated = call(port, "POST", "/api/v2/p0/codesign-consent", command, nonce)
        assert repeated[0] == 202 and control.calls == 2
        control.release.set()
        result = terminal(port, command["command_id"])
        assert result["state"] == "LOCAL_COMMAND_COMPLETED", result
        final = result["result"]
        assert final["state"] == "CODESIGN_CANDIDATE", final
        assert len(control.chain_calls) == (4 if correction else 2)
        assert control.prompt_calls == 0
        broker = control.binding.broker
        with broker.ledger.locked(create=False):
            slots = broker.ledger.slots()
        chain = [s for s in slots if s["schema"] == "P0-FINITE-CHAIN-SLOT-2.0"]
        assert [s["grant"]["role"] for s in chain] == list(x.ROLES[: len(chain)]) or sorted(
            s["grant"]["ordinal"] for s in chain
        ) == list(range(len(chain)))
        assert len(slots) == 1 + len(chain)
        assert sum(Decimal(s["reserved_usd"]) for s in chain) <= Decimal(shown["chain_bound_usd"])
        current = final["view"]
        base = (
            "/api/v2/productions/"
            + current["production_ref"]
            + "/versions/"
            + current["version_ref"]
        )
        assert call(port, "GET", base + "/saved")[0] == 200
        assert call(port, "GET", base + "/compare/student")[0] == 200
        for kind in ("student", "correction"):
            status, raw = x.f.request(port, "GET", base + "/word/" + kind)
            assert status == 200 and raw[:2] == b"PK"
        before = control.calls
        assert call(port, "POST", "/api/v2/p0/codesign-consent", command, nonce)[0] == 202
        assert control.calls == before


@pytest.mark.parametrize(
    "condition", ("transfer", "cost", "expired", "identity", "revoked", "tokenizer")
)
def test_no_effect_without_exact_conditions(tmp_path, monkeypatch, condition):
    control = x.Control()
    with x.running(tmp_path / "SYNTHETIC325", monkeypatch, control) as (port, _):
        nonce, view = parent(port, control)
        shown, command = preview(port, nonce, view)
        broker = control.binding.broker
        if condition == "transfer":
            command["transfer_accepted"] = False
        if condition == "cost":
            command["cost_bound_accepted"] = False
        if condition == "expired":
            old = broker.clock()
            broker.clock = lambda: old + timedelta(minutes=16)
        if condition == "identity":
            command["bundle_sha256"] = "f" * 64
        if condition == "revoked":
            assert (
                call(
                    port,
                    "POST",
                    "/api/v2/p0/codesign-revoke",
                    {"command_id": "c" * 32, "preview_sha256": shown["preview_sha256"]},
                    nonce,
                )[0]
                == 200
            )
        if condition == "tokenizer":
            control.token_delta = 1
        status, _ = call(port, "POST", "/api/v2/p0/codesign-consent", command, nonce)
        if status == 202:
            result = terminal(port, command["command_id"])
            assert result["state"] == "LOCAL_COMMAND_UNCERTAIN", result
        else:
            assert status == 409
        assert control.calls == 1 and control.chain_calls == []
        with broker.ledger.locked(create=False):
            assert len(broker.ledger.slots()) == 1


@pytest.mark.parametrize("scenario", ("timeout", "partial", "malformed", "late"))
def test_uncertain_or_rejected_stops_chain_retains_slot_and_never_retries(
    tmp_path, monkeypatch, scenario
):
    control = x.Control()
    with x.running(tmp_path / "SYNTHETIC325", monkeypatch, control) as (port, _):
        nonce, view = parent(port, control)
        _, command = preview(port, nonce, view)
        control.scenario = scenario
        assert call(port, "POST", "/api/v2/p0/codesign-consent", command, nonce)[0] == 202
        result = terminal(port, command["command_id"])
        assert result["state"] == "LOCAL_COMMAND_RETAINED_UNCERTAIN", result
        assert len(control.chain_calls) == 1
        broker = control.binding.broker
        # Passive read is intentionally distinct from any finalization/retry.
        broker.clock = lambda: x.datetime.now(x.UTC)
        retained = broker.observe(command["command_id"])
        assert retained["state"] == "LOCAL_COMMAND_RETAINED_UNCERTAIN"
        assert len(retained["effects"]) == 1 and retained["authority_restored"] is False
        assert call(port, "POST", "/api/v2/p0/codesign-consent", command, nonce)[0] == 202
        assert len(control.chain_calls) == 1
