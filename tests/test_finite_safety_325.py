"""Finite owner/SDK/ledger tests with declared synthetic identity/source ports."""

from copy import deepcopy
from datetime import timedelta
from threading import Thread

import pytest

from backend.adapters.outbound.generation.openai.p0_finite_chain import FiniteChainBroker
from backend.adapters.outbound.generation.openai.p0_normal_policy import HASH_FIELDS, canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    validate_events,
)
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    check_budget,
    prospective_grant,
)
from tests.finite_component_325_fixture import component


def submit(c):
    return c.service.execute("codesign-consent", c.command)


@pytest.mark.parametrize("correction", (False, True))
def test_real_sdk_adapters_and_native_roles_are_finite(tmp_path, correction):
    c = component(tmp_path / "SYNTHETIC", correction=correction)
    result = submit(c)
    assert result["state"] == "CODESIGN_CANDIDATE"
    assert len(c.control.chain_calls) == (4 if correction else 2)
    assert c.state.secret_reads == 1
    before = c.control.calls
    assert submit(c) == result and c.control.calls == before
    with c.ledger.locked(create=False):
        slots = c.ledger.slots()
    assert len(slots) == before
    assert c.permission["max_calls"] == 1


@pytest.mark.parametrize(
    "failure",
    (
        "transfer",
        "cost",
        "expired",
        "changed",
        "revoked",
        "unadopted",
        "disabled",
        "key_missing",
        "tokenizer_changed",
        "expiry_during_preflight",
        "expiry_at_first_slot",
    ),
)
def test_no_effect_without_all_conditions(tmp_path, failure):
    c = component(tmp_path / "SYNTHETIC")
    if failure == "transfer":
        c.command["transfer_accepted"] = False
    if failure == "cost":
        c.command["cost_bound_accepted"] = False
    if failure == "expired":
        c.state.clock += timedelta(minutes=16)
    if failure == "changed":
        c.command["bundle_sha256"] = "f" * 64
    if failure == "revoked":
        c.broker.revoke(c.shown["preview_sha256"])
    if failure == "unadopted":
        c.broker.decision.update(
            status="PROPOSED",
            financial_evidence_admitted=False,
            additional_finite_right_accepted=False,
        )
    if failure == "disabled":
        c.broker.enabled = False
    if failure == "key_missing":

        def absent():
            assert c.ledger._held_thread is None
            raise ValueError("P0_CHAIN_SYNTHETIC_KEY_ABSENT")

        c.broker.prepare_credential = absent
    if failure == "tokenizer_changed":
        c.state.token_delta = 1
    if failure == "expiry_during_preflight":
        actual = c.broker.prepare_credential

        def delayed():
            actual()
            c.state.clock = c.state.clock + timedelta(minutes=16)

        c.broker.prepare_credential = delayed
    if failure == "expiry_at_first_slot":

        def delayed_count(count):
            if count == 3:
                c.state.clock += timedelta(minutes=16)

        c.state.on_count = delayed_count
    if failure == "expiry_at_first_slot":
        assert submit(c)["state"] != "CODESIGN_CANDIDATE"
    else:
        with pytest.raises(ValueError):
            submit(c)
    assert c.control.calls == 0
    with c.ledger.locked(create=False):
        assert c.ledger.slots() == []
    if failure in {"transfer", "cost", "expired", "changed", "revoked", "unadopted", "disabled"}:
        assert c.state.secret_reads == 0


@pytest.mark.parametrize("scenario", ("timeout", "partial", "malformed", "late", "crash"))
def test_captured_or_uncertain_response_stops_without_retry(tmp_path, scenario):
    c = component(tmp_path / "SYNTHETIC", scenario=scenario)
    try:
        result = submit(c)
        assert result["state"] != "CODESIGN_CANDIDATE"
    except (ValueError, SystemExit):
        pass
    assert c.control.calls == 1
    view = c.broker.observe(c.command["command_id"])
    assert view["state"] == "LOCAL_COMMAND_RETAINED_UNCERTAIN"
    assert view["authority_restored"] is False and len(view["effects"]) == 1
    c.broker.observe(c.command["command_id"])
    assert c.control.calls == 1
    # New process owner has no live capability: consult but never resume.
    other = P0ProductLedger(root=c.ledger.root, permission=c.permission)
    restarted = FiniteChainBroker(**{**c.args, "ledger": other})
    assert restarted.observe(c.command["command_id"])["state"] == "LOCAL_COMMAND_RETAINED_UNCERTAIN"
    assert c.control.calls == 1
    with pytest.raises(ValueError):
        restarted.preview(c.request)


def test_two_submissions_and_revocation_while_transport_is_slow(tmp_path):
    c = component(tmp_path / "SYNTHETIC")
    c.control.release.clear()
    outcomes = []

    def work():
        try:
            outcomes.append(submit(c))
        except ValueError as error:
            outcomes.append(str(error))

    worker = Thread(target=work)
    worker.start()
    try:
        assert c.control.entered.wait(10)
        assert c.service.execute("codesign-consent", c.command)["state"] == "LOCAL_COMMAND_RUNNING"
        observed = c.broker.observe(c.command["command_id"])
        assert observed["phase"] == "PROPOSE_TRANSPORT_ENTERED"
        different = {**c.command, "command_id": "c" * 32}
        with pytest.raises(ValueError, match="P0_CHAIN_CONCURRENT_COMMAND"):
            c.service.execute("codesign-consent", different)
        c.broker.revoke(c.shown["preview_sha256"])
    finally:
        c.control.release.set()
        worker.join(20)
    assert not worker.is_alive() and c.control.calls == 1
    assert isinstance(outcomes[0], str) or outcomes[0]["state"] != "CODESIGN_CANDIDATE"
    assert c.broker.observe(c.command["command_id"])["state"] == "LOCAL_COMMAND_RETAINED_UNCERTAIN"


def test_refused_next_preflight_never_rewrites_previous_consumed_receipt(tmp_path):
    c = component(tmp_path / "SYNTHETIC")
    saved = {}

    def before_second(count):
        if count == 4:
            with_own = c.ledger.slots()
            namespace = with_own[0]["namespace_sha256"]
            saved.update(
                {p.name: p.read_bytes() for p in c.ledger.root.glob(str(namespace) + ".*.json")}
            )

    c.state.on_count = before_second
    c.state.fail_count_at = 4
    try:
        result = submit(c)
        assert result["state"] != "CODESIGN_CANDIDATE"
    except ValueError:
        pass
    assert c.control.calls == 1 and saved
    assert all((c.ledger.root / name).read_bytes() == raw for name, raw in saved.items())
    assert not any(p.name.endswith(".PARSING_REJECTED.json") for p in c.ledger.root.glob("*.json"))


def pending_legacy(c):
    body = b"{}"
    grant = {key: "2" * 64 for key in HASH_FIELDS}
    grant.update({k: c.permission[k] for k in HASH_FIELDS & c.permission.keys()})
    grant.update(request_sha256=sha(body), request_bytes=len(body), namespace_sha256="6" * 64)
    grant = prospective_grant(
        c.permission, {**grant, "baseline_commit": c.permission["baseline_commit"]}, c.state.clock
    )
    proof = {"cost_bound_usd": "0.08", "request_sha256": sha(body), "request_bytes": len(body)}
    with c.ledger.locked(create=False):
        c.ledger.reserve(grant=grant, preview_sha256="7" * 64, command_id="8" * 32, preflight=proof)
        receipt = P0NormalReceipt(c.ledger.root, "6" * 64)
        receipt.reserve(
            grant=grant, dispatch={"declared": "SYNTHETIC_ORIGIN"}, body=body, preflight=proof
        )
    # Read by the real ledger without the finite extension for fixture setup only.
    old = P0ProductLedger(root=c.ledger.root, permission=c.permission)
    with old.locked(create=False):
        slot = old.slots()[0]
    return slot, receipt, grant, proof


def test_reservation_not_reported_before_publisher_acknowledgement(tmp_path, monkeypatch):
    c = component(tmp_path / "SYNTHETIC")
    observations = []

    def denied(path, raw):
        observations.append(c.broker._summary())
        raise OSError("SYNTHETIC_WRITE_REFUSED")

    monkeypatch.setattr(c.ledger, "_publish", denied)
    try:
        result = submit(c)
        assert result["state"] != "CODESIGN_CANDIDATE"
    except ValueError:
        pass
    assert observations and observations[0]["effects_reserved"] == 0
    assert c.control.calls == 0


def test_legacy_uncertainty_needs_exact_disposition_and_late_completion_invalidates_it(tmp_path):
    c = component(tmp_path / "SYNTHETIC")
    slot, receipt, grant, proof = pending_legacy(c)
    with (
        c.ledger.locked(create=False),
        pytest.raises(ValueError, match="P0_CHAIN_EXACT_HISTORICAL_DISPOSITION_REQUIRED"),
    ):
        c.ledger.slots()
    policy = deepcopy(c.policy)
    policy["retained_origins"] = [dict(c.broker.retained_origin_snapshot(slot))]
    decision = {**c.decision, "policy_sha256": sha(canonical(policy))}
    old = P0ProductLedger(root=c.ledger.root, permission=c.permission)
    broker = FiniteChainBroker(**{**c.args, "ledger": old, "policy": policy, "decision": decision})
    with old.locked(create=False):
        assert len(old.slots()) == 1
    # The exhausted CREATE remains exhausted despite a new financial envelope.
    with pytest.raises(ValueError):
        check_budget(
            c.permission,
            [__import__("decimal").Decimal("0.08")],
            __import__("decimal").Decimal("0.01"),
        )
    receipt.publish("PROVIDER_ATTEMPTED", receipt.event("PROVIDER_ATTEMPTED", grant, proof))
    usage = {
        "input_tokens": 1,
        "cached_input_tokens": 0,
        "output_tokens": 1,
        "reasoning_tokens": 0,
        "total_tokens": 2,
        "cache_write_input_tokens": 0,
    }
    artifact = {
        "schema": "P0-NORMAL-CONFIRMED-RESULT-1.0",
        "grant_sha256": slot["grant_sha256"],
        "request_sha256": grant["request_sha256"],
        "dispatch_sha256": sha(canonical({"declared": "SYNTHETIC_ORIGIN"})),
        "response_status": "completed",
        "output_text": "SYNTHETIC_CAPTURE",
        "usage": usage,
    }
    pin = receipt.publish("RESULT", artifact)
    receipt.publish(
        "RESPONSE_CAPTURED",
        receipt.event(
            "RESPONSE_CAPTURED", grant, proof, artifact=pin, status="completed", usage=usage
        ),
    )
    for state in ("PARSED", "CONSUMED"):
        receipt.publish(state, receipt.event(state, grant, proof))
    assert receipt.confirmed(grant) is not None
    validate_events(
        slot,
        {
            s: receipt.read(s)
            for s in ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED")
        },
    )
    with (
        old.locked(create=False),
        pytest.raises(ValueError, match="P0_CHAIN_EXACT_HISTORICAL_DISPOSITION_REQUIRED"),
    ):
        old.slots()
    assert broker.active is None
