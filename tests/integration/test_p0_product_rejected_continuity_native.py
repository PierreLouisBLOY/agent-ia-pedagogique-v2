"""Actual Windows fixtures and Normal/P1 events; all authority/data synthetic."""

import copy
import json
import os
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

import pytest

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    COMMON_KEYS,
    LIMIT_KEYS,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    DISPOSITION,
)
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
)
from backend.infrastructure.composition.factories import p0_rejected_profile as F
from backend.infrastructure.composition.factories.p0_normal_profile import (
    P0NormalProductComposition,
)
from backend.infrastructure.filesystem import capture_secure_path
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from tests.integration.test_p0_creation_http import context
from tests.integration.test_p0_local_reference_context_composition import composed, prepare
from tests.integration.test_p0_product_continuity_native import install_doubles
from tests.unit.test_p0_normal_generation import SyntheticResolver, SyntheticTransport
from tests.unit.test_p0_normal_policy import fixture as financial_fixture
from tests.unit.test_p0_normal_profile import artifact, local_context_profile_fixture
from tests.unit.test_p0_rich_course_content import rich_content


@pytest.mark.skipif(os.name != "nt", reason="Real Windows handles/oplocks required")
def test_native_readset_pending_writer_rename_cancel_and_partial_cleanup(tmp_path):
    import ctypes

    from backend.infrastructure.composition.factories.p0_rejected_readset import (
        WindowsImmutableReadSet,
    )

    path = tmp_path / "SYNTHETIC_CODE.py"
    path.write_bytes(b"SYNTHETIC PUBLIC CODE\n")
    lease = WindowsImmutableReadSet({path: (tmp_path, sha(path.read_bytes()))})
    count = ctypes.WinDLL("kernel32", use_last_error=True).GetProcessHandleCount
    count.argtypes, count.restype = (ctypes.c_void_p, ctypes.c_void_p), ctypes.c_int
    current = ctypes.WinDLL("kernel32", use_last_error=True).GetCurrentProcess
    current.restype = ctypes.c_void_p

    def handles():
        n = ctypes.c_uint32()
        assert count(current(), ctypes.byref(n))
        return n.value

    before = handles()
    lease.acquire()
    assert lease.active and lease.members[0].pending
    assert lease.native.wait(lease.members[0].event, 0) == 258
    lease.require_intact()
    with pytest.raises(OSError):
        path.write_bytes(b"ANOTHER SAME SIZE CODE\n")
    with pytest.raises(OSError):
        path.rename(tmp_path / "SYNTHETIC_RENAMED.py")
    with pytest.raises(OSError):
        tmp_path.rename(tmp_path.with_name(tmp_path.name + "-renamed"))
    member = lease.members[0]
    assert lease.native.cancel(member.handle, ctypes.byref(member.overlapped))
    assert lease.native.wait(member.event, 5000) == 0
    with pytest.raises(ValueError, match="BROKEN"):
        lease.require_intact()
    lease.close()
    assert not lease.members and not lease.parents and not lease.cleanup_unconfirmed
    assert handles() == before
    # First member acquired, second pin wrong: every partial handle/IRP closes.
    other = tmp_path / "SYNTHETIC_OTHER.py"
    other.write_bytes(b"SYNTHETIC ONLY")
    partial = WindowsImmutableReadSet(
        {path: (tmp_path, sha(path.read_bytes())), other: (tmp_path, "0" * 64)}
    )
    before = handles()
    with pytest.raises(ValueError, match="PIN_CHANGED"):
        partial.acquire()
    assert not partial.members and not partial.parents and not partial.cleanup_unconfirmed
    assert handles() == before


@pytest.mark.skipif(os.name != "nt", reason="Real Windows writable section required")
def test_native_readset_hashes_retained_handle_with_separate_async_reads(tmp_path):
    import ctypes

    from backend.infrastructure.composition.factories.p0_rejected_readset import (
        WindowsImmutableReadSet,
    )

    raw = bytes(range(256)) * 9000
    path, empty = tmp_path / "SYNTHETIC_MULTIBLOCK.py", tmp_path / "SYNTHETIC_EMPTY.py"
    path.write_bytes(raw)
    empty.write_bytes(b"")
    lease = WindowsImmutableReadSet(
        {path: (tmp_path, sha(raw)), empty: (tmp_path, sha(b""))}
    )
    native_read = lease.native.read
    observed = []

    def retained_read(handle, buffer, count, transferred, overlapped):
        member = lease.members[-1]
        read_io = member.read_io
        assert handle == member.handle and read_io is not None
        assert read_io.event != member.event
        assert ctypes.addressof(read_io.overlapped) != ctypes.addressof(member.overlapped)
        assert transferred is None
        observed.append((read_io.overlapped.offset, count))
        return native_read(handle, buffer, count, transferred, overlapped)

    lease.native.read = retained_read
    try:
        lease.acquire()
        lease.require_intact()
        assert observed == [(0, 1048576), (1048576, 1048576), (2097152, 206848)]
        assert all(member.read_io is None for member in lease.members)
    finally:
        lease.close()
    assert not lease.members and not lease.parents and not lease.cleanup_unconfirmed


@pytest.mark.skipif(os.name != "nt", reason="Real Windows writable section required")
@pytest.mark.parametrize("operation", ["io", "read"])
def test_native_readset_interrupt_after_submission_retains_and_closes(tmp_path, operation):
    import ctypes

    from backend.infrastructure.composition.factories.p0_rejected_readset import (
        WindowsImmutableReadSet,
    )

    path = tmp_path / "SYNTHETIC_INTERRUPT.py"
    path.write_bytes(b"SYNTHETIC PUBLIC CODE")
    lease = WindowsImmutableReadSet({path: (tmp_path, sha(path.read_bytes()))})
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    count, current = kernel.GetProcessHandleCount, kernel.GetCurrentProcess
    count.argtypes, count.restype = (ctypes.c_void_p, ctypes.c_void_p), ctypes.c_int
    current.restype = ctypes.c_void_p
    def handles():
        value = ctypes.c_uint32()
        assert count(current(), ctypes.byref(value))
        return value.value
    original = getattr(lease.native, operation)
    def submitted(*args):
        member = lease.members[-1]
        assert member.pending
        if operation == "read":
            assert member.read_io is not None and member.read_io.pending
        original(*args)
        raise KeyboardInterrupt("SYNTHETIC_AFTER_NATIVE_SUBMISSION")
    setattr(lease.native, operation, submitted)
    before = handles()
    with pytest.raises(KeyboardInterrupt, match="SYNTHETIC_AFTER_NATIVE_SUBMISSION"):
        lease.acquire()
    assert not lease.cleanup_unconfirmed and not lease.active
    assert not lease.members and not lease.parents and handles() == before


@pytest.mark.skipif(os.name != "nt", reason="Real Windows writable section required")
def test_native_readset_refuses_writable_mapping_after_writer_handle_closed(tmp_path):
    import ctypes

    from backend.infrastructure.composition.factories.p0_rejected_readset import (
        WindowsImmutableReadSet,
        _Windows,
    )

    path = tmp_path / "SYNTHETIC_MAPPED.py"
    raw = b"SYNTHETIC ONLY"
    path.write_bytes(raw)
    windows = _Windows()
    writer = windows.create(str(path), 0xC0000000, 7, None, 3, 0x00200000, None)
    assert writer not in (None, ctypes.c_void_p(-1).value)
    create_map = windows.kernel.CreateFileMappingW
    create_map.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_wchar_p,
    )
    create_map.restype = ctypes.c_void_p
    map_view = windows.kernel.MapViewOfFile
    map_view.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_size_t,
    )
    map_view.restype = ctypes.c_void_p
    unmap = windows.kernel.UnmapViewOfFile
    unmap.argtypes, unmap.restype = (ctypes.c_void_p,), ctypes.c_int
    section = create_map(writer, None, 4, 0, 0, None)
    assert section
    view = map_view(section, 2, 0, 0, 0)
    assert view
    windows.close(writer)
    lease = WindowsImmutableReadSet({path: (tmp_path, sha(raw))})
    try:
        with pytest.raises(ValueError, match="OPEN_REFUSED|NOT_GRANTED"):
            lease.acquire()
        assert not lease.active and not lease.cleanup_unconfirmed
    finally:
        assert unmap(view)
        windows.close(section)
        lease.close()


def native(path):
    item = capture_secure_path(path, allowed_root=path)
    return {"path": str(path), "device": item.device, "inode": item.inode}


def send(
    composition,
    app,
    endpoint,
    selection,
    reference,
    *,
    rich=False,
    rejected=False,
    notion=False,
    timings=None,
    before_generate=None,
    expect_generate_refusal=False,
):
    if rich:
        ctx = context("FIRST_STMG", "COURSE", None)
        ctx.update(
            contract_id="P0-CONTEXT-COURSE-4.0" if notion else "P0-CONTEXT-COURSE-3.0",
            course_format="CHAPTER",
            discipline="Management",
            institutional=copy.deepcopy(selection),
            institutional_resolution=None,
            local_progression={"chapter": "1", "week": None, "sequence": None},
        )
        prepared = app.execute(
            "prepare",
            {
                "command_id": token_hex(16),
                "context": ctx,
                "reference": {
                    "notion_id": reference["notion_id"],
                    "passage_ref": reference["passage_ref"],
                },
            },
        )
    else:
        prepared = prepare(app, selection, reference, "FIRST_STMG")
    dispatch = as_plain(app.prepared[prepared["preparation_ref"]])
    if rich:
        template_context = copy.deepcopy(dispatch)
        template_context["context"]["institutional_resolution"]["question"] = {
            "official_label": "Synthetic local question"
        }
        content = rich_content(template_context)
        if notion:
            content["course_chapter"]["concepts"][0].pop("notion")
            content["course_chapter"]["concepts"][0]["notion_id"] = "N1"
        if rejected:
            content["course_chapter"]["concepts"][0]["notion"] = "Unknown synthetic notion"
        response = OpenAIResponsesResponse(
            OpenAIResponseStatus.COMPLETED,
            canonical(content).decode(),
            OpenAIResponseUsage(1000, 0, 100, 1100, reasoning_tokens=0),
            service_tier="default",
        )
        resolver, transport = SyntheticResolver(), SyntheticTransport(response)
        composition.generation.resolver, composition.generation.transport = resolver, transport
        tokenizer = financial_fixture()[5]
        composition.generation.tokenizer = lambda body: {
            **tokenizer,
            "request_sha256": sha(body),
            "manifest_sha256": composition.permission["tokenizer_manifest_sha256"],
        }
    else:
        resolver, transport = install_doubles(composition, dispatch)
    command = {
        "command_id": token_hex(16),
        "preparation_ref": prepared["preparation_ref"],
        "preparation_sha256": prepared["preparation_sha256"],
    }
    preview_started_utc = datetime.now(UTC)
    started = time.perf_counter()
    status, _, raw, _ = endpoint.respond(
        "POST", "/api/v2/p0/consent-preview", canonical(command), "SYNTHETIC"
    )
    if timings is not None:
        timings["preview"] = {
            "seconds": time.perf_counter() - started,
            "started_utc": preview_started_utc.isoformat(),
            "finished_utc": datetime.now(UTC).isoformat(),
        }
    if status != 200:
        # A fixture failure is diagnosed through the same Application service;
        # no HTTP exception suppression or production policy is changed.
        endpoint.consent_execute("consent_preview", command)
    assert status == 200, raw
    shown = json.loads(raw)["data"]
    consent = {
        **command,
        "preview_sha256": shown["preview_sha256"],
        "transfer_accepted": True,
        "cost_bound_accepted": True,
    }
    if before_generate is not None:
        before_generate(dispatch, composition)
    started = time.perf_counter()
    generate_started_utc = datetime.now(UTC)
    status, _, raw, _ = endpoint.respond(
        "POST", "/api/v2/p0/consent-generate", canonical(consent), "SYNTHETIC"
    )
    if timings is not None:
        timings["generate"] = {
            "seconds": time.perf_counter() - started,
            "started_utc": generate_started_utc.isoformat(),
            "finished_utc": datetime.now(UTC).isoformat(),
            "preview_age_seconds_at_generate": (
                generate_started_utc - datetime.fromisoformat(shown["preview"]["issued_at_utc"])
            ).total_seconds(),
            "preview_lifetime_seconds": (
                datetime.fromisoformat(shown["preview"]["expires_at_utc"])
                - datetime.fromisoformat(shown["preview"]["issued_at_utc"])
            ).total_seconds(),
        }
    if expect_generate_refusal:
        assert status != 200, raw
        assert resolver.calls == transport.calls == 0
        return dispatch, resolver, transport, shown
    if rejected:
        assert status != 200, raw
    else:
        assert status == 200 and json.loads(raw)["data"]["state"] == "CANDIDATE", raw
    assert resolver.calls == transport.calls == 1
    return dispatch, resolver, transport, shown


def create_successor(
    tmp_path,
    parent,
    root,
    saved,
    *,
    anchor,
    anchor_desc,
    witness,
    name,
    enabled,
    output_schema=None,
    disposition_desc=None,
    source_rebind=None,
):
    nodes = []
    if parent.profile["schema"] in {"P0-NORMAL-PROFILE-3.0", "P0-NORMAL-PROFILE-4.0"}:
        nodes = json.loads(Path(parent.profile["continuity_manifest"]["path"]).read_bytes())[
            "ancestors"
        ]
    nodes.append(
        {
            "permission_sha256": sha(canonical(parent.permission)),
            "parent_permission_sha256": None
            if parent is root
            else json.loads(Path(parent.profile["continuity_manifest"]["path"]).read_bytes())[
                "parent_permission_sha256"
            ],
            "permission": parent.envelope["permission"],
            "profile_envelope": {"path": str(parent.path), "sha256": sha(parent.path.read_bytes())},
            "owner_decision": parent.envelope["decision"],
        }
    )
    manifest = {
        "schema": "P0-PRODUCT-CONTINUITY-MANIFEST-1.0"
        if disposition_desc is None
        else "P0-PRODUCT-CONTINUITY-MANIFEST-2.0",
        "implementation_decision_sha256": anchor["implementation_decision"]["sha256"],
        "conditions_sha256": anchor["conditions"]["sha256"],
        "continuity_anchor": anchor_desc,
        "root_permission_sha256": sha(canonical(root.permission)),
        "root_lock_sha256": sha(canonical({"permission_sha256": sha(canonical(root.permission))})),
        "parent_permission_sha256": sha(canonical(parent.permission)),
        "campaign_namespace_sha256": root.permission["permission_namespace_sha256"],
        "campaign_window": {
            key: root.permission[key] for key in ("issued_at_utc", "expires_at_utc")
        },
        "campaign_limits": {key: root.permission[key] for key in LIMIT_KEYS},
        "common_identities": {
            key: sha(canonical(native(saved)))
            if key == "saved_root_native_sha256"
            else root.permission[key]
            for key in COMMON_KEYS
        },
        "ancestors": nodes,
        "historical_reservations": [witness],
    }
    if disposition_desc is not None:
        manifest["rejected_dispositions"] = [disposition_desc]
    manifest_desc = artifact(tmp_path, name + "_manifest.json", canonical(manifest))
    profile = copy.deepcopy(root.profile)
    profile.update(
        schema="P0-NORMAL-PROFILE-3.0" if disposition_desc is None else "P0-NORMAL-PROFILE-4.0",
        continuity_manifest=manifest_desc,
        continuity_anchor=anchor_desc,
        source_admission_owner_decision=root.envelope["decision"],
        continuity_enabled=enabled,
    )
    if disposition_desc is not None:
        profile["rejected_disposition"] = disposition_desc
    if source_rebind is not None:
        profile.update(source_rebind)
    permission = {
        **root.permission,
        "issued_at_utc": datetime.now(UTC).isoformat(),
        "profile_sha256": sha(canonical(profile)),
    }
    permission.update(
        baseline_commit=profile["baseline_commit"],
        source_tree_sha256=profile["source_manifest"]["sha256"],
        package_sha256=profile["package"]["sha256"],
    )
    if output_schema is not None:
        permission["output_schema_sha256"] = output_schema
    decision = {
        **root.decision,
        "schema": "P0-NORMAL-OWNER-DECISION-3.0"
        if disposition_desc is None
        else "P0-NORMAL-OWNER-DECISION-4.0",
        "profile_sha256": permission["profile_sha256"],
        "permission_policy_sha256": sha(
            canonical(
                {key: value for key, value in permission.items() if key != "owner_decision_sha256"}
            )
        ),
        "continuity_manifest_sha256": manifest_desc["sha256"],
        "continuity_anchor_sha256": anchor_desc["sha256"],
        "parent_permission_sha256": sha(canonical(parent.permission)),
        "source_admission_owner_decision_sha256": root.envelope["decision"]["sha256"],
    }
    if disposition_desc is not None:
        decision.update(
            continuity_version=2, rejected_disposition_sha256=disposition_desc["sha256"]
        )
    dec_desc = artifact(tmp_path, name + "_SYNTHETIC_NOT_OWNER.json", canonical(decision))
    permission["owner_decision_sha256"] = dec_desc["sha256"]
    envelope = {
        "schema": "P0-NORMAL-PROFILE-ENVELOPE-1.0",
        "profile": profile,
        "decision": dec_desc,
        "permission": artifact(tmp_path, name + "_SYNTHETIC_NOT_LIVE.json", canonical(permission)),
    }
    path = Path(artifact(tmp_path, name + "_envelope.json", canonical(envelope))["path"])
    return SimpleFixture(path, envelope, permission, decision, profile)


class SimpleFixture:
    def __init__(self, path, envelope, permission, decision, profile):
        self.path, self.envelope, self.permission, self.decision, self.profile = (
            path,
            envelope,
            permission,
            decision,
            profile,
        )


def adoption(tmp_path, components, *, operation, name, envelopes=None):
    book = {
        "schema": "P0-KNOWN-REJECTED-COMPONENT-BOOK-1.0",
        "operation": operation,
        "components": components,
    }
    book_desc = artifact(tmp_path, name + "_book.json", canonical(book))
    owner = {
        "schema": "LU-OWNER-KNOWN-REJECTED-EXACT-ADOPTION-1.0",
        "source": "DIRECT_HUMAN_ASYNC_QUESTION_REPLY",
        "question_call_id": "SYNTHETIC_REPLY_NOT_A_REAL_OWNER_VOTE",
        "proposal_sha256": book_desc["sha256"],
        "answer_exact": "ADOPTED_EXACT_COMPONENTS",
        "scope": operation,
        "human_cryptographic_signature_claimed": False,
    }
    owner_desc = artifact(tmp_path, name + "_SYNTHETIC_owner.json", canonical(owner))
    control = {
        "schema": "P0-KNOWN-REJECTED-EXTERNAL-ADOPTION-1.0",
        "operation": operation,
        "book": book_desc,
        "owner_evidence": owner_desc,
        "expected_owner_evidence_sha256": owner_desc["sha256"],
    }
    if envelopes is not None:
        control["profile_envelopes"] = envelopes
    return Path(artifact(tmp_path, name + "_external_control.json", canonical(control))["path"])


def fixture(tmp_path, monkeypatch, *, actual_source=False):
    native_subprocess_run = subprocess.run
    from tests.unit import test_p0_local_reference_context as local

    original_fixture = local.fixture

    def rich_local_fixture(*args, **kwargs):
        values = original_fixture("FIRST_STMG")
        manifest, sources, selection, reference, passages, resolution = values
        resolution.update(
            question={"official_label": "Synthetic local question"},
            capacities=[
                {
                    "capacity_ref": "capacity:synthetic",
                    "label": "Compare synthetic observations",
                    "locator": "unit:synthetic-capacity",
                }
            ],
        )
        manifest["bindings"][0]["canonical_resolution_sha256"] = sha(canonical(resolution))
        return manifest, sources, selection, reference, passages, resolution

    monkeypatch.setattr(local, "fixture", rich_local_fixture)
    from tests.integration import test_p0_local_reference_context_composition as local_composition

    monkeypatch.setattr(local_composition, "fixture", rich_local_fixture)
    path, target, saved, code, _, _ = local_context_profile_fixture(tmp_path, monkeypatch)
    root = P0NormalProductComposition(
        path=path, target=target, saved_root=saved, application_root=code
    )
    app, endpoint, _, selection, reference, *_ = composed(monkeypatch, "FIRST_STMG")
    app.generation = root.generation
    root.bind(app, endpoint)
    old_dispatch, old_resolver, old_transport, _ = send(root, app, endpoint, selection, reference)
    slot = root.generation.ledger.slots()[0]
    receipt = P0NormalReceipt(root.root, slot["namespace_sha256"])
    event_states = ("RESERVED", "PROVIDER_ATTEMPTED", "RESPONSE_CAPTURED", "PARSED", "CONSUMED")
    metadata = {
        "schema": "LU-P1-OWNER-EXACT-RECEIPT-METADATA-1.0",
        "source_commit": root.permission["baseline_commit"],
        "permission_sha256": sha(canonical(root.permission)),
        "campaign_namespace_sha256": root.permission["permission_namespace_sha256"],
        "slot_namespace_sha256": slot["namespace_sha256"],
        "request_sha256": slot["request_sha256"],
        "flags": {**dict.fromkeys(event_states, True), "UNKNOWN": False, "PARSING_REJECTED": False},
        "events": {
            state: {"receipt_sha256": sha(canonical(receipt.read(state)))} for state in event_states
        },
        "raw_output_text_disclosed": False,
    }
    witness = {
        key: slot[key]
        for key in ("permission_sha256", "namespace_sha256", "request_sha256", "reserved_usd")
    }
    witness["metadata_evidence"] = artifact(
        tmp_path,
        "SYNTHETIC-consumed-evidence.json",
        (json.dumps(metadata, indent=2) + "\n").encode(),
    )
    anchor = {
        "schema": "P0-PRODUCT-CONTINUITY-ANCHOR-1.0",
        "implementation_decision": artifact(
            tmp_path, "SYNTHETIC_conditions_adoption.json", canonical({"schema": "SYNTHETIC_ONLY"})
        ),
        "conditions": artifact(tmp_path, "SYNTHETIC_conditions.md", b"SYNTHETIC ONLY"),
        "root_permission_sha256": sha(canonical(root.permission)),
        "campaign_namespace_sha256": root.permission["permission_namespace_sha256"],
        "required_historical_reservations": [witness],
    }
    anchor_desc = artifact(tmp_path, "SYNTHETIC-anchor1.json", canonical(anchor))
    from backend.adapters.outbound.generation.openai.p0_course_content_schema import (
        rich_course_content_schema,
    )

    tip_data = create_successor(
        tmp_path,
        root,
        root,
        saved,
        anchor=anchor,
        anchor_desc=anchor_desc,
        witness=witness,
        name="tip3",
        enabled=True,
        output_schema=sha(canonical(rich_course_content_schema())),
    )
    tip = P0NormalProductComposition(
        path=tip_data.path, target=target, saved_root=saved, application_root=code
    )
    tip_app, tip_endpoint, _, selection, reference, *_ = composed(monkeypatch, "FIRST_STMG")
    tip_app.generation = tip.generation
    tip.bind(tip_app, tip_endpoint)
    rejected_dispatch, resolver, transport, shown = send(
        tip, tip_app, tip_endpoint, selection, reference, rich=True, rejected=True
    )
    paths = list(tip.root.glob(tip.generation.ledger.prefix + "*.json"))
    records = [json.loads(path.read_bytes()) for path in paths]
    rejected_slot = next(
        row for row in records if row["permission_sha256"] == sha(canonical(tip.permission))
    )
    rejected_receipt = P0NormalReceipt(tip.root, rejected_slot["namespace_sha256"])
    assert rejected_receipt.exists("PARSING_REJECTED") and not rejected_receipt.exists("UNKNOWN")
    assert not rejected_receipt.exists("PARSED") and not rejected_receipt.exists("CONSUMED")
    output_sha = sha(rejected_receipt.read("RESULT")["output_text"].encode())
    selected = {
        key: rejected_slot[key]
        for key in ("permission_sha256", "namespace_sha256", "request_sha256", "reserved_usd")
    }
    selected.update(
        request_bytes=rejected_slot["grant"]["request_bytes"], output_text_sha256=output_sha
    )
    proposal = artifact(
        tmp_path, "SYNTHETIC_prior_orientation.md", b"SYNTHETIC ONLY, NOT AN OWNER DECISION"
    )
    orientation = {
        "schema": "LU-OWNER-P1-FAILED-DISPOSITION-M02-EXTENSION-ADOPTIONS-1.0",
        "source": "DIRECT_HUMAN_ASYNC_QUESTION_REPLY",
        "question_call_id": "SYNTHETIC_NOT_A_REAL_OWNER_VOTE",
        "human_cryptographic_signature_claimed": False,
        "p1": {
            "proposal_sha256": proposal["sha256"],
            "answer_exact": "Adopter cette disposition bornée",
            "state": "ADOPTED_LIMITED",
            "failed_request_sha256": selected["request_sha256"],
            "retained_reserved_usd": selected["reserved_usd"],
            **dict.fromkeys(
                (
                    "real_ledger_mutation",
                    "activation",
                    "new_provider_call",
                    "grant_transfer",
                    "quota_reset",
                ),
                False,
            ),
        },
    }
    orientation_desc = artifact(tmp_path, "SYNTHETIC_orientation.json", canonical(orientation))
    diagnostic = {
        "schema": "LU-P1-OWNER-PURE-REJECTION-RULE-1.0",
        "request_sha256": selected["request_sha256"],
        "request_bytes": selected["request_bytes"],
        "permission_sha256": selected["permission_sha256"],
        "slot_namespace_sha256": selected["namespace_sha256"],
        "output_text_sha256": output_sha,
        "diagnosis": "PURE_LOCAL_REJECTION_REPRODUCED",
        "raw_output_text_disclosed": False,
        "stages": [
            {
                "stage": "BIND_AND_VALIDATE_COURSE",
                "status": "REJECTED",
                "code": "P0_RICH_COURSE_NOTION_UNKNOWN",
            }
        ],
    }
    diagnostic_desc = artifact(tmp_path, "SYNTHETIC_diagnostic.json", canonical(diagnostic))
    tip_manifest = json.loads(Path(tip.profile["continuity_manifest"]["path"]).read_bytes())
    nodes = [
        *tip_manifest["ancestors"],
        {
            "permission_sha256": sha(canonical(tip.permission)),
            "parent_permission_sha256": sha(canonical(root.permission)),
            "permission": tip.envelope["permission"],
            "profile_envelope": {"path": str(tip.path), "sha256": sha(tip.path.read_bytes())},
            "owner_decision": tip.envelope["decision"],
        },
    ]
    now = datetime.now(UTC)
    plan = {
        "schema": "P0-KNOWN-REJECTED-INSPECTION-PLAN-1.0",
        "operation": "INSPECT_KNOWN_REJECTION_AND_CAMPAIGN_READ_ONLY",
        "source_manifest": root.profile["source_manifest"],
        "package": root.profile["package"],
        "baseline_commit": root.permission["baseline_commit"],
        "source_tree": "2" * 40,
        "origin_tip_permission_sha256": sha(canonical(tip.permission)),
        "ancestors": nodes,
        "original_anchor": anchor_desc,
        "proposal": proposal,
        "owner_orientation_adoption": orientation_desc,
        "owner_diagnostic": diagnostic_desc,
        "expected_operator_delegation": root.profile["operator_delegation"],
        "saved_root_native_identity": native(saved),
        "receipt_root_native_identity": native(root.root),
        "target_runtime": root.profile["runtime"],
        "target_attempt": selected,
        "issued_at_utc": now.isoformat(),
        "expires_at_utc": root.permission["expires_at_utc"],
        "ledger_writes_allowed": False,
        "provider_calls_allowed": 0,
    }
    plan_desc = artifact(tmp_path, "SYNTHETIC_inspection_plan.json", canonical(plan))
    plan_control = adoption(
        tmp_path,
        {
            "inspection_plan_sha256": plan_desc["sha256"],
            "source_manifest_sha256": root.profile["source_manifest"]["sha256"],
            "package_sha256": root.profile["package"]["sha256"],
        },
        operation="INSPECTION_ONLY",
        name="plan",
    )
    inspection = F.P0RejectedInspectionComposition(
        plan_path=Path(plan_desc["path"]),
        adoption_path=plan_control,
        target=target,
        saved_root=saved,
        application_root=code,
    )
    observation = inspection._ledger().bootstrap()
    evidence = observation["observed_evidence"]
    evidence_desc = artifact(tmp_path, "SYNTHETIC_observed_evidence.json", canonical(evidence))
    disposition = {
        "schema": "P0-PRODUCT-KNOWN-REJECTED-DISPOSITION-1.0",
        "disposition": DISPOSITION,
        "target_attempt": selected,
        "observed_evidence": evidence_desc,
        "observed_evidence_sha256": evidence_desc["sha256"],
        "adoption_decision": orientation_desc,
        "owner_orientation_adoption": orientation_desc,
        "owner_diagnostic": diagnostic_desc,
        "source_origin_manifest_sha256": tip.profile["source_manifest"]["sha256"],
        "operation": "READ_ONLY_RECONCILIATION",
        "no_grant_reuse": True,
        "preserve_reservation": True,
        "no_runtime_mutation": True,
    }
    disp_desc = artifact(tmp_path, "SYNTHETIC_disposition.json", canonical(disposition))
    anchor2 = {
        **anchor,
        "schema": "P0-PRODUCT-CONTINUITY-ANCHOR-2.0",
        "original_anchor": anchor_desc,
        "required_rejected_dispositions": [disp_desc],
    }
    anchor2_desc = artifact(tmp_path, "SYNTHETIC_anchor2.json", canonical(anchor2))
    source_rebind = None
    current_code = code
    if actual_source:
        current_code = Path(F.__file__).resolve().parents[4]
        # Restore the engineering Git reader, disabled by the old extracted
        # one-file fixture; no Git mutation or private data is involved.
        monkeypatch.setattr(subprocess, "run", native_subprocess_run)
        if (current_code / ".git").exists():
            ids = subprocess.run(
                ["git", "rev-parse", "HEAD", "HEAD^{tree}"],
                cwd=current_code,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()
        else:
            distribution = json.loads(
                (current_code / "P0_NORMAL_SOURCE_MANIFEST.json").read_bytes()
            )
            ids = [distribution["source_commit"], distribution["source_tree"]]
        files = {
            path.relative_to(current_code).as_posix(): sha(path.read_bytes())
            for folder in ("backend", "frontend", "tools", "config")
            for path in (current_code / folder).rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".py", ".js", ".css", ".html", ".ps1", ".json"}
        }
        source = {
            "schema": "P0-NORMAL-SOURCE-MANIFEST-2.0",
            "source_commit": ids[0],
            "source_tree": ids[1],
            "files": files,
        }
        source_desc = artifact(tmp_path, "SYNTHETIC_current_public_source.json", canonical(source))
        archive_path = tmp_path / "SYNTHETIC_current_public_package.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            for name in files:
                archive.write(current_code / name, name)
            archive.writestr("P0_NORMAL_SOURCE_MANIFEST.json", canonical(source))
        source_rebind = {
            "baseline_commit": ids[0],
            "source_manifest": source_desc,
            "package": {"path": str(archive_path), "sha256": sha(archive_path.read_bytes())},
        }
    from backend.adapters.outbound.generation.openai.p0_course_content_schema import (
        rich_course_notion_content_schema,
    )

    off = create_successor(
        tmp_path,
        tip,
        root,
        saved,
        anchor=anchor2,
        anchor_desc=anchor2_desc,
        witness=witness,
        name="off4",
        enabled=False,
        output_schema=sha(canonical(rich_course_notion_content_schema())),
        disposition_desc=disp_desc,
        source_rebind=source_rebind,
    )
    on = create_successor(
        tmp_path,
        off,
        root,
        saved,
        anchor=anchor2,
        anchor_desc=anchor2_desc,
        witness=witness,
        name="on4",
        enabled=True,
        output_schema=sha(canonical(rich_course_notion_content_schema())),
        disposition_desc=disp_desc,
        source_rebind=source_rebind,
    )
    components = {
        "observed_evidence_sha256": evidence_desc["sha256"],
        "disposition_sha256": disp_desc["sha256"],
        "anchor2_sha256": anchor2_desc["sha256"],
        "manifest2_sha256": {
            "off": off.profile["continuity_manifest"]["sha256"],
            "on": on.profile["continuity_manifest"]["sha256"],
        },
        "profile4_OFF_sha256": off.permission["profile_sha256"],
        "profile4_ON_sha256": on.permission["profile_sha256"],
        "source_manifest_sha256": off.profile["source_manifest"]["sha256"],
        "package_sha256": off.profile["package"]["sha256"],
    }
    control = adoption(
        tmp_path,
        components,
        operation="OFF_ON_COMPONENT_REBIND",
        name="rebinding",
        envelopes={
            "off": {"path": str(off.path), "sha256": sha(off.path.read_bytes())},
            "on": {"path": str(on.path), "sha256": sha(on.path.read_bytes())},
        },
    )
    return locals()


def test_actual_windows_captured_rejected_bootstrap_off_and_shared_lock(tmp_path, monkeypatch):
    state = fixture(tmp_path, monkeypatch, actual_source=True)
    old_bytes = {
        path.name: path.read_bytes() for path in state["root"].root.iterdir() if path.is_file()
    }
    off = F.P0RejectedProductComposition(
        path=state["off"].path,
        adoption_path=state["control"],
        target=state["target"],
        saved_root=state["saved"],
        application_root=state["current_code"],
    )
    assert off.generation is None and off.resolver is None
    app, endpoint, *_ = composed(monkeypatch, "FIRST_STMG")
    off.bind(app, endpoint)
    status, _, raw, _ = endpoint.respond("GET", "/api/v2/p0", b"", "SYNTHETIC")
    assert status == 200, raw
    snapshot = json.loads(raw)["data"]["campaign_snapshot"]
    assert snapshot["known_rejected_count"] == snapshot["consumed_count"] == 1
    assert snapshot["slots_reserved"] == 2 and snapshot["live_enabled"] is False
    assert snapshot["financial_basis"] == "RESERVATIONS_NOT_BILLED_COST"
    assert app.generation is None and endpoint.consent_execute is None
    with state["root"].generation.ledger.locked():
        with pytest.raises(ValueError, match="CONCURRENT_DISPATCH"):
            off._ledger().snapshot()
    assert {name: (off.root / name).read_bytes() for name in old_bytes} == old_bytes
    assert state["resolver"].calls == state["transport"].calls == 1
    assert state["old_resolver"].calls == state["old_transport"].calls == 1
    state["inspection"].bind(app, endpoint)
    status, _, raw, _ = endpoint.respond("GET", "/api/v2/p0", b"", "SYNTHETIC")
    assert status == 200, raw
    observed = json.loads(raw)["data"]["campaign_snapshot"]
    assert observed["schema"] == "P1-CAMPAIGN-INSPECTION-OBSERVATION-1.0"
    assert observed["state"] == "OBSERVED_NOT_ADOPTED" and "remaining_calls" not in observed
    assert {name: (off.root / name).read_bytes() for name in old_bytes} == old_bytes
    child_code = """import ctypes,sys
k=ctypes.WinDLL('kernel32',use_last_error=True)
c=k.CreateFileW;c.argtypes=(ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p);c.restype=ctypes.c_void_p
h=c(sys.argv[1],0x80000000,0,None,3,0x00200000,None)
if h in (None,ctypes.c_void_p(-1).value):raise SystemExit(2)
try:
 print('SYNTHETIC_LOCK_HELD',flush=True);sys.stdin.readline()
finally:
 f=k.CloseHandle;f.argtypes=(ctypes.c_void_p,);f.restype=ctypes.c_int;f(h)
"""
    child = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            child_code,
            str(off.root / (state["root"].generation.ledger.prefix + "LOCK")),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            key: os.environ[key]
            for key in ("SystemRoot", "WINDIR", "TEMP", "TMP")
            if key in os.environ
        },
    )
    try:
        assert child.stdout.readline().strip() == "SYNTHETIC_LOCK_HELD"
        with pytest.raises(ValueError, match="CONCURRENT_DISPATCH"):
            off._ledger().snapshot()
    finally:
        child.stdin.write("CLOSE\n")
        child.stdin.flush()
        _, child_errors = child.communicate(timeout=15)
        assert child.returncode == 0 and not child_errors
    assert {name: (off.root / name).read_bytes() for name in old_bytes} == old_bytes
    # Same real CLI and profile4 factory; only the server loop is a harness.
    from types import SimpleNamespace

    from backend.adapters.inbound.cli import local_browser

    cli_calls = []

    def build_cli(*args, **kwargs):
        assert kwargs["p0_generation"] is None
        kwargs["p0_product_binder"](app, endpoint)
        assert endpoint.campaign_snapshot()["slots_reserved"] == 2
        cli_calls.append("factory-bound")
        return SimpleNamespace(
            url="http://127.0.0.1:9123/",
            serve_forever=lambda: None,
            close=lambda: cli_calls.append("server-closed"),
        )

    monkeypatch.setattr(local_browser, "build_local_read15", build_cli)
    cli_args = [
        "--port",
        "9123",
        "--runtime",
        str(state["target"].runtime_path),
        "--data-root",
        str(state["target"].data_root),
        "--runtime-sha256",
        state["target"].expected_sha256,
        "--saved-root",
        str(state["saved"]),
        "--word-profile",
        "product-v7",
        "--p0-rejected-profile",
        str(state["off"].path),
        "--p0-rejected-adoption",
        str(state["control"]),
    ]
    assert local_browser.main(cli_args) == 0
    assert cli_calls == ["factory-bound", "server-closed"]
    # A new profile4 permission is required; toggling the adopted OFF fails.
    with pytest.raises(ValueError, match="ADOPTED_MODE_MISMATCH"):
        F.P0RejectedProductComposition(
            path=state["off"].path,
            adoption_path=state["control"],
            target=state["target"],
            saved_root=state["saved"],
            mode="on",
            application_root=state["current_code"],
        )
    from backend.infrastructure.composition.factories import p0_normal_profile

    monkeypatch.setattr(F, "LocalTokenizerHelper", p0_normal_profile.LocalTokenizerHelper)
    on = F.P0RejectedProductComposition(
        path=state["on"].path,
        adoption_path=state["control"],
        target=state["target"],
        saved_root=state["saved"],
        mode="on",
        application_root=state["current_code"],
    )
    new_app, new_endpoint, _, selection, reference, *_ = composed(monkeypatch, "FIRST_STMG")
    new_app.generation = on.generation
    on.bind(new_app, new_endpoint)
    before = on._ledger().snapshot()
    assert before["slots_reserved"] == 2 and before["live_enabled"] is True
    with pytest.raises(ValueError, match="OLD_GRANT_CURRENT_RECOVERY_REFUSED"):
        on.generation.recover_confirmed(request=state["rejected_dispatch"])
    new_dispatch, new_resolver, new_transport, _ = send(
        on, new_app, new_endpoint, selection, reference, rich=True, notion=True
    )
    assert new_dispatch["context"]["contract_id"] == "P0-CONTEXT-COURSE-4.0"
    after = on._ledger().snapshot()
    assert (
        after["slots_reserved"] == 3
        and after["known_rejected_count"] == 1
        and after["consumed_count"] == 2
    )
    assert new_resolver.calls == new_transport.calls == 1
    assert {name: (off.root / name).read_bytes() for name in old_bytes} == old_bytes
    # Closed failure matrix on disposable synthetic receipts only. No rejected
    # or missing receipt can return an available current budget.
    selected_slot = state["rejected_slot"]
    selected_receipt = state["rejected_receipt"]
    for mutation in (
        "UNKNOWN",
        "PARSED",
        "CONSUMED",
        "missing_RESULT",
        "changed_capture",
        "bool_attempt",
        "usage",
        "missing_slot",
        "lock",
    ):
        changed_path = None
        before_bytes = None
        if mutation in {"UNKNOWN", "PARSED", "CONSUMED"}:
            changed_path = selected_receipt._path(mutation)
            capture = selected_receipt.read("DISPATCH")
            selected_receipt.publish(
                mutation,
                selected_receipt.event(mutation, selected_slot["grant"], capture["preflight"]),
            )
        else:
            state_name = {
                "missing_RESULT": "RESULT",
                "changed_capture": "DISPATCH",
                "bool_attempt": "PROVIDER_ATTEMPTED",
                "usage": "RESULT",
            }.get(mutation)
            changed_path = (
                selected_receipt._path(state_name)
                if state_name is not None
                else off.root
                / (
                    state["root"].generation.ledger.prefix
                    + (
                        selected_slot["preview_sha256"] + ".json"
                        if mutation == "missing_slot"
                        else "LOCK"
                    )
                )
            )
            before_bytes = changed_path.read_bytes()
            if mutation in {"missing_RESULT", "missing_slot"}:
                changed_path.unlink()
            elif mutation == "lock":
                changed_path.write_bytes(canonical({"permission_sha256": "0" * 64}))
            else:
                changed = json.loads(before_bytes)
                if mutation == "changed_capture":
                    changed["body"] += " "
                elif mutation == "bool_attempt":
                    changed["provider_attempts"] = True
                else:
                    changed["usage"]["total_tokens"] += 1
                changed_path.write_bytes(canonical(changed))
        try:
            with pytest.raises(ValueError):
                on._ledger().snapshot()
        finally:
            if before_bytes is None:
                changed_path.unlink()
            else:
                changed_path.write_bytes(before_bytes)
        assert (
            selected_receipt.exists("RESERVED")
            and selected_slot["reserved_usd"] == state["selected"]["reserved_usd"]
        )
    assert {name: (off.root / name).read_bytes() for name in old_bytes} == old_bytes
    assert new_resolver.calls == new_transport.calls == 1
    on.close()
    for owner in (state["root"], state["tip"], state["inspection"], off):
        owner.close()


def timed_native(timings, timing_path, name, operation):
    started, started_utc = time.perf_counter(), datetime.now(UTC).isoformat()
    try:
        return operation()
    finally:
        timings[name] = {
            "seconds": time.perf_counter() - started,
            "started_utc": started_utc,
            "finished_utc": datetime.now(UTC).isoformat(),
        }
        timing_path.write_bytes(canonical(timings))


@pytest.mark.skipif(
    not os.environ.get("PROJET_V2_QA_SHORT_SOURCE_ROOT"),
    reason="Dedicated exact short public distribution required for the deadline qualification",
)
def test_short_distribution_deadlines_fresh_reads_and_pre_effect_mutations(tmp_path, monkeypatch):
    """R7 targeted operations, not a repeat of the historical R6 matrix."""
    code = Path(F.__file__).resolve().parents[4]
    assert code == Path(os.environ["PROJET_V2_QA_SHORT_SOURCE_ROOT"])
    assert not (code / ".git").exists()
    manifest = json.loads((code / "P0_NORMAL_SOURCE_MANIFEST.json").read_bytes())
    import backend.adapters.outbound.generation.openai.p0_product_rejected as broker_module
    import backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection as dto_module

    provenance = {}
    for module in (F, broker_module, dto_module):
        module_path = Path(module.__file__).resolve()
        name = module_path.relative_to(code).as_posix()
        assert sha(module_path.read_bytes()) == manifest["files"][name]
        provenance[name] = {"path": str(module_path), "sha256": manifest["files"][name]}
    timings, timing_path = {}, tmp_path / "OPERATION_TIMINGS_PROGRESS.json"
    state = timed_native(
        timings, timing_path, "fixture", lambda: fixture(tmp_path, monkeypatch, actual_source=True)
    )
    old_bytes = {
        path.name: path.read_bytes() for path in state["root"].root.iterdir() if path.is_file()
    }
    off = F.P0RejectedProductComposition(
        path=state["off"].path,
        adoption_path=state["control"],
        target=state["target"],
        saved_root=state["saved"],
        application_root=code,
    )
    assert off._ledger() is off._ledger()
    app, endpoint, *_ = composed(monkeypatch, "FIRST_STMG")
    off.bind(app, endpoint)
    calls = []
    loader = off._ledger().chain_loader

    def fresh_chain():
        calls.append(datetime.now(UTC).isoformat())
        return loader()

    off._ledger().chain_loader = fresh_chain

    def timed_get(name):
        started = time.perf_counter()
        started_utc = datetime.now(UTC).isoformat()
        status, _, raw, _ = endpoint.respond("GET", "/api/v2/p0", b"", "SYNTHETIC")
        timings[name] = {
            "seconds": time.perf_counter() - started,
            "started_utc": started_utc,
            "finished_utc": datetime.now(UTC).isoformat(),
        }
        timing_path.write_bytes(canonical(timings))
        assert status == 200, raw
        return json.loads(raw)["data"]["campaign_snapshot"]

    assert timed_get("get_off")["slots_reserved"] == 2
    assert len(calls) == 1
    assert timed_get("get_off_fresh")["slots_reserved"] == 2
    assert len(calls) == 2
    # Each mutation happens between operations; no previous source validation
    # can make a current budget available. Disposable synthetic descriptors
    # are restored, while the distribution code mutation is byte-restored.
    paths = (
        Path(state["control"]),
        Path(state["off"].path),
        Path(off.profile["source_manifest"]["path"]),
        Path(off.profile["package"]["path"]),
        code / "backend" / "__init__.py",
    )
    refusals = []
    for path in paths:
        previous = path.read_bytes()
        try:
            path.write_bytes(previous + b" ")
            status, _, raw, _ = endpoint.respond("GET", "/api/v2/p0", b"", "SYNTHETIC")
            assert status != 200, raw
            assert "CURRENT_RESERVATIONS_RECONCILED" not in raw.decode()
            refusals.append(path.name)
        finally:
            path.write_bytes(previous)
    assert off._ledger() is off._ledger()
    assert {name: (off.root / name).read_bytes() for name in old_bytes} == old_bytes
    # A newly bound inspection plan may observe the same historical attempt
    # with the exact current public source, without conferring effect rights.
    plan = copy.deepcopy(state["plan"])
    plan.update(
        source_manifest=off.profile["source_manifest"],
        package=off.profile["package"],
        baseline_commit=off.permission["baseline_commit"],
        source_tree=manifest["source_tree"],
    )
    plan_desc = artifact(tmp_path, "SYNTHETIC_R7_plan.json", canonical(plan))
    control = adoption(
        tmp_path,
        {
            "inspection_plan_sha256": plan_desc["sha256"],
            "source_manifest_sha256": off.profile["source_manifest"]["sha256"],
            "package_sha256": off.profile["package"]["sha256"],
        },
        operation="INSPECTION_ONLY",
        name="R7_inspection",
    )
    inspection = F.P0RejectedInspectionComposition(
        plan_path=Path(plan_desc["path"]),
        adoption_path=control,
        target=state["target"],
        saved_root=state["saved"],
        application_root=code,
    )
    assert inspection._ledger() is inspection._ledger()
    inspection.bind(app, endpoint)
    assert timed_get("get_inspect_only")["state"] == "OBSERVED_NOT_ADOPTED"
    from backend.infrastructure.composition.factories import p0_normal_profile

    monkeypatch.setattr(F, "LocalTokenizerHelper", p0_normal_profile.LocalTokenizerHelper)
    on = timed_native(
        timings,
        timing_path,
        "on_construction",
        lambda: F.P0RejectedProductComposition(
            path=state["on"].path,
            adoption_path=state["control"],
            target=state["target"],
            saved_root=state["saved"],
            mode="on",
            application_root=code,
        ),
    )
    app.generation = on.generation
    timed_native(timings, timing_path, "on_bind", lambda: on.bind(app, endpoint))
    assert timed_get("get_on")["slots_reserved"] == 2
    source_path = code / "backend" / "__init__.py"
    source_bytes = source_path.read_bytes()
    try:
        send(
            on,
            app,
            endpoint,
            state["selection"],
            state["reference"],
            rich=True,
            notion=True,
            before_generate=lambda *_: source_path.write_bytes(source_bytes + b" "),
            expect_generate_refusal=True,
        )
    finally:
        source_path.write_bytes(source_bytes)
    assert on._ledger().snapshot()["slots_reserved"] == 2
    timed_native(
        timings,
        timing_path,
        "positive_round_trip",
        lambda: send(
            on,
            app,
            endpoint,
            state["selection"],
            state["reference"],
            rich=True,
            notion=True,
            timings=timings,
        ),
    )
    after = on._ledger().snapshot()
    assert after["slots_reserved"] == 3 and after["known_rejected_count"] == 1
    assert after["consumed_count"] == 2
    assert {name: (off.root / name).read_bytes() for name in old_bytes} == old_bytes
    (tmp_path / "R7_OPERATION_TIMINGS.json").write_bytes(
        canonical(
            {
                "schema": "SYNTHETIC_P1_V2_NORMAL_OPERATION_TIMINGS_1.0",
                "timings": timings,
                "loaded_public_modules": provenance,
                "fresh_off_get_chain_calls": len(calls),
                "between_operation_refusals": refusals,
                "provider_sla_proved": False,
                "provider_timeout_seconds_unchanged": 120,
                "business_originals_read": False,
            }
        )
    )
    assert all(row["seconds"] < 60 for key, row in timings.items() if key.startswith("get_"))
    assert timings["preview"]["seconds"] < 150 and timings["generate"]["seconds"] < 150
    assert timings["generate"]["preview_lifetime_seconds"] == 900
    assert 0 <= timings["generate"]["preview_age_seconds_at_generate"] < 900
    for owner in (on, inspection, off, state["inspection"], state["tip"], state["root"]):
        owner.close()


@pytest.mark.skipif(
    not os.environ.get("PROJET_V2_QA_SHORT_SOURCE_ROOT"),
    reason="Dedicated exact short public distribution required for the deadline qualification",
)
def test_short_distribution_changed_source_after_accept_keeps_reserved_and_refuses_effect(
    tmp_path, monkeypatch
):
    """A source change at the accept→authorize boundary cannot use a cache."""
    code = Path(F.__file__).resolve().parents[4]
    assert code == Path(os.environ["PROJET_V2_QA_SHORT_SOURCE_ROOT"])
    timings, timing_path = {}, tmp_path / "PRE_EFFECT_TIMINGS_PROGRESS.json"
    state = timed_native(
        timings, timing_path, "fixture", lambda: fixture(tmp_path, monkeypatch, actual_source=True)
    )
    old_bytes = {
        path.name: path.read_bytes() for path in state["root"].root.iterdir() if path.is_file()
    }
    from backend.infrastructure.composition.factories import p0_normal_profile

    monkeypatch.setattr(F, "LocalTokenizerHelper", p0_normal_profile.LocalTokenizerHelper)
    on = timed_native(
        timings,
        timing_path,
        "on_construction",
        lambda: F.P0RejectedProductComposition(
            path=state["on"].path,
            adoption_path=state["control"],
            target=state["target"],
            saved_root=state["saved"],
            mode="on",
            application_root=code,
        ),
    )
    app, endpoint, *_ = composed(monkeypatch, "FIRST_STMG")
    app.generation = on.generation
    timed_native(timings, timing_path, "on_bind", lambda: on.bind(app, endpoint))
    source_path, before = (
        code / "backend" / "__init__.py",
        (code / "backend" / "__init__.py").read_bytes(),
    )
    original_authorize = on.generation.authorize
    boundary = []

    def mutate_after_accept(*, request):
        boundary.append("ACCEPT_RETURNED_BEFORE_AUTHORIZE")
        source_path.write_bytes(before + b" ")
        return original_authorize(request=request)

    def install_mutation(*_):
        monkeypatch.setattr(on.generation, "authorize", mutate_after_accept)

    try:
        _, resolver, transport, shown = timed_native(
            timings,
            timing_path,
            "pre_effect_refusal",
            lambda: send(
                on,
                app,
                endpoint,
                state["selection"],
                state["reference"],
                rich=True,
                notion=True,
                before_generate=install_mutation,
                expect_generate_refusal=True,
                timings=timings,
            ),
        )
    finally:
        source_path.write_bytes(before)
    assert boundary == ["ACCEPT_RETURNED_BEFORE_AUTHORIZE"]
    assert resolver.calls == transport.calls == 0
    new_slots = [
        json.loads(path.read_bytes())
        for path in on.root.glob(on.generation.ledger.prefix + "*.json")
        if path.name not in old_bytes
    ]
    assert len(new_slots) == 1
    new_slot = new_slots[0]
    assert new_slot["preview_sha256"] == shown["preview_sha256"]
    assert new_slot["reserved_usd"] == shown["preview"]["cost_bound_usd"]
    receipt = P0NormalReceipt(on.root, new_slot["namespace_sha256"])
    assert not receipt.exists("PROVIDER_ATTEMPTED") and not receipt.exists("CONSUMED")
    with pytest.raises(ValueError, match="OUTCOME_RECONCILIATION_REQUIRED"):
        on._ledger().snapshot()
    assert {name: (on.root / name).read_bytes() for name in old_bytes} == old_bytes
    for owner in (on, state["inspection"], state["tip"], state["root"]):
        owner.close()
