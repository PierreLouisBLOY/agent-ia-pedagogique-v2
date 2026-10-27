"""Actual Windows protocol on new synthetic fixtures, never owner data/provider."""
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

import pytest

from backend.adapters.outbound.generation.openai.p0_content import CONTENT_FIELDS
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    COMMON_KEYS,
    LIMIT_KEYS,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
    P0ContinuityProductLedger,
)
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
)
from backend.infrastructure.composition.factories.p0_normal_profile import (
    P0NormalProductComposition,
)
from backend.infrastructure.filesystem import capture_secure_path
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests.integration.test_p0_local_reference_context_composition import composed, prepare
from tests.support.p0_generation_double import P0GenerationDouble
from tests.unit.test_p0_normal_generation import SyntheticResolver, SyntheticTransport
from tests.unit.test_p0_normal_policy import fixture as financial_fixture
from tests.unit.test_p0_normal_profile import artifact, local_context_profile_fixture


def native_identity(path):
    identity = capture_secure_path(path, allowed_root=path)
    return sha(canonical({"path": str(path), "device": identity.device, "inode": identity.inode}))


def install_doubles(composition, dispatch):
    generated = P0GenerationDouble().generate(request=dispatch)
    if dispatch["context"]["resource_type"] == "COURSE":
        # The transport fixture emits the actual explained-course contract;
        # no validator/response is repaired after the adapter receives it.
        generated = {**generated, "sections": [{"section_id": "S_" + role, "heading": heading,
            "text": text} for role, heading, text in (
            ("OBJECTIVES", "Objectifs synthétiques", "Observer un cas de test et expliciter une démarche locale."),
            ("EXPLAINED_NOTIONS", "Notions expliquées", "Une notion de test est définie puis reliée aux observations du cas synthétique."),
            ("METHOD", "Méthode", "Identifier les informations disponibles, les comparer puis justifier la conclusion."),
            ("GUIDED_APPLICATION", "Application guidée", "Sur les données fictives du harnais, décrire les indices qui soutiennent une réponse."),
            ("SYNTHESIS", "Synthèse", "Retenir la démarche de comparaison ; aucun contenu du harnais n’est un cours propriétaire."))]}
    content = {key: as_plain(generated[key]) for key in CONTENT_FIELDS}
    response = OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, canonical(content).decode(),
        OpenAIResponseUsage(1000, 0, 100, 1100, reasoning_tokens=0), service_tier="default")
    resolver, transport = SyntheticResolver(), SyntheticTransport(response)
    composition.generation.resolver, composition.generation.transport = resolver, transport
    # Recognition data is an explicitly synthetic double, never the real Terra
    # tokenizer. The production F1 contract and exact manifest binding execute.
    tokenizer = financial_fixture()[5]
    composition.generation.tokenizer = lambda body: {**tokenizer, "request_sha256": sha(body),
        "manifest_sha256": composition.permission["tokenizer_manifest_sha256"]}
    return resolver, transport


def send_once(composition, app, endpoint, selection, reference):
    prepared = prepare(app, selection, reference, "BTS_CG_YEAR_2")
    dispatch = as_plain(app.prepared[prepared["preparation_ref"]])
    resolver, transport = install_doubles(composition, dispatch)
    command = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"]}
    status, _, raw, _ = endpoint.respond("POST", "/api/v2/p0/consent-preview", canonical(command), "SYNTHETIC")
    assert status == 200, raw
    shown = json.loads(raw)["data"]
    consent = {**command, "preview_sha256": shown["preview_sha256"], "transfer_accepted": True, "cost_bound_accepted": True}
    status, _, raw, _ = endpoint.respond("POST", "/api/v2/p0/consent-generate", canonical(consent), "SYNTHETIC")
    assert status == 200, raw
    assert json.loads(raw)["data"]["state"] == "CANDIDATE", raw
    assert resolver.calls == transport.calls == 1
    return dispatch, resolver, transport


def root_with_actual_lifecycle(tmp_path, monkeypatch, *, metadata_format="canonical"):
    path, target, saved, code, envelope, _ = local_context_profile_fixture(tmp_path, monkeypatch)
    root = P0NormalProductComposition(path=path, target=target, saved_root=saved, application_root=code)
    app, endpoint, _, selection, reference, *_ = composed(monkeypatch)
    app.generation = root.generation
    root.bind(app, endpoint)
    dispatch, resolver, transport = send_once(root, app, endpoint, selection, reference)
    slot = root.generation.ledger.slots()[0]
    receipt = P0NormalReceipt(root.root, slot["namespace_sha256"])
    events = {state: {**receipt.read(state), "receipt_sha256": sha(canonical(receipt.read(state)))}
        for state in ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED")}
    metadata = {"schema": "LU-P1-OWNER-EXACT-RECEIPT-METADATA-1.0", "source_commit": root.permission["baseline_commit"],
        "permission_sha256": sha(canonical(root.permission)), "campaign_namespace_sha256": root.permission["permission_namespace_sha256"],
        "slot_namespace_sha256": slot["namespace_sha256"], "request_sha256": slot["request_sha256"],
        "flags": {**{state: True for state in events}, "UNKNOWN": False, "PARSING_REJECTED": False},
        "events": events, "raw_output_text_disclosed": False}
    metadata_raw = canonical(metadata) if metadata_format == "canonical" else (json.dumps(metadata, indent=2) + "\n").encode()
    evidence = artifact(tmp_path, "SYNTHETIC_actual_protocol_metadata.json", metadata_raw)
    witness = {key: slot[key] for key in ("permission_sha256", "namespace_sha256", "request_sha256", "reserved_usd")}
    witness["metadata_evidence"] = evidence
    anchor = {"schema": "P0-PRODUCT-CONTINUITY-ANCHOR-1.0",
        "implementation_decision": artifact(tmp_path, "SYNTHETIC_implementation_not_an_owner_adoption.json", canonical({"schema": "SYNTHETIC_ONLY"})),
        "conditions": artifact(tmp_path, "SYNTHETIC_conditions.txt", b"SYNTHETIC FIXTURE CONDITIONS; NO OWNER AUTHORITY"),
        "root_permission_sha256": sha(canonical(root.permission)), "campaign_namespace_sha256": root.permission["permission_namespace_sha256"],
        "required_historical_reservations": [witness]}
    anchor_desc = artifact(tmp_path, "SYNTHETIC_private_anchor.json", canonical(anchor))
    return root, target, saved, code, app, endpoint, selection, reference, dispatch, resolver, transport, witness, anchor, anchor_desc


def successor(tmp_path, parent, root, target, saved, code, witness, anchor, anchor_desc, *, enabled, name):
    nodes = []
    if parent.continuity:
        nodes = json.loads(Path(parent.profile["continuity_manifest"]["path"]).read_bytes())["ancestors"]
    nodes.append({"permission_sha256": sha(canonical(parent.permission)), "parent_permission_sha256": None if parent is root else
        json.loads(Path(parent.profile["continuity_manifest"]["path"]).read_bytes())["parent_permission_sha256"],
        "permission": parent.envelope["permission"],
        "profile_envelope": {"path": str(parent.path), "sha256": sha(parent.path.read_bytes())},
        "owner_decision": parent.envelope["decision"]})
    manifest = {"schema": "P0-PRODUCT-CONTINUITY-MANIFEST-1.0",
        "implementation_decision_sha256": anchor["implementation_decision"]["sha256"], "conditions_sha256": anchor["conditions"]["sha256"],
        "continuity_anchor": anchor_desc, "root_permission_sha256": sha(canonical(root.permission)),
        "root_lock_sha256": sha(canonical({"permission_sha256": sha(canonical(root.permission))})),
        "parent_permission_sha256": sha(canonical(parent.permission)), "campaign_namespace_sha256": root.permission["permission_namespace_sha256"],
        "campaign_window": {key: root.permission[key] for key in ("issued_at_utc", "expires_at_utc")},
        "campaign_limits": {key: root.permission[key] for key in LIMIT_KEYS},
        "common_identities": {key: native_identity(saved) if key == "saved_root_native_sha256" else root.permission[key] for key in COMMON_KEYS},
        "ancestors": nodes, "historical_reservations": [witness]}
    manifest_desc = artifact(tmp_path, name + "_manifest.json", canonical(manifest))
    profile = copy.deepcopy(root.profile)
    profile.update(schema="P0-NORMAL-PROFILE-3.0", continuity_manifest=manifest_desc, continuity_anchor=anchor_desc,
        source_admission_owner_decision=root.envelope["decision"], continuity_enabled=enabled)
    permission = {**root.permission, "issued_at_utc": datetime.now(UTC).isoformat(), "profile_sha256": sha(canonical(profile))}
    decision = {**root.decision, "schema": "P0-NORMAL-OWNER-DECISION-3.0", "profile_sha256": permission["profile_sha256"],
        "permission_policy_sha256": sha(canonical({key: value for key, value in permission.items() if key != "owner_decision_sha256"})),
        "continuity_manifest_sha256": manifest_desc["sha256"], "continuity_anchor_sha256": anchor_desc["sha256"],
        "parent_permission_sha256": sha(canonical(parent.permission)),
        "source_admission_owner_decision_sha256": root.envelope["decision"]["sha256"]}
    dec_desc = artifact(tmp_path, name + "_SYNTHETIC_not_an_owner_decision.json", canonical(decision))
    permission["owner_decision_sha256"] = dec_desc["sha256"]
    permission_desc = artifact(tmp_path, name + "_SYNTHETIC_not_live_permission.json", canonical(permission))
    envelope = {"schema": "P0-NORMAL-PROFILE-ENVELOPE-1.0", "profile": profile, "decision": dec_desc, "permission": permission_desc}
    env_desc = artifact(tmp_path, name + "_SYNTHETIC_envelope.json", canonical(envelope))
    result = P0NormalProductComposition(path=Path(env_desc["path"]), target=target, saved_root=saved, application_root=code)
    return result


def test_actual_windows_normal_protocol_continues_root_off_on_under_same_lock(tmp_path, monkeypatch):
    (root, target, saved, code, app, endpoint, selection, reference, old_dispatch, old_resolver, old_transport,
        witness, anchor, anchor_desc) = root_with_actual_lifecycle(tmp_path, monkeypatch)
    old_slot = root.generation.ledger.slots()[0]
    old_files = {path.name: path.read_bytes() for path in root.root.iterdir() if path.is_file()}
    off = successor(tmp_path, root, root, target, saved, code, witness, anchor, anchor_desc, enabled=False, name="off")
    off.bind(app, endpoint)
    try:
        status, _, raw, _ = endpoint.respond("GET", "/api/v2/p0", b"", "SYNTHETIC")
        assert status == 200, raw
        view = json.loads(raw)["data"]
        assert view["live_binding"] == view["normal_consent_binding"] == "NONE"
        assert view["campaign_snapshot"]["slots_reserved"] == 1
        assert view["campaign_snapshot"]["live_enabled"] is False
        assert app.generation is None and endpoint.consent_execute is None
        assert old_resolver.calls == old_transport.calls == 1
        on = successor(tmp_path, off, root, target, saved, code, witness, anchor, anchor_desc, enabled=True, name="on")
        on_app, on_endpoint, _, selection, reference, *_ = composed(monkeypatch)
        on_app.generation = on.generation
        on.bind(on_app, on_endpoint)
        try:
            assert on.permission["profile_sha256"] != off.permission["profile_sha256"]
            assert on.permission["permission_namespace_sha256"] == root.permission["permission_namespace_sha256"]
            assert isinstance(on.generation.ledger, P0ContinuityProductLedger)
            with root.generation.ledger.locked():
                with pytest.raises(ValueError, match="CONCURRENT_DISPATCH"):
                    on.generation.campaign_snapshot()
            before = on.generation.campaign_snapshot()
            assert before["slots_reserved"] == 1 and before["live_enabled"] is True
            with pytest.raises(ValueError, match="OLD_GRANT_CURRENT_RECOVERY_REFUSED"):
                on.generation.recover_confirmed(request=old_dispatch)
            _, new_resolver, new_transport = send_once(on, on_app, on_endpoint, selection, reference)
            after = on.generation.campaign_snapshot()
            assert after["slots_reserved"] == 2
            assert after["remaining_calls"] == root.permission["max_calls"] - 2
            slots = on.generation.ledger.slots()
            assert old_slot in slots and len(slots) == 2
            assert after["reserved_budget_usd"] != before["reserved_budget_usd"]
            assert after["financial_basis"] == "RESERVATIONS_NOT_BILLED_COST"
            assert new_resolver.calls == new_transport.calls == 1
            assert {name: (root.root / name).read_bytes() for name in old_files} == old_files
        finally:
            on.close()
    finally:
        off.close()
        root.close()


@pytest.mark.parametrize("mutation", ["UNKNOWN", "PARSING_REJECTED", "missing_PARSED",
    "missing_slot", "lock_bytes", "anchor_bytes", "campaign_orphan", "unidentified_campaign"])
def test_actual_native_refusals_preserve_reservations_without_new_effect(tmp_path, monkeypatch, mutation):
    (root, target, saved, code, _, _, _, _, _, resolver, transport,
        witness, anchor, anchor_desc) = root_with_actual_lifecycle(tmp_path, monkeypatch)
    off = successor(tmp_path, root, root, target, saved, code, witness, anchor, anchor_desc, enabled=False, name="off")
    record = root.generation.ledger.slots()[0]
    receipt = P0NormalReceipt(root.root, record["namespace_sha256"])
    capture = receipt.read("DISPATCH")
    preserved_cost = record["reserved_usd"]
    try:
        if mutation in {"UNKNOWN", "PARSING_REJECTED"}:
            receipt.publish(mutation, receipt.event(mutation, record["grant"], capture["preflight"]))
        elif mutation == "missing_PARSED":
            # Deliberate tamper in this disposable synthetic fixture only.
            receipt._path("PARSED").unlink()
        elif mutation == "missing_slot":
            (root.root / (root.generation.ledger.prefix + record["preview_sha256"] + ".json")).unlink()
        elif mutation == "lock_bytes":
            (root.root / (root.generation.ledger.prefix + "LOCK")).write_bytes(canonical({"permission_sha256": "0" * 64}))
        elif mutation == "anchor_bytes":
            Path(anchor_desc["path"]).write_bytes(b'{"SYNTHETIC_TAMPER":true}')
        else:
            orphan_namespace = token_hex(32)
            orphan_grant = {**record["grant"], "namespace_sha256": orphan_namespace}
            if mutation == "unidentified_campaign":
                orphan_grant["owner_decision_sha256"] = "0" * 64
            orphan = P0NormalReceipt(root.root, orphan_namespace)
            orphan.reserve(grant=orphan_grant, dispatch=capture["dispatch"],
                body=capture["body"].encode(), preflight=capture["preflight"])
        diagnostic = "P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED" if mutation == "missing_PARSED" else None
        with pytest.raises((ValueError, OSError), match=diagnostic):
            off.generation.campaign_snapshot()
        assert resolver.calls == transport.calls == 1
        assert record["reserved_usd"] == preserved_cost
        assert receipt.exists("RESERVED")
    finally:
        off.close()
        root.close()


def test_indented_historical_witness_is_preserved_but_business_receipts_stay_canonical(tmp_path, monkeypatch):
    (root, target, saved, code, _, _, _, _, _, resolver, transport,
        witness, anchor, anchor_desc) = root_with_actual_lifecycle(tmp_path, monkeypatch, metadata_format="indented")
    witness_path = Path(witness["metadata_evidence"]["path"])
    witness_before = witness_path.read_bytes()
    assert witness_before != canonical(json.loads(witness_before))
    off = successor(tmp_path, root, root, target, saved, code, witness, anchor, anchor_desc, enabled=False, name="off")
    root_files = {path.name: path.read_bytes() for path in root.root.iterdir() if path.is_file()}
    try:
        snapshot = off.generation.campaign_snapshot()
        assert snapshot["slots_reserved"] == 1 and snapshot["live_enabled"] is False
        assert witness_path.read_bytes() == witness_before
        assert sha(witness_before) == witness["metadata_evidence"]["sha256"]
        assert {name: (root.root / name).read_bytes() for name in root_files} == root_files
        slot = root.generation.ledger.slots()[0]
        receipt = P0NormalReceipt(root.root, slot["namespace_sha256"])
        parsed = receipt.read("PARSED")
        # Only this disposable synthetic normal receipt is deliberately tampered.
        # External witness whitespace does not loosen the unchanged business decoder.
        parsed_indented = json.dumps(parsed, indent=2).encode()
        assert json.loads(parsed_indented) == parsed
        assert parsed_indented != canonical(parsed)
        receipt._path("PARSED").write_bytes(parsed_indented)
        with pytest.raises(ValueError, match="P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED"):
            off.generation.campaign_snapshot()
        assert witness_path.read_bytes() == witness_before
        assert receipt.exists("RESERVED")
        assert resolver.calls == transport.calls == 1
    finally:
        off.close()
        root.close()
