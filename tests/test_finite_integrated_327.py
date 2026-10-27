"""Normal CLI and complete source guards, native parent, synthetic effects only."""

import json
import time

from tests import finite_chain_325_fixture as x
from tests.test_finite_chain_325 import preview
from tests.test_normal_on_323a import call


def native_parent(port):
    status, metadata = call(port, "GET", "/api/v2/p0")
    assert status == 200
    nonce = metadata["data"]["transport_nonce"]
    status, prepared = call(
        port,
        "POST",
        "/api/v2/p0/prepare",
        {
            "command_id": "1" * 32,
            "context": x.f.context(),
            "reference": {"notion_id": "notion:shared", "passage_ref": x.f.SOURCE["passage_ref"]},
        },
        nonce,
    )
    assert status == 200, prepared
    status, result = call(
        port,
        "POST",
        "/api/v2/p0/local-propose",
        {
            "command_id": "2" * 32,
            **{k: prepared["data"][k] for k in ("preparation_ref", "preparation_sha256")},
        },
        nonce,
    )
    assert status == 200 and result["data"]["provider_attempts"] == 0, result
    return nonce, result["data"]["view"]


def configuration(root, *, total=None):
    config, descriptor = x.configuration(root)
    if total is None:
        return config, descriptor
    startup = json.loads(open(descriptor["path"], encoding="utf-8").read())
    policy = json.loads(open(startup["policy"]["path"], encoding="utf-8").read())
    decision = json.loads(open(startup["decision"]["path"], encoding="utf-8").read())
    policy["cumulative_ceiling_usd"] = total
    decision["policy_sha256"] = x.sha(x.canonical(policy))
    startup["policy"] = x.f.artifact(root, "SYNTHETIC-budget-refusal-policy.json", policy)
    startup["decision"] = x.f.artifact(root, "SYNTHETIC-budget-refusal-decision.json", decision)
    return config, x.f.artifact(root, "SYNTHETIC-budget-refusal-startup.json", startup)


def test_budget_refusal_from_actual_launcher_has_no_reservation_or_transport(tmp_path, monkeypatch):
    root = tmp_path / "SYNTHETIC-budget327"
    config = configuration(root, total="0.140000")
    control = x.Control()
    control.seed = {}
    with x.running(root, monkeypatch, control, existing=config) as (port, _):
        nonce, view = native_parent(port)
        status, result = call(
            port,
            "POST",
            "/api/v2/p0/codesign-preview",
            {
                "command_id": "a" * 32,
                **{k: view[k] for k in ("production_ref", "version_ref", "bundle_sha256")},
                "direction": "V2_TO_AI",
                "objective": "Clarifier le titre",
                "evidence_query": None,
            },
            nonce,
        )
        assert status == 409 and result["error"]["code"] == "P0_CHAIN_CUMULATIVE_BUDGET_STOP", (
            result
        )
        assert control.calls == 0
        with control.binding.broker.ledger.locked(create=False):
            assert control.binding.broker.ledger.slots() == []


def test_crash_reopen_consultation_and_duplicate_never_resend(tmp_path, monkeypatch):
    root = tmp_path / "SYNTHETIC-crash327"
    config = configuration(root)
    control = x.Control()
    control.seed = {}
    with x.running(root, monkeypatch, control, existing=config) as (port, _):
        nonce, view = native_parent(port)
        _, command = preview(port, nonce, view)
        control.scenario = "crash"
        assert call(port, "POST", "/api/v2/p0/codesign-consent", command, nonce)[0] == 202
        assert control.entered.wait(120)
        # A test-only interruption at the transport leaves retained uncertainty.
        deadline = time.monotonic() + 10
        while (
            control.binding.broker.active is not None
            or control.binding.broker.pending_command is not None
        ) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(control.chain_calls) == 1
        retained = control.binding.broker.observe(command["command_id"])
        assert retained["state"] == "LOCAL_COMMAND_RETAINED_UNCERTAIN", retained
        assert retained["authority_restored"] is False
        assert call(port, "POST", "/api/v2/p0/codesign-consent", command, nonce)[0] == 202
        assert len(control.chain_calls) == 1
        before = x.canonical(retained["effects"])
    new_control = x.Control()
    new_control.seed = {}
    with x.running(root, monkeypatch, new_control, existing=config) as (port, _):
        status, result = call(port, "GET", "/api/v2/p0/commands/" + command["command_id"])
        assert status == 200 and result["data"]["state"] == "LOCAL_COMMAND_RETAINED_UNCERTAIN", (
            result
        )
        assert new_control.calls == 0 and new_control.prompt_calls == 0
        assert x.canonical(result["data"]["effects"]) == before
