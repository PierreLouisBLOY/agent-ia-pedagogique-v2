"""Memory-only continuity fixtures; no actual adoption, filesystem or supplier.

All campaign anchors use the same closed factory composition as production,
with entirely synthetic descriptors and proofs. No identity bypass or real pin
monkeypatch exists. Actual native/owner-data qualification remains separate.
"""
import copy
from datetime import UTC, datetime, timedelta

import pytest

from backend.adapters.outbound.generation.openai import p0_product_continuity_contract as C

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)
START = datetime(2026, 10, 11, 19, tzinfo=UTC)
END = datetime(2026, 10, 18, 19, tzinfo=UTC)


def descriptor(name, hash_value="b" * 64):
    return {"path": "C:\\SYNTHETIC_ONLY_NEVER_READ\\" + name, "sha256": hash_value}


def base_permission():
    p = {key: "b" * 64 for key in C.P1_HASHES}
    p.update(schema="P0-PRODUCT-CREATE-PERMISSION-1.0", baseline_commit="1" * 40,
        issued_at_utc=START.isoformat(), expires_at_utc=END.isoformat(),
        allowed_families=["COURSE"], allowed_levels=["FIRST_STMG"],
        selected_admitted_sources_only=True, excluded_oracles_and_private_evidence=True,
        require_exact_local_consent=True, local_operator_delegation_accepted=True,
        provider="OPENAI", model="gpt-5.6-terra", endpoint="https://api.openai.com/v1/responses",
        reasoning="low", tier="default", max_output_tokens=4096, max_calls=14,
        count_calls=0, review_calls=0, modify_calls=0, retry=0, fallback="NONE",
        parallelism=1, per_call_ceiling_usd="0.140000", cumulative_ceiling_usd="1.960000",
        live_authorized=True, transfer_authorized=True)
    return p


def build_origin(permission, profile, delegation, extra_decision=None):
    p = copy.deepcopy(permission)
    p["profile_sha256"] = C.sha(C.canonical(profile))
    p["operator_delegation_sha256"] = C.sha(C.canonical(delegation))
    p["runtime_sha256"] = profile["runtime"]["sha256"]
    p["source_admission_manifest_sha256"] = profile["source_admission_manifest"]["sha256"]
    decision = {"schema": "P0-NORMAL-OWNER-DECISION-2.0", "status": "ADOPTED",
        "profile_sha256": p["profile_sha256"],
        "permission_policy_sha256": C.sha(C.canonical({k: v for k, v in p.items() if k != "owner_decision_sha256"})),
        "source_admission_manifest_sha256": profile["source_admission_manifest"]["sha256"],
        "local_reference_context_manifest_sha256": profile["local_reference_context_manifest"]["sha256"],
        "operator_delegation_sha256": profile["operator_delegation"]["sha256"],
        "tokenizer_manifest_sha256": profile["tokenizer_manifest"]["sha256"],
        "tariff_sha256": profile["tariff"]["sha256"],
        "excluded_oracles_and_private_evidence": True, "source_authority_unknown_preserved": True,
        "local_operator_delegation_accepted": True}
    if extra_decision:
        decision.update(schema="P0-NORMAL-OWNER-DECISION-3.0", **extra_decision)
    p["owner_decision_sha256"] = C.sha(C.canonical(decision))
    envelope = {"schema": "P0-NORMAL-PROFILE-ENVELOPE-1.0", "profile": profile,
        "permission": descriptor("permission.json", C.sha(C.canonical(p))),
        "decision": descriptor("decision.json", p["owner_decision_sha256"])}
    return C.OriginProof(p, envelope, decision, delegation,
        {"windows_sid": delegation["windows_sid"], "windows_profile": delegation["windows_profile"]}, "f" * 64)


def fixtures(monkeypatch):
    delegation = {"schema": "P0-LOCAL-OPERATOR-DELEGATION-1.0",
        "windows_sid": "SYNTHETIC_TEST_SID", "windows_profile": "C:\\SYNTHETIC_TEST_PROFILE",
        "credential_ref": "SYNTHETIC_LOGICAL_NOT_A_SECRET", "local_operator_delegation_accepted": True}
    profile = {key: descriptor(key + ".json") for key in C.DESCRIPTORS}
    profile.update(schema="P0-NORMAL-PROFILE-2.0", baseline_commit="1" * 40,
        runtime={"path": "C:\\SYNTHETIC_TEST_RUNTIME\\qualified.sqlite",
                 "data_root": "C:\\SYNTHETIC_TEST_RUNTIME", "sha256": "b" * 64},
        saved_root="C:\\SYNTHETIC_TEST_SAVED", receipt_root="C:\\SYNTHETIC_TEST_RECEIPTS",
        institutional_catalog_sha256="b" * 64, credential_ref=delegation["credential_ref"],
        local_reference_context_manifest=descriptor("local-manifest.json"))
    profile["operator_delegation"] = descriptor("delegation.json", C.sha(C.canonical(delegation)))
    root = build_origin(base_permission(), profile, delegation)
    anchor = {"schema": "P0-PRODUCT-CONTINUITY-ANCHOR-1.0",
        "implementation_decision": descriptor("SYNTHETIC-owner-implementation.json", "e" * 64),
        "conditions": descriptor("SYNTHETIC-conditions.md", "e" * 64),
        "root_permission_sha256": root.permission_sha256,
        "campaign_namespace_sha256": root.permission["permission_namespace_sha256"],
        "required_historical_reservations": [{"permission_sha256": root.permission_sha256,
            "namespace_sha256": "3" * 64, "request_sha256": "3" * 64, "reserved_usd": "0.0800000",
            "metadata_evidence": descriptor("owner-SYNTHETIC-metadata.json")}]}
    manifest = {"schema": "P0-PRODUCT-CONTINUITY-MANIFEST-1.0",
        "implementation_decision_sha256": anchor["implementation_decision"]["sha256"],
        "conditions_sha256": anchor["conditions"]["sha256"],
        "continuity_anchor": descriptor("SYNTHETIC-continuity-anchor.json", C.sha(C.canonical(anchor))),
        "root_permission_sha256": root.permission_sha256,
        "root_lock_sha256": C.sha(C.canonical({"permission_sha256": root.permission_sha256})),
        "parent_permission_sha256": root.permission_sha256,
        "campaign_namespace_sha256": root.permission["permission_namespace_sha256"],
        "campaign_window": {key: root.permission[key] for key in ("issued_at_utc", "expires_at_utc")},
        "campaign_limits": {key: root.permission[key] for key in C.LIMIT_KEYS},
        "common_identities": {key: root.permission.get(key, root.saved_root_native_sha256) for key in C.COMMON_KEYS},
        "historical_reservations": [{"permission_sha256": root.permission_sha256,
            "namespace_sha256": "3" * 64, "request_sha256": "3" * 64, "reserved_usd": "0.0800000",
            "metadata_evidence": descriptor("owner-SYNTHETIC-metadata.json")}],
        "ancestors": [{"permission_sha256": root.permission_sha256, "parent_permission_sha256": None,
            "permission": root.envelope["permission"],
            "profile_envelope": descriptor("root-profile.json", C.sha(C.canonical(root.envelope))),
            "owner_decision": root.envelope["decision"]}]}
    current_profile = copy.deepcopy(profile)
    current_profile.update(schema="P0-NORMAL-PROFILE-3.0", baseline_commit="2" * 40,
        continuity_manifest=descriptor("continuity.json", C.sha(C.canonical(manifest))),
        continuity_anchor=manifest["continuity_anchor"],
        source_admission_owner_decision=root.envelope["decision"],
        continuity_enabled=False)
    current_permission = copy.deepcopy(root.permission)
    current_permission.update(baseline_commit="2" * 40, source_tree_sha256="c" * 64,
        package_sha256="c" * 64, output_schema_sha256="c" * 64, issued_at_utc=NOW.isoformat())
    current = build_origin(current_permission, current_profile, delegation, {
        "continuity_manifest_sha256": C.sha(C.canonical(manifest)),
        "continuity_anchor_sha256": C.sha(C.canonical(anchor)),
        "parent_permission_sha256": root.permission_sha256,
        "source_admission_owner_decision_sha256": C.sha(C.canonical(root.decision))})
    chain = C.bind_chain(manifest, [root], current, ancestor_manifests={}, anchor=anchor)
    return manifest, root, current, chain


def slot(origin, n):
    grant = {key: origin.permission.get(key, str(n) * 64) for key in C.HASH_FIELDS}
    grant.update(baseline_commit=origin.permission["baseline_commit"], request_bytes=123,
        schema="P0-NORMAL-CREATE-GRANT-1.0", operation="CREATE", provider="OPENAI",
        model="gpt-5.6-terra", endpoint="https://api.openai.com/v1/responses",
        reasoning="low", tier="default", max_output_tokens=4096, max_calls=1,
        count_calls=0, review_calls=0, modify_calls=0, retry=0, fallback="NONE",
        parallelism=1, ceiling_usd="0.140000", live_authorized=True, transfer_authorized=True,
        issued_at_utc=NOW.isoformat(), expires_at_utc=(NOW + timedelta(minutes=120)).isoformat())
    return {"schema": "P0-PRODUCT-BUDGET-SLOT-1.0", "permission_sha256": origin.permission_sha256,
        "preview_sha256": str(n) * 64, "command_id": str(n) * 32, "grant": grant,
        "grant_sha256": C.sha(C.canonical(grant)), "namespace_sha256": grant["namespace_sha256"],
        "request_sha256": grant["request_sha256"], "preflight_sha256": str(n) * 64,
        "reserved_usd": "0.0800000"}


def events(record):
    result = {}
    for n, state in enumerate(C.EVENT_ORDER):
        response = state == "RESPONSE_CAPTURED"
        result[state] = {"schema": "P0-NORMAL-TECHNICAL-RECEIPT-1.0",
            **{key: record[key] for key in ("grant_sha256", "request_sha256", "preflight_sha256", "namespace_sha256", "reserved_usd")},
            "state": state, "timestamp_utc": (NOW + timedelta(seconds=n)).isoformat(),
            "provider_attempts": 0 if state == "RESERVED" else 1,
            "response_status": "completed" if response else None,
            "response_artifact_sha256": "e" * 64 if response else None,
            "usage": {"input_tokens": 10, "output_tokens": 20} if response else None,
            "observed_cost_status": "NOT_ESTABLISHED"}
    return result


def test_synthetic_exact_dag_and_common_reservations_off(monkeypatch):
    _, root, current, chain = fixtures(monkeypatch)
    records = [slot(root, 3), slot(current, 4)]
    for record in records:
        name = chain.manifest["campaign_namespace_sha256"] + ".P1." + record["preview_sha256"] + ".json"
        C.validate_slot(chain, record, file_name=name)
        C.validate_events(record, events(record))
    snapshot = C.metadata(chain, records, now=NOW)
    assert snapshot["slots_reserved"] == 2 and snapshot["remaining_calls"] == 12
    assert snapshot["reserved_budget_usd"] == "0.1600000"
    assert snapshot["remaining_reserved_budget_usd"] == "1.8000000"
    assert snapshot["live_enabled"] is False
    with pytest.raises(ValueError, match="NOT_ACTIVATED"):
        C.require_effect_enabled(chain, now=NOW, family="COURSE", level="FIRST_STMG")


@pytest.mark.parametrize("mutation", ["root", "parent", "cycle", "extra", "limits", "unknown_source_owner"])
def test_closed_dag_mutations_refuse(monkeypatch, mutation):
    manifest, root, current, chain = fixtures(monkeypatch)
    manifest = copy.deepcopy(manifest)
    if mutation == "root":
        manifest["root_permission_sha256"] = "0" * 64
    elif mutation == "parent":
        manifest["parent_permission_sha256"] = "0" * 64
    elif mutation == "cycle":
        manifest["ancestors"][0]["parent_permission_sha256"] = root.permission_sha256
    elif mutation == "extra":
        manifest["hidden_authority"] = True
    elif mutation == "limits":
        manifest["campaign_limits"]["max_calls"] = 15
    elif mutation == "unknown_source_owner":
        current.envelope["profile"]["source_admission_owner_decision"]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        C.bind_chain(manifest, [root], current, ancestor_manifests={}, anchor=chain.anchor)


@pytest.mark.parametrize("mutation", ["unknown_permission", "old_grant_new_owner", "reserved_zero", "grant_hash"])
def test_slot_origin_mutations_refuse(monkeypatch, mutation):
    _, root, current, chain = fixtures(monkeypatch)
    record = slot(root, 3)
    if mutation == "unknown_permission":
        record["permission_sha256"] = "0" * 64
    elif mutation == "old_grant_new_owner":
        record["permission_sha256"] = current.permission_sha256
    elif mutation == "reserved_zero":
        record["reserved_usd"] = "0"
    elif mutation == "grant_hash":
        record["grant_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        C.validate_slot(chain, record, file_name=chain.manifest["campaign_namespace_sha256"] + ".P1." + record["preview_sha256"] + ".json")


@pytest.mark.parametrize("mutation", ["unknown", "rejected", "parsed_missing", "consumed_missing", "amount", "order", "bool_attempt"])
def test_unknown_partial_or_changed_lifecycle_never_frees_budget(monkeypatch, mutation):
    _, root, _, _ = fixtures(monkeypatch)
    record = slot(root, 3)
    lifecycle = events(record)
    if mutation == "unknown":
        lifecycle["UNKNOWN"] = {}
    elif mutation == "rejected":
        lifecycle["PARSING_REJECTED"] = {}
    elif mutation == "parsed_missing":
        lifecycle.pop("PARSED")
    elif mutation == "consumed_missing":
        lifecycle.pop("CONSUMED")
    elif mutation == "amount":
        lifecycle["CONSUMED"]["reserved_usd"] = "0.01"
    elif mutation == "order":
        lifecycle["PARSED"]["timestamp_utc"] = START.isoformat()
    elif mutation == "bool_attempt":
        lifecycle["PROVIDER_ATTEMPTED"]["provider_attempts"] = True
    with pytest.raises(ValueError):
        C.validate_events(record, lifecycle)
    assert record["reserved_usd"] == "0.0800000"


def test_exact_own_pending_only_and_old_recovery_refused(monkeypatch):
    _, root, current, chain = fixtures(monkeypatch)
    record = slot(current, 4)
    identity = object()
    pending = C.OwnPending(identity, current.permission_sha256, record["command_id"],
        record["grant_sha256"], record["namespace_sha256"], record["request_sha256"],
        record["preflight_sha256"], "d" * 64, (NOW + timedelta(minutes=15)).isoformat())
    kwargs = dict(broker_identity=identity, dispatch_sha256="d" * 64, now=NOW,
        existing_p0_events=[])
    assert C.allow_own_transition(chain, record, pending, **kwargs)
    assert not C.allow_own_transition(chain, record, pending, **{**kwargs, "broker_identity": object()})
    assert not C.allow_own_transition(chain, record, pending, **{**kwargs, "existing_p0_events": ["RESERVED"]})
    assert not C.allow_own_transition(chain, record, pending, **{**kwargs, "now": NOW + timedelta(minutes=16)})
    assert not C.allow_own_transition(chain, slot(root, 3), pending, **kwargs)
    with pytest.raises(ValueError, match="OLD_GRANT_CURRENT_RECOVERY_REFUSED"):
        C.assert_current_recovery(chain, slot(root, 3))
    C.assert_current_recovery(chain, record)




@pytest.mark.parametrize("position", ["before_permission", "after_permission"])
def test_grant_must_remain_in_origin_window(monkeypatch, position):
    _, root, _, chain = fixtures(monkeypatch)
    record = slot(root, 3)
    start = START - timedelta(minutes=1) if position == "before_permission" else END - timedelta(minutes=1)
    record["grant"].update(issued_at_utc=start.isoformat(), expires_at_utc=(start + timedelta(minutes=2)).isoformat())
    record["grant_sha256"] = C.sha(C.canonical(record["grant"]))
    with pytest.raises(ValueError, match="GRANT_ORIGIN_WINDOW"):
        C.validate_slot(chain, record, file_name=chain.manifest["campaign_namespace_sha256"] + ".P1." + record["preview_sha256"] + ".json")


@pytest.mark.parametrize("mutation", ["missing", "changed_amount", "changed_request", "empty_witness"])
def test_attested_old_reservation_cannot_be_omitted(monkeypatch, mutation):
    _, root, _, chain = fixtures(monkeypatch)
    record = slot(root, 3)
    records = [record]
    if mutation == "missing":
        records = []
    elif mutation == "changed_amount":
        record["reserved_usd"] = "0.01"
    elif mutation == "changed_request":
        record["request_sha256"] = "0" * 64
    elif mutation == "empty_witness":
        chain.manifest["historical_reservations"] = []
    with pytest.raises(ValueError):
        C.metadata(chain, records, now=NOW)


@pytest.mark.parametrize("kind", ["exact_campaign_orphan", "unknown_campaign", "missing_dispatch"])
def test_orphan_namespace_never_assumed_foreign_or_charged_here(monkeypatch, kind):
    _, root, _, chain = fixtures(monkeypatch)
    extra = slot(root, 5)
    capture = {"grant": extra["grant"]}
    if kind == "unknown_campaign":
        capture["grant"]["owner_decision_sha256"] = "0" * 64
    elif kind == "missing_dispatch":
        capture = None
    with pytest.raises(ValueError, match="RECEIPT_ORPHAN|CAMPAIGN_UNIDENTIFIED"):
        C.reject_orphan_namespaces(chain, [slot(root, 3)], normal_namespaces={extra["namespace_sha256"]: capture})


@pytest.mark.parametrize("mutation", ["runtime_path", "runtime_data_root", "profile_catalog", "tokenizer_path", "tariff_hash"])
def test_profile_common_cannot_change_after_synthetic_rebinding(monkeypatch, mutation):
    manifest, root, current, chain = fixtures(monkeypatch)
    changed_profile = copy.deepcopy(current.envelope["profile"])
    if mutation == "runtime_path":
        changed_profile["runtime"]["path"] = "C:\\SYNTHETIC_OTHER_RUNTIME\\qualified.sqlite"
    elif mutation == "runtime_data_root":
        changed_profile["runtime"]["data_root"] = "C:\\SYNTHETIC_OTHER_RUNTIME"
    elif mutation == "profile_catalog":
        changed_profile["institutional_catalog_sha256"] = "0" * 64
    elif mutation == "tokenizer_path":
        changed_profile["tokenizer_manifest"]["path"] = "C:\\SYNTHETIC_OTHER_TOKENIZER\\tokenizer.json"
    elif mutation == "tariff_hash":
        changed_profile["tariff"]["sha256"] = "0" * 64
    changed = build_origin(current.permission, changed_profile, current.delegation, {
        "continuity_manifest_sha256": C.sha(C.canonical(manifest)),
        "continuity_anchor_sha256": C.sha(C.canonical(chain.anchor)),
        "parent_permission_sha256": root.permission_sha256,
        "source_admission_owner_decision_sha256": C.sha(C.canonical(root.decision))})
    with pytest.raises(ValueError, match="RUNTIME_LOCATION_CHANGED|PROFILE_CATALOG_BINDING|PROFILE_COMMON"):
        C.bind_chain(manifest, [root], changed, ancestor_manifests={}, anchor=chain.anchor)


@pytest.mark.parametrize("kind", ["absent", "empty", "changed_descriptor", "hidden_field"])
def test_private_anchor_is_required_and_bound_not_http_authority(monkeypatch, kind):
    manifest, root, current, chain = fixtures(monkeypatch)
    anchor = copy.deepcopy(chain.anchor)
    if kind == "absent":
        anchor = None
    elif kind == "empty":
        anchor["required_historical_reservations"] = []
    elif kind == "changed_descriptor":
        anchor["conditions"]["sha256"] = "0" * 64
    elif kind == "hidden_field":
        anchor["new_live_authority"] = True
    with pytest.raises(ValueError):
        C.bind_chain(manifest, [root], current, ancestor_manifests={}, anchor=anchor)

@pytest.mark.parametrize("raw", [b'{"same":1,"same":2}', b'{"nested":{"same":1,"same":2}}',
    b'{"value":NaN}', b'{"value":Infinity}', b'{"value":-Infinity}', b'[]', b'null', b'{', b'\xff'])
def test_historical_technical_metadata_parser_refuses_ambiguous_nonfinite_nonobject_or_invalid(raw):
    from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
        _decode_historical_metadata,
    )

    with pytest.raises(ValueError, match="P0_CONTINUITY_HISTORICAL_METADATA_"):
        _decode_historical_metadata(raw)
