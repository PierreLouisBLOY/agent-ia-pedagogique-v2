"""Synthetic closed V2 evidence and adoption mutations, no native/business I/O."""

import copy
from datetime import UTC, datetime

import pytest

from backend.adapters.outbound.generation.openai import p0_product_rejected_continuity_contract as C
from backend.infrastructure.composition.factories.p0_rejected_profile_contract import (
    validate_external_adoption,
)
from tests.unit.test_p0_product_continuity import descriptor

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def evidence():
    data = {key: "a" * 64 for key in C.EVIDENCE_FIELDS if key.endswith("_sha256")}
    data.update(
        schema="P0-PRODUCT-KNOWN-REJECTED-EVIDENCE-1.0",
        observation_state="OBSERVED_NOT_ADOPTED",
        request_bytes=100,
        reserved_usd="0.07",
        command_id="a" * 32,
        response_status="completed",
        provider_attempts=1,
        event_sha256s=dict.fromkeys(C.REJECTED_ORDER, "b" * 64),
        event_timestamps=dict.fromkeys(C.REJECTED_ORDER, NOW.isoformat()),
        usage={
            "input_tokens": 100,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": 50,
            "reasoning_tokens": 0,
            "total_tokens": 150,
        },
        disposition=C.DISPOSITION,
        local_rejection_code="P0_RICH_COURSE_NOTION_UNKNOWN",
        owner_orientation_adoption=descriptor("SYNTHETIC-orientation.json"),
        owner_diagnostic=descriptor("SYNTHETIC-diagnostic.json"),
        transport_metadata_scope=C.TRANSPORT_SCOPE,
        qualification="REJECTED_NOT_CONSUMED",
        timestamp_utc=NOW.isoformat(),
    )
    return data


def disposition(data):
    witness = descriptor("SYNTHETIC-observed.json", C.sha(C.canonical(data)))
    selected = {
        key: data[{"permission_sha256": "origin_permission_sha256"}.get(key, key)]
        for key in C.TARGET_FIELDS
    }
    return {
        "schema": "P0-PRODUCT-KNOWN-REJECTED-DISPOSITION-1.0",
        "disposition": C.DISPOSITION,
        "target_attempt": selected,
        "observed_evidence": witness,
        "observed_evidence_sha256": witness["sha256"],
        "adoption_decision": data["owner_orientation_adoption"],
        "owner_orientation_adoption": data["owner_orientation_adoption"],
        "owner_diagnostic": data["owner_diagnostic"],
        "source_origin_manifest_sha256": "c" * 64,
        "operation": "READ_ONLY_RECONCILIATION",
        "no_grant_reuse": True,
        "preserve_reservation": True,
        "no_runtime_mutation": True,
    }


def test_closed_evidence_and_disposition_have_no_consumed_or_effect_authority():
    data = evidence()
    C.validate_evidence(data)
    C.validate_disposition(disposition(data), data)
    assert "output_text" not in data and "remaining_calls" not in data


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "request_bool",
        "attempt_bool",
        "completed",
        "consumed",
        "transport_claim",
        "negative_usage",
        "bool_usage",
        "usage_total",
        "cached_over",
        "reasoning_over",
        "output_over",
        "zero_reserve",
        "nan",
        "bad_hash",
        "missing_event",
        "event_hash",
        "time_offset",
    ],
)
def test_evidence_mutations_refuse(mutation):
    data = evidence()
    if mutation == "extra":
        data["live_authorized"] = True
    elif mutation == "request_bool":
        data["request_bytes"] = True
    elif mutation == "attempt_bool":
        data["provider_attempts"] = True
    elif mutation == "completed":
        data["response_status"] = "incomplete"
    elif mutation == "consumed":
        data["qualification"] = "CONSUMED"
    elif mutation == "transport_claim":
        data["transport_metadata_scope"] = "default"
    elif mutation == "negative_usage":
        data["usage"]["input_tokens"] = -1
    elif mutation == "bool_usage":
        data["usage"]["input_tokens"] = True
    elif mutation == "usage_total":
        data["usage"]["total_tokens"] = 151
    elif mutation == "cached_over":
        data["usage"]["cached_input_tokens"] = 101
    elif mutation == "reasoning_over":
        data["usage"]["reasoning_tokens"] = 51
    elif mutation == "output_over":
        data["usage"]["output_tokens"] = 4097
    elif mutation in {"zero_reserve", "nan"}:
        data["reserved_usd"] = "0" if mutation == "zero_reserve" else "NaN"
    elif mutation == "bad_hash":
        data["result_sha256"] = "X" * 64
    elif mutation == "missing_event":
        data["event_sha256s"].pop("PARSING_REJECTED")
    elif mutation == "event_hash":
        data["event_sha256s"]["RESERVED"] = "bad"
    else:
        data["timestamp_utc"] = "2026-01-01T00:00:00+01:00"
    with pytest.raises(ValueError):
        C.validate_evidence(data)


@pytest.mark.parametrize(
    "mutation",
    ["hidden", "reuse", "refund", "write", "cyclic_decision", "target", "evidence", "descriptor"],
)
def test_disposition_never_self_adopts_reuses_or_returns_reserve(mutation):
    data = evidence()
    item = copy.deepcopy(disposition(data))
    if mutation == "hidden":
        item["approved"] = True
    elif mutation in {"reuse", "refund", "write"}:
        item[
            {
                "reuse": "no_grant_reuse",
                "refund": "preserve_reservation",
                "write": "no_runtime_mutation",
            }[mutation]
        ] = False
    elif mutation == "cyclic_decision":
        item["adoption_decision"] = item["observed_evidence"]
    elif mutation == "target":
        item["target_attempt"]["permission_sha256"] = "0" * 64
    elif mutation == "evidence":
        item["observed_evidence_sha256"] = "0" * 64
    else:
        item["observed_evidence"]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        C.validate_disposition(item, data)


def external_fixture():
    components = {
        "observed_evidence_sha256": "a" * 64,
        "disposition_sha256": "b" * 64,
        "anchor2_sha256": "c" * 64,
        "manifest2_sha256": {"off": "d" * 64, "on": "e" * 64},
        "profile4_OFF_sha256": "f" * 64,
        "profile4_ON_sha256": "1" * 64,
        "source_manifest_sha256": "2" * 64,
        "package_sha256": "3" * 64,
    }
    book = {
        "schema": "P0-KNOWN-REJECTED-COMPONENT-BOOK-1.0",
        "operation": "OFF_ON_COMPONENT_REBIND",
        "components": components,
    }
    owner = {
        "schema": "LU-OWNER-KNOWN-REJECTED-EXACT-ADOPTION-1.0",
        "source": "DIRECT_HUMAN_ASYNC_QUESTION_REPLY",
        "question_call_id": "SYNTHETIC_NOT_HUMAN_ADOPTION",
        "proposal_sha256": C.sha(C.canonical(book)),
        "answer_exact": "ADOPTED_EXACT_COMPONENTS",
        "scope": "OFF_ON_COMPONENT_REBIND",
        "human_cryptographic_signature_claimed": False,
    }
    owner_sha = C.sha(C.canonical(owner))
    control = {
        "schema": "P0-KNOWN-REJECTED-EXTERNAL-ADOPTION-1.0",
        "operation": "OFF_ON_COMPONENT_REBIND",
        "book": descriptor("SYNTHETIC-book.json", C.sha(C.canonical(book))),
        "owner_evidence": descriptor("SYNTHETIC-owner.json", owner_sha),
        "expected_owner_evidence_sha256": owner_sha,
        "profile_envelopes": {
            "off": descriptor("SYNTHETIC-off.json"),
            "on": descriptor("SYNTHETIC-on.json"),
        },
    }
    return control, book, owner, owner_sha, components


def test_final_adoption_is_external_to_components_with_two_distinct_manifests():
    control, book, owner, owner_sha, components = external_fixture()
    validate_external_adoption(
        control,
        book=book,
        owner_evidence=owner,
        owner_raw_sha256=owner_sha,
        expected_owner_raw_sha256=owner_sha,
        components=components,
        operation="OFF_ON_COMPONENT_REBIND",
    )
    assert "owner_evidence" not in book and "profile_envelopes" not in book


@pytest.mark.parametrize(
    "mutation",
    [
        "approved_flag",
        "answer_only",
        "wrong_expected",
        "scope",
        "proposal",
        "crypto",
        "pair_extra",
        "pair_same",
        "pair_scalar",
    ],
)
def test_external_adoption_refuses_unbound_or_self_declared_authority(mutation):
    control, book, owner, owner_sha, components = external_fixture()
    expected = owner_sha
    if mutation == "approved_flag":
        control["approved"] = True
    elif mutation == "answer_only":
        owner.pop("question_call_id")
    elif mutation == "wrong_expected":
        expected = "0" * 64
    elif mutation == "scope":
        owner["scope"] = "INSPECTION_ONLY"
    elif mutation == "proposal":
        owner["proposal_sha256"] = "0" * 64
    elif mutation == "crypto":
        owner["human_cryptographic_signature_claimed"] = True
    elif mutation == "pair_extra":
        components["manifest2_sha256"]["hidden"] = "0" * 64
    elif mutation == "pair_same":
        components["manifest2_sha256"]["on"] = components["manifest2_sha256"]["off"]
    else:
        components["manifest2_sha256"] = "d" * 64
    with pytest.raises(ValueError):
        validate_external_adoption(
            control,
            book=book,
            owner_evidence=owner,
            owner_raw_sha256=owner_sha,
            expected_owner_raw_sha256=expected,
            components=components,
            operation="OFF_ON_COMPONENT_REBIND",
        )


def test_native_read_phase_rejects_invalid_kind_and_missing_lock_before_io():
    from backend.infrastructure.composition.factories.p0_rejected_readset import (
        NativeP0RejectedReadPhases,
    )

    def no_lock():
        raise ValueError("SYNTHETIC_NO_NATIVE_LOCK")

    def forbidden():
        raise AssertionError("No filesystem/proof call before valid lock scope")

    phase = NativeP0RejectedReadPhases(
        lock_scope=no_lock, collect=forbidden, full_chain=forbidden, fresh=lambda _: forbidden()
    )
    with pytest.raises(ValueError, match="SCOPE_REFUSED"):
        with phase.phase("UNKNOWN"):
            forbidden()
    with pytest.raises(ValueError, match="NO_NATIVE_LOCK"):
        with phase.phase("PREVIEW"):
            forbidden()
    with pytest.raises(ValueError, match="PROOF_SCOPE_REFUSED"):
        phase.require_proof()
    assert not phase.has_proof and phase._lease is None


def test_native_readset_rejects_empty_and_over_capacity_before_native_calls():
    from pathlib import Path

    from backend.infrastructure.composition.factories.p0_rejected_readset import (
        WindowsImmutableReadSet,
    )

    with pytest.raises(ValueError, match="FILE_BOUND"):
        WindowsImmutableReadSet({})
    files = {Path(f"SYNTHETIC_{i}"): (Path("SYNTHETIC"), "0" * 64) for i in range(4097)}
    with pytest.raises(ValueError, match="FILE_BOUND"):
        WindowsImmutableReadSet(files)


@pytest.mark.parametrize("mutation", [None, "body", "dispatch", "preflight", "grant", "grant_bool", "reserve", "attempt_bool", "reserve_time", "pending", "broker"])
def test_preprovider_reserved_pending_checks_actual_bindings(monkeypatch, mutation):
    from types import SimpleNamespace

    from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
    from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
        OwnPending,
    )
    from backend.infrastructure.composition.factories.p0_rejected_profile import (
        P0RejectedProductComposition,
    )
    from tests.unit.test_p0_product_continuity import NOW as CURRENT_TIME
    from tests.unit.test_p0_product_continuity import fixtures, slot

    _, _, current, chain = fixtures(monkeypatch)
    record = slot(current, 4)
    body, dispatch, proof = "SYNTHETIC", {"synthetic": "dispatch"}, {"cost_bound_usd": record["reserved_usd"]}
    record["grant"].update(request_bytes=len(body.encode()), request_sha256=C.sha(body.encode()))
    record.update(grant_sha256=C.sha(C.canonical(record["grant"])), request_sha256=C.sha(body.encode()), preflight_sha256=C.sha(C.canonical(proof)))
    identity = object()
    pending = OwnPending(identity, current.permission_sha256, record["command_id"], record["grant_sha256"], record["namespace_sha256"], record["request_sha256"], record["preflight_sha256"], C.sha(C.canonical(dispatch)), record["grant"]["expires_at_utc"])
    ledger = SimpleNamespace(_pending=pending, _pending_dispatch_sha256=pending.dispatch_sha256, broker_identity=identity, clock=lambda: CURRENT_TIME)
    receipt = SimpleNamespace(namespace=pending.namespace_sha256)
    receipt.event = lambda *args: P0NormalReceipt.event(receipt, *args)
    capture = {"schema": "P0-NORMAL-DISPATCH-CAPTURE-1.0", **{key: record[key] for key in ("grant_sha256", "request_sha256", "preflight_sha256", "namespace_sha256")}, "dispatch_sha256": pending.dispatch_sha256, "grant": copy.deepcopy(record["grant"]), "dispatch": dispatch, "body": body, "preflight": proof}
    reserved = receipt.event("RESERVED", record["grant"], proof)
    reserved["timestamp_utc"] = CURRENT_TIME.isoformat()
    receipt.read = lambda name: {"DISPATCH": capture, "RESERVED": reserved}[name]
    if mutation == "body":
        capture["body"] += " "
    elif mutation == "dispatch":
        capture["dispatch"] = {"synthetic": "another dispatch"}
    elif mutation == "preflight":
        capture["preflight"] = {"cost_bound_usd": "0"}
    elif mutation == "grant":
        capture["grant"]["request_bytes"] += 1
    elif mutation == "grant_bool":
        capture["grant"]["max_calls"] = True
    elif mutation == "reserve":
        reserved["request_sha256"] = "e" * 64
    elif mutation == "attempt_bool":
        reserved["provider_attempts"] = False
    elif mutation == "reserve_time":
        reserved["timestamp_utc"] = record["grant"]["expires_at_utc"]
    elif mutation == "pending":
        ledger._pending_dispatch_sha256 = "e" * 64
    elif mutation == "broker":
        ledger.broker_identity = object()
    composition = object.__new__(P0RejectedProductComposition)
    if mutation is None:
        composition._read_reserved_pending(chain, record, receipt, ledger)
    else:
        with pytest.raises(ValueError, match="P0_READSET_OWN_"):
            composition._read_reserved_pending(chain, record, receipt, ledger)


@pytest.mark.parametrize("states,expected", [
    (("RESERVED",), "OWN_PENDING_STAGE"),
    (("DISPATCH",), "OWN_PENDING_STAGE"),
    (("PARSED",), "OWN_PENDING_STAGE"),
    (("CONSUMED",), "OWN_PENDING_STAGE"),
    (("RESERVED", "DISPATCH", "PARSED", "CONSUMED"), "OWN_PENDING_STAGE"),
    (("RESERVED", "DISPATCH", "PROVIDER_ATTEMPTED"), "OWN_PENDING_STAGE"),
    (("UNKNOWN",), "OWN_PENDING_STAGE"),
    (("PARSING_REJECTED",), "OWN_PENDING_STAGE"),
    (("ORPHAN_RESERVED",), "NORMAL_CAMPAIGN_UNIDENTIFIED"),
    (("AMBIGUOUS_RESERVED",), "NORMAL_NAMESPACE_AMBIGUOUS"),
])
def test_readset_fresh_actual_pending_stages_and_new_orphans_refuse(tmp_path, monkeypatch, states, expected):
    from types import SimpleNamespace

    from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
        P0ContinuityProductLedger,
    )
    from backend.infrastructure.composition.factories import p0_rejected_profile as F

    root = tmp_path / "SYNTHETIC_RECEIPTS"
    code = tmp_path / "SYNTHETIC_CODE"
    root.mkdir()
    for name in ("backend", "frontend", "tools", "config"):
        (code / name).mkdir(parents=True)
    namespace, prefix = "a" * 64, "SYNTHETIC_SLOT_"
    slot_path = root / (prefix + "b" * 64 + ".json")
    slot_path.write_bytes(C.canonical({"namespace_sha256": namespace}))
    for state in states:
        name = namespace + "." + state + ".json"
        if state == "ORPHAN_RESERVED":
            name = "e" * 64 + ".RESERVED.json"
        elif state == "AMBIGUOUS_RESERVED":
            name = "AMBIGUOUS.RESERVED.json"
        (root / name).write_bytes(C.canonical({"synthetic": True}))
    ledger = SimpleNamespace(root=root, prefix=prefix, _pending=SimpleNamespace(namespace_sha256=namespace), pin=SimpleNamespace(_root_unchanged=lambda: None))
    ledger._normal_namespaces = lambda: P0ContinuityProductLedger._normal_namespaces(ledger)
    composition = object.__new__(F.P0RejectedProductComposition)
    composition.root, composition.application_root, composition.saved_root = root, code, tmp_path / "SYNTHETIC_SAVED"
    composition.target = SimpleNamespace(validate=lambda: None)
    composition.generation = SimpleNamespace(ledger=ledger)
    composition.read_phases = SimpleNamespace(protected_paths=(slot_path,))
    chain = SimpleNamespace(current=SimpleNamespace(operator={"synthetic": True}, saved_root_native_sha256=C.sha(C.canonical({})), envelope={"profile": {"source_manifest": {}}}), origins=())
    monkeypatch.setattr(F, "windows_operator", lambda: {"synthetic": True})
    monkeypatch.setattr(F, "_native", lambda _: {})
    monkeypatch.setattr(F, "read_descriptor", lambda _: {"files": {}})
    with pytest.raises(ValueError, match=expected):
        composition._read_fresh(chain)
