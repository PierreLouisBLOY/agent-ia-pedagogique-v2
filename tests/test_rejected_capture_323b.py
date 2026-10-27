"""Native readonly inspection, canonical identifiers and no external effects."""

from __future__ import annotations

import copy
import re
import socket
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.adapters.inbound.application.rejected_capture import RejectedCaptureInbound
from backend.adapters.outbound.generation.openai.p0_content import INSTRUCTIONS, content_schema
from backend.adapters.outbound.generation.openai.p0_normal_policy import HASH_FIELDS, canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.adapters.outbound.persistence.rejected_capture import NormalRejectedCaptureReader
from backend.modules.pedagogical_design.contracts.dto.p0_production import _validated_sections
from backend.modules.pedagogical_design.contracts.dto.section_identity import SECTION_ID_PATTERN
from backend.modules.work_orchestration.application.queries.read_rejected_capture import (
    ReadRejectedCapture,
)
from backend.modules.work_orchestration.contracts.dto.rejected_capture import RejectedCaptureRequest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("323B_ZERO_NETWORK")

    monkeypatch.setattr(socket.socket, "connect", denied)


def fixture(root: Path, *, dispatched=None, body_bytes=None, output=None, rejected=True):
    root.mkdir()
    common = {key: "a" * 64 for key in HASH_FIELDS}
    permission = {
        **common,
        "permission_namespace_sha256": "b" * 64,
        "baseline_commit": "a" * 40,
        "max_calls": 1,
        "per_call_ceiling_usd": "0.080942",
        "cumulative_ceiling_usd": "0.080942",
    }
    pin = P0NormalReceipt(root, "b" * 64)
    permission["receipt_root_sha256"] = pin.root_sha256
    body = body_bytes or canonical({"model": "gpt-5.6-terra", "SYNTHETIC": True})
    if body_bytes is not None:
        import json

        permission["output_schema_sha256"] = sha(
            canonical(json.loads(body_bytes)["text"]["format"]["schema"])
        )
        common["output_schema_sha256"] = permission["output_schema_sha256"]
    now = datetime.now(UTC)
    grant = {
        **common,
        "receipt_root_sha256": pin.root_sha256,
        "schema": "P0-NORMAL-CREATE-GRANT-1.0",
        "operation": "CREATE",
        "provider": "OPENAI",
        "model": "gpt-5.6-terra",
        "endpoint": "https://api.openai.com/v1/responses",
        "reasoning": "low",
        "tier": "default",
        "fallback": "NONE",
        "live_authorized": True,
        "transfer_authorized": True,
        "max_output_tokens": 4096,
        "max_calls": 1,
        "count_calls": 0,
        "review_calls": 0,
        "modify_calls": 0,
        "retry": 0,
        "parallelism": 1,
        "baseline_commit": "a" * 40,
        "request_sha256": sha(body),
        "request_bytes": len(body),
        "namespace_sha256": "c" * 64,
        "issued_at_utc": now.isoformat(),
        "expires_at_utc": (now + timedelta(minutes=60)).isoformat(),
        "ceiling_usd": "0.080942",
    }
    # Permission identities are common, while each grant owns its operation namespace/body.
    permission.pop("namespace_sha256")
    permission.pop("request_sha256")
    proof = {"cost_bound_usd": "0.080942", "synthetic": True}
    dispatch = dispatched or {"SYNTHETIC_DISPATCH": True}
    ledger = P0ProductLedger(root=root, permission=permission)
    command = "d" * 32
    with ledger.locked():
        ledger.reserve(grant=grant, preview_sha256="e" * 64, command_id=command, preflight=proof)
        receipt = P0NormalReceipt(root, "c" * 64)
        receipt.reserve(grant=grant, dispatch=dispatch, body=body, preflight=proof)
        receipt.publish("PROVIDER_ATTEMPTED", receipt.event("PROVIDER_ATTEMPTED", grant, proof))
        usage = {
            "input_tokens": 100,
            "cached_input_tokens": 0,
            "output_tokens": 20,
            "total_tokens": 120,
            "reasoning_tokens": 0,
            "cache_write_input_tokens": None,
        }
        artifact = {
            "schema": "P0-NORMAL-CONFIRMED-RESULT-1.0",
            "grant_sha256": sha(canonical(grant)),
            "request_sha256": sha(body),
            "dispatch_sha256": sha(canonical(dispatch)),
            "response_status": "completed",
            "output_text": output or '{"SYNTHETIC_CAPTURE":true}',
            "usage": usage,
        }
        result_sha = receipt.publish("RESULT", artifact)
        receipt.publish(
            "RESPONSE_CAPTURED",
            receipt.event(
                "RESPONSE_CAPTURED",
                grant,
                proof,
                artifact=result_sha,
                status="completed",
                usage=usage,
            ),
        )
        if rejected:
            receipt.publish("PARSING_REJECTED", receipt.event("PARSING_REJECTED", grant, proof))
    binding = RejectedCaptureRequest(
        command,
        sha(canonical(permission)),
        sha(body),
        len(body),
        result_sha,
        sha(canonical(grant)),
        sha(canonical(proof)),
    )
    reader = NormalRejectedCaptureReader(
        root=root, permission_loader=lambda: permission, binding=binding
    )
    inbound = RejectedCaptureInbound(ReadRejectedCapture(reader, binding))
    return inbound, binding, ledger, receipt, artifact


def hashes(root):
    return {p.name: sha(p.read_bytes()) for p in root.iterdir() if p.is_file()}


def test_read_completed_rejected_twice_without_mutation(tmp_path):
    root = tmp_path / "SYNTHETIC"
    inbound, binding, ledger, receipt, _ = fixture(root)
    before = hashes(root)
    first, second = inbound.read(binding), inbound.read(binding)
    assert first.output_text == second.output_text == '{"SYNTHETIC_CAPTURE":true}'
    assert first.metadata["receipt_hashes_before"] == first.metadata["receipt_hashes_after"]
    assert hashes(root) == before
    with pytest.raises(ValueError, match="P0_RECOVERY_OUTCOME_UNKNOWN"):
        receipt.confirmed(ledger.slots()[0]["grant"])


@pytest.mark.parametrize(
    "key,value",
    [
        ("command_id", "f" * 32),
        ("result_sha256", "f" * 64),
        ("request_sha256", "f" * 64),
        ("grant_sha256", "f" * 64),
        ("preflight_sha256", "f" * 64),
    ],
)
def test_foreign_request_refused_before_reader(tmp_path, key, value):
    inbound, binding, _, _, _ = fixture(tmp_path / "SYNTHETIC")
    with pytest.raises(ValueError, match="APPLICATION_SCOPE"):
        inbound.read(replace(binding, **{key: value}))


def test_existing_lock_required_no_creation(tmp_path):
    root = tmp_path / "SYNTHETIC"
    inbound, binding, ledger, _, _ = fixture(root)
    # Synthetic fixture only: simulate an absent LOCK after setup.
    (root / (ledger.prefix + "LOCK")).unlink()
    before = hashes(root)
    with pytest.raises(ValueError, match="EXISTING_LOCK_REQUIRED"):
        inbound.read(binding)
    assert hashes(root) == before


def test_native_lock_concurrency_refuses_without_effect(tmp_path):
    root = tmp_path / "SYNTHETIC"
    inbound, binding, ledger, _, _ = fixture(root)
    before = hashes(root)
    with ledger.locked(create=False):
        with pytest.raises(ValueError, match="CONCURRENT_DISPATCH"):
            inbound.read(binding)
    assert hashes(root) == before


@pytest.mark.parametrize("change", ["incomplete", "usage", "result", "parsed", "unknown"])
def test_altered_or_wrong_state_refused(tmp_path, change):
    root = tmp_path / "SYNTHETIC"
    inbound, binding, ledger, receipt, artifact = fixture(root)
    if change in {"incomplete", "result"}:
        value = copy.deepcopy(artifact)
        value["response_status" if change == "incomplete" else "output_text"] = (
            "incomplete" if change == "incomplete" else "changed"
        )
        receipt._path("RESULT").write_bytes(canonical(value))
    elif change == "usage":
        value = receipt.read("RESPONSE_CAPTURED")
        value["usage"]["output_tokens"] += 1
        receipt._path("RESPONSE_CAPTURED").write_bytes(canonical(value))
    else:
        slot = ledger.slots()[0]
        receipt.publish(
            change.upper(),
            receipt.event(change.upper(), slot["grant"], {"cost_bound_usd": "0.080942"}),
        )
    before = hashes(root)
    with pytest.raises(ValueError):
        inbound.read(binding)
    assert hashes(root) == before


@pytest.mark.parametrize(
    "identity,valid",
    [
        ("S1", True),
        ("S_DOC1", True),
        ("S" + "A" * 63, True),
        ("S" + "A" * 64, False),
        ("section_1", False),
        ("s1", False),
        ("S", False),
        ("S1\n", False),
        ("SÉ", False),
    ],
)
def test_schema_instructions_and_actual_validator_agree(identity, valid):
    pattern = content_schema()["properties"]["sections"]["items"]["properties"]["section_id"][
        "pattern"
    ]
    assert pattern == SECTION_ID_PATTERN and pattern in INSTRUCTIONS
    assert bool(re.search(pattern, identity)) is valid
    data = [{"section_id": identity, "heading": "Titre factice", "text": "Contenu synthétique."}]
    if valid:
        _validated_sections(data)
    else:
        with pytest.raises(ValueError, match="P0_SECTION_ID"):
            _validated_sections(data)


def test_duplicate_id_rejected():
    row = {"section_id": "S1", "heading": "Factice", "text": "Contenu synthétique."}
    with pytest.raises(ValueError, match="P0_SECTIONS"):
        _validated_sections([row, row])


def test_historical_schema_is_explicitly_pinned_for_readonly_recovery():
    assert (
        sha(canonical(content_schema(legacy_section_ids=True)))
        == "2a3ff169e426cbced8e23e1383df914b40b8f0261eb83241dfd661cf703f495a"
    )
    assert (
        "pattern"
        not in content_schema(legacy_section_ids=True)["properties"]["sections"]["items"][
            "properties"
        ]["section_id"]
    )


@pytest.mark.parametrize("fault", ["incomplete", "usage"])
def test_coherent_hash_does_not_admit_invalid_status_or_usage(tmp_path, fault):
    root = tmp_path / "SYNTHETIC"
    _, binding, ledger, receipt, artifact = fixture(root)
    if fault == "incomplete":
        artifact["response_status"] = "incomplete"
    else:
        artifact["usage"]["total_tokens"] = 999
    receipt._path("RESULT").write_bytes(canonical(artifact))
    changed = replace(binding, result_sha256=sha(canonical(artifact)))
    slot = ledger.slots()[0]
    witness = receipt.event(
        "RESPONSE_CAPTURED",
        slot["grant"],
        {"cost_bound_usd": "0.080942"},
        artifact=changed.result_sha256,
        status=artifact["response_status"],
        usage=artifact["usage"],
    )
    receipt._path("RESPONSE_CAPTURED").write_bytes(canonical(witness))
    reader = NormalRejectedCaptureReader(
        root=root, permission_loader=lambda: ledger.permission, binding=changed
    )
    before = hashes(root)
    with pytest.raises(
        ValueError,
        match="RECOVERY_BINDING" if fault == "incomplete" else "RECOVERY_USAGE_INCOHERENT",
    ):
        RejectedCaptureInbound(ReadRejectedCapture(reader, changed)).read(changed)
    assert hashes(root) == before


def test_boolean_provider_attempts_is_not_integer_one(tmp_path):
    root = tmp_path / "SYNTHETIC"
    inbound, binding, _, receipt, _ = fixture(root)
    value = receipt.read("PROVIDER_ATTEMPTED")
    value["provider_attempts"] = True
    receipt._path("PROVIDER_ATTEMPTED").write_bytes(canonical(value))
    with pytest.raises(ValueError, match="RECEIPT_CHAIN"):
        inbound.read(binding)


def test_same_bytes_file_substitution_refused(tmp_path, monkeypatch):
    root = tmp_path / "SYNTHETIC"
    inbound, binding, _, receipt, _ = fixture(root)
    original = P0NormalReceipt.read
    changed = False

    def replaced(self, name):
        nonlocal changed
        value = original(self, name)
        if name == "RESULT" and not changed:
            changed = True
            path = receipt._path("RESULT")
            temporary = root / "SYNTHETIC-replacement.tmp"
            temporary.write_bytes(path.read_bytes())
            temporary.replace(path)
        return value

    monkeypatch.setattr(P0NormalReceipt, "read", replaced)
    with pytest.raises(ValueError, match="CHANGED_DURING_READ"):
        inbound.read(binding)


@pytest.mark.parametrize("state", ["confirmed", "tampered_body", "rejected"])
def test_actual_legacy_recovery_method_keeps_body_and_rejection_guards(tmp_path, state):
    from test_recovered_derivative_323b import capture, content

    from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
    from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
    from backend.infrastructure.config.secrets.provider import ProviderCredentialRef
    from backend.modules.pedagogical_design.application.commands.repair_captured_sections import (
        RepairCapturedSectionIds,
    )

    dispatch = capture().dispatch
    wire = build_p0_content_request(dispatch, legacy_section_ids=True)
    body = NormalP0GenerationAdapter.body(wire)
    if state == "tampered_body":
        body += b" "
    valid = RepairCapturedSectionIds().execute(content()).content
    _, _, ledger, _, _ = fixture(
        tmp_path / "SYNTHETIC",
        dispatched=dispatch,
        body_bytes=body,
        output=canonical(valid).decode(),
        rejected=state == "rejected",
    )

    class Never:
        def resolve(self, *args, **kwargs):
            raise AssertionError("NO_CREDENTIAL")

        def build(self, *args, **kwargs):
            raise AssertionError("NO_TRANSPORT")

    def forbidden(*args, **kwargs):
        raise AssertionError("NO_PREFLIGHT_OR_TOKENIZER")

    adapter = NormalP0GenerationAdapter(
        grant=ledger.slots()[0]["grant"],
        identity_source=forbidden,
        tariff={},
        tokenizer=forbidden,
        receipt_root=ledger.root,
        resolver=Never(),
        credential_ref=ProviderCredentialRef("openai.p0.normal"),
        transport=Never(),
    )
    if state == "confirmed":
        output = adapter.recover_confirmed(request=dispatch)
        assert output["production_ref"] == dispatch["production_ref"]
    else:
        with pytest.raises(
            ValueError,
            match="P0_NORMAL_RECOVERY_BODY"
            if state == "tampered_body"
            else "P0_RECOVERY_OUTCOME_UNKNOWN",
        ):
            adapter.recover_confirmed(request=dispatch)
