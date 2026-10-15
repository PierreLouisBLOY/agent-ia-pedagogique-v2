"""Windows native OFF qualification with declared synthetic campaign and doubles."""
import copy
import json
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.adapters.outbound.generation.openai.p0_product_policy import P1_HASHES
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_contract import (
    UNKNOWN_FILES,
)
from backend.core_contracts.outcome import ApplicationFailureKind
from backend.infrastructure.composition.factories import p0_normal_profile
from backend.infrastructure.composition.factories import p0_rejected_profile as historical
from backend.infrastructure.composition.factories import p0_unknown_off as F
from backend.infrastructure.composition.factories.p0_normal_profile import (
    P0NormalProductComposition,
)
from backend.infrastructure.filesystem import capture_secure_path
from backend.shared_kernel.correlation import CorrelationId
from tests.integration.test_p0_product_rejected_continuity_native import (
    artifact,
    composed,
    fixture,
    native,
    send,
)

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Native Windows original LOCK required")


def build(tmp_path, monkeypatch, *, actual_source=False, mutate_manifest=None, mutate_plan=None):
    native_run = subprocess.run
    # Declared historical-generation identity double only. The OFF composition
    # below performs its complete native/source/ancestor/adoption checks, after
    # this double is restored. No OFF validator or reader is substituted.
    with monkeypatch.context() as legacy_setup:
        legacy_setup.setattr(P0NormalProductComposition, "identities",
            lambda self: {k: self.permission[k] for k in P1_HASHES | {"baseline_commit"}})
        f = fixture(tmp_path, monkeypatch, actual_source=False)
    # Same declared tokenizer double as the inherited native V2 fixture. The
    # OFF reader never invokes a tokenizer; this is history construction only.
    monkeypatch.setattr(historical, "LocalTokenizerHelper", p0_normal_profile.LocalTokenizerHelper)
    current = historical.P0RejectedProductComposition(path=f["on"].path, adoption_path=f["control"],
        target=f["target"], saved_root=f["saved"], mode="on", application_root=f["current_code"])
    app, endpoint, _, selection, reference, *_ = composed(monkeypatch, "FIRST_STMG")
    app.generation = current.generation
    current.bind(app, endpoint)
    def fail_transport(dispatch, composition):
        composition.generation.transport.failure = RuntimeError("SYNTHETIC_PRIVATE_FAILURE_SENTINEL")
    _, resolver, transport, _ = send(current, app, endpoint, selection, reference,
        rich=True, notion=True, rejected=True, before_generate=fail_transport)
    assert resolver.calls == transport.calls == 1
    root = current.root
    records = [json.loads(p.read_bytes()) for p in root.glob(current._ledger().prefix + "*.json")]
    selected = next(r for r in records if r["permission_sha256"] == sha(canonical(current.permission)))
    receipt = P0NormalReceipt(root, selected["namespace_sha256"])
    assert receipt.exists("UNKNOWN") and not receipt.exists("RESULT")
    files = {s: receipt.read(s) for s in UNKNOWN_FILES}
    pins = {s: sha((root / (selected["namespace_sha256"] + "." + s + ".json")).read_bytes()) for s in UNKNOWN_FILES}
    owner = {"schema": "LU-P1-OWNER-EXACT-C4-ATTEMPT-METADATA-1.0",
        "source_commit": current.permission["baseline_commit"],
        "campaign_namespace_sha256": current.permission["permission_namespace_sha256"],
        "original_lock_sha256": current.chain.manifest["root_lock_sha256"],
        **{k: selected[k] for k in ("permission_sha256", "request_sha256", "grant_sha256", "preview_sha256", "command_id")},
        "slot_namespace_sha256": selected["namespace_sha256"], "request_bytes": selected["grant"]["request_bytes"],
        "flags": {**dict.fromkeys(("RESERVED", "PROVIDER_ATTEMPTED", "UNKNOWN", "DISPATCH"), True),
            **dict.fromkeys(("RESPONSE_CAPTURED", "PARSED", "CONSUMED", "PARSING_REJECTED", "RESULT"), False)},
        "events": {s: {"receipt_sha256": pins[s]} for s in ("RESERVED", "PROVIDER_ATTEMPTED", "UNKNOWN")},
        "raw_output_text_disclosed": False, "actual_billed_cost_status": "NOT_ESTABLISHED"}
    diagnostic = artifact(tmp_path, "SYNTHETIC-unknown-owner-metadata.json", canonical(owner))
    disposition = {"schema": "P0-UNKNOWN-OFF-DISPOSITION-1.0", "disposition": "UNKNOWN_PRESERVE_COUNT_NO_EFFECT",
        "target_attempt": {**{k: selected[k] for k in ("permission_sha256", "namespace_sha256", "request_sha256",
            "reserved_usd", "grant_sha256", "preview_sha256", "command_id", "preflight_sha256")},
            "request_bytes": selected["grant"]["request_bytes"]},
        "slot_sha256": sha(canonical(selected)), "file_sha256s": pins, "owner_diagnostic": diagnostic,
        "preserve_reservation": True, "no_grant_reuse": True, "no_runtime_mutation": True}
    disp_desc = artifact(tmp_path, "SYNTHETIC-unknown-disposition.json", canonical(disposition))
    old_anchor = current.chain.anchor
    anchor = {"schema": "P0-UNKNOWN-OFF-ANCHOR-1.0",
        **{k: current.chain.manifest[k] for k in ("root_permission_sha256", "campaign_namespace_sha256", "root_lock_sha256")},
        "original_anchor": old_anchor["original_anchor"], "prior_anchor": current.profile["continuity_anchor"],
        "orientation_adoption": artifact(tmp_path, "SYNTHETIC-off-orientation.txt", b"SYNTHETIC ONLY"),
        "prior_design_review": artifact(tmp_path, "SYNTHETIC-off-review.txt", b"SYNTHETIC ONLY"),
        "owner_diagnostic": diagnostic}
    anchor_desc = artifact(tmp_path, "SYNTHETIC-off-anchor.json", canonical(anchor))
    rejected_ns = current.chain.evidence["namespace_sha256"]
    total = sum((Decimal(r["reserved_usd"]) for r in records), Decimal(0))
    manifest = {"schema": "P0-UNKNOWN-OFF-MANIFEST-1.0", "anchor": anchor_desc,
        "historical_manifest": current.profile["continuity_manifest"], "unknown_disposition": disp_desc,
        "expected_slots": [{"namespace_sha256": r["namespace_sha256"], "slot_sha256": sha(canonical(r)),
            "classification": "UNKNOWN" if r is selected else "KNOWN_REJECTED" if r["namespace_sha256"] == rejected_ns else "CONSUMED"}
            for r in records], "expected_reserved_budget_usd": str(total)}
    if mutate_manifest:
        mutate_manifest(manifest)
    manifest_desc = artifact(tmp_path, "SYNTHETIC-off-manifest.json", canonical(manifest))
    source = json.loads(Path(current.profile["source_manifest"]["path"]).read_bytes())
    off_code = f["current_code"]
    source_desc, package_desc = current.profile["source_manifest"], current.profile["package"]
    if actual_source:
        # The new OFF code/package is separate from the preserved old origin.
        # Never activate/rebind a historical ON profile to current source.
        monkeypatch.setattr(subprocess, "run", native_run)
        off_code = Path(F.__file__).resolve().parents[4]
        if (off_code / ".git").exists():
            ids = native_run(["git", "rev-parse", "HEAD", "HEAD^{tree}"], cwd=off_code,
                capture_output=True, text=True, check=True).stdout.splitlines()
        else:
            distributed = json.loads((off_code / "P0_NORMAL_SOURCE_MANIFEST.json").read_bytes())
            ids = [distributed["source_commit"], distributed["source_tree"]]
        source_files = {p.relative_to(off_code).as_posix(): sha(p.read_bytes())
            for folder in ("backend", "frontend", "tools", "config") for p in (off_code / folder).rglob("*")
            if p.is_file() and p.suffix.lower() in {".py", ".js", ".css", ".html", ".ps1", ".json"}}
        source = {"schema": "P0-NORMAL-SOURCE-MANIFEST-2.0", "source_commit": ids[0],
            "source_tree": ids[1], "files": source_files}
        source_desc = artifact(tmp_path, "SYNTHETIC-new-OFF-source.json", canonical(source))
        archive_path = tmp_path / "SYNTHETIC-new-OFF-public-code.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            for name in source_files:
                archive.write(off_code / name, name)
            archive.writestr("P0_NORMAL_SOURCE_MANIFEST.json", canonical(source))
        package_desc = {"path": str(archive_path), "sha256": sha(archive_path.read_bytes())}
    plan = {"schema": "P0-UNKNOWN-OFF-PLAN-1.0", "operation": "INSPECT_UNKNOWN_LOCAL_OFF",
        "baseline_commit": source["source_commit"], "source_tree": source["source_tree"],
        "source_manifest": source_desc, "package": package_desc,
        "historical_profile_envelope": {"path": str(current.path), "sha256": sha(current.path.read_bytes())},
        "historical_adoption_control": {"path": str(f["control"]), "sha256": sha(f["control"].read_bytes())},
        "origin_tip_permission_sha256": sha(canonical(current.permission)), "anchor": anchor_desc,
        "manifest": manifest_desc, "operator_delegation": current.profile["operator_delegation"],
        "target_runtime": current.profile["runtime"], "saved_root_native_identity": native(f["saved"]),
        "receipt_root_native_identity": native(root), "issued_at_utc": datetime.now(UTC).isoformat(),
        "expires_at_utc": current.chain.root.permission["expires_at_utc"],
        "continuity_enabled": False, "ledger_writes_allowed": False, "provider_calls_allowed": 0}
    if mutate_plan:
        mutate_plan(plan)
    plan_desc = artifact(tmp_path, "SYNTHETIC-off-plan.json", canonical(plan))
    components = {"plan_sha256": plan_desc["sha256"], "anchor_sha256": anchor_desc["sha256"],
        "manifest_sha256": manifest_desc["sha256"], "disposition_sha256": disp_desc["sha256"],
        "source_manifest_sha256": plan["source_manifest"]["sha256"], "package_sha256": plan["package"]["sha256"]}
    book = {"schema": "P0-UNKNOWN-OFF-BOOK-1.0", "operation": "LOCAL_OFF_ONLY", "components": components}
    book_desc = artifact(tmp_path, "SYNTHETIC-off-book.json", canonical(book))
    adoption = {"schema": "P0-UNKNOWN-OFF-OWNER-ADOPTION-1.0", "operation": "LOCAL_OFF_ONLY",
        "book_sha256": book_desc["sha256"], "components": copy.deepcopy(components)}
    adoption_desc = artifact(tmp_path, "SYNTHETIC-off-owner.json", canonical(adoption))
    control = {"schema": "P0-UNKNOWN-OFF-ADOPTION-1.0", "book": book_desc, "owner_evidence": adoption_desc}
    control_desc = artifact(tmp_path, "SYNTHETIC-off-control.json", canonical(control))
    args = dict(plan_path=Path(plan_desc["path"]), adoption_path=Path(control_desc["path"]),
        expected_owner_sha256=adoption_desc["sha256"], target=f["target"], saved_root=f["saved"],
        application_root=off_code)
    return locals()


def facts(root):
    result = {}
    for p in root.iterdir():
        if p.is_file():
            identity = capture_secure_path(p, allowed_root=root)
            result[p.name] = (sha(p.read_bytes()), identity.device, identity.inode)
    return result


@pytest.fixture(scope="module")
def shared_synthetic_campaign(tmp_path_factory):
    """Build history once; each inspection still validates all fresh inputs."""
    patch = pytest.MonkeyPatch()
    data = build(tmp_path_factory.mktemp("SYNTHETIC-off-history"), patch)
    yield data
    data["current"].close()
    patch.undo()


@pytest.fixture
def campaign(shared_synthetic_campaign, tmp_path):
    """Restore declared fixture bytes between faults, never a real P1 ledger."""
    data = shared_synthetic_campaign
    base = data["tmp_path"]
    before = {p: p.read_bytes() for p in base.rglob("*") if p.is_file()}
    yield data
    archive = tmp_path / "SYNTHETIC_FAULT_ARTIFACTS"
    archive.mkdir()
    for path in base.rglob("*"):
        if path.is_file() and path not in before:
            path.rename(archive / sha(str(path.relative_to(base)).encode()))
    for path, raw in before.items():
        if not path.exists() or path.read_bytes() != raw:
            path.write_bytes(raw)


def rebind(base, tmp_path, *, mutate_manifest=None, mutate_plan=None):
    """Synthetic exact adoption of a test mutation; no production authority."""
    manifest, plan = copy.deepcopy(base["manifest"]), copy.deepcopy(base["plan"])
    if mutate_manifest:
        mutate_manifest(manifest)
    manifest_desc = artifact(tmp_path, "SYNTHETIC-case-manifest.json", canonical(manifest))
    plan["manifest"] = manifest_desc
    if mutate_plan:
        mutate_plan(plan)
    plan_desc = artifact(tmp_path, "SYNTHETIC-case-plan.json", canonical(plan))
    components = {"plan_sha256": plan_desc["sha256"], "anchor_sha256": plan["anchor"]["sha256"],
        "manifest_sha256": manifest_desc["sha256"], "disposition_sha256": manifest["unknown_disposition"]["sha256"],
        "source_manifest_sha256": plan["source_manifest"]["sha256"], "package_sha256": plan["package"]["sha256"]}
    book = {"schema": "P0-UNKNOWN-OFF-BOOK-1.0", "operation": "LOCAL_OFF_ONLY", "components": components}
    book_desc = artifact(tmp_path, "SYNTHETIC-case-book.json", canonical(book))
    owner = {"schema": "P0-UNKNOWN-OFF-OWNER-ADOPTION-1.0", "operation": "LOCAL_OFF_ONLY",
        "book_sha256": book_desc["sha256"], "components": components}
    owner_desc = artifact(tmp_path, "SYNTHETIC-case-owner.json", canonical(owner))
    control_desc = artifact(tmp_path, "SYNTHETIC-case-control.json", canonical({
        "schema": "P0-UNKNOWN-OFF-ADOPTION-1.0", "book": book_desc, "owner_evidence": owner_desc}))
    return {**base["args"], "plan_path": Path(plan_desc["path"]),
        "adoption_path": Path(control_desc["path"]), "expected_owner_sha256": owner_desc["sha256"]}


def inspect(composition):
    return composition.inbound.inspect(request=composition.request,
        correlation_id=CorrelationId("SYNTHETIC_UNKNOWN_OFF"))


def deny_effects(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("SYNTHETIC_OFF_EFFECT_FORBIDDEN")
    for cls, names in ((P0ProductLedger, ("reserve", "_publish", "locked")),
        (P0NormalReceipt, ("reserve", "event", "publish", "_publish_document")),
        (historical.MaskedLocalSecretResolver, ("resolve",))):
        for name in names:
            monkeypatch.setattr(cls, name, refuse)


def test_native_actual_source_application_off_preserves_all_bytes_slots_lock_and_no_effect(tmp_path, monkeypatch):
    b = build(tmp_path, monkeypatch, actual_source=True)
    before = facts(b["root"])
    attempts = b["transport"].calls
    deny_effects(monkeypatch)
    off = F.P0UnknownOffComposition(**b["args"])
    off.bind(b["app"], b["endpoint"])
    outcome = inspect(off)
    assert outcome.success and outcome.side_effects == ()
    data = outcome.data.as_dict()
    assert data["slots_reserved"] == 3 and data["unknown_count"] == data["consumed_count"] == data["known_rejected_count"] == 1
    assert Decimal(data["reserved_budget_usd"]) == b["total"]
    assert not data["live_enabled"] and not data["effect_permitted"]
    assert b["app"].generation is None and b["endpoint"].consent_execute is None
    assert not any(hasattr(off.reader, name) for name in ("reserve", "generate", "recover", "activate", "grant", "resolver"))
    encoded = canonical(data).decode()
    assert all(s not in encoded for s in ("SYNTHETIC_PRIVATE_FAILURE_SENTINEL", str(b["root"]), "body", "Bearer", "output_text"))
    assert facts(b["root"]) == before and b["transport"].calls == attempts == 1
    assert b["receipt"].exists("UNKNOWN") and not b["receipt"].exists("CONSUMED")
    with pytest.raises(ValueError, match="UNKNOWN"):
        b["receipt"].confirmed(b["selected"]["grant"])


@pytest.mark.parametrize("mutation", ["omit", "duplicate", "classification", "lower_total"])
def test_exact_adopted_manifest_cannot_drop_or_release_unknown(campaign, tmp_path, mutation):
    def change(value):
        if mutation == "omit":
            value["expected_slots"].pop()
        elif mutation == "duplicate":
            value["expected_slots"][0] = copy.deepcopy(value["expected_slots"][1])
        elif mutation == "classification":
            for row in value["expected_slots"]:
                if row["classification"] == "UNKNOWN":
                    row["classification"] = "CONSUMED"
        else:
            value["expected_reserved_budget_usd"] = "0.00001"
    b = campaign
    before = facts(b["root"])
    off = F.P0UnknownOffComposition(**rebind(b, tmp_path, mutate_manifest=change))
    outcome = inspect(off)
    assert not outcome.success and outcome.application_failure.kind is ApplicationFailureKind.AF_MAPPING_CORRUPTION
    assert facts(b["root"]) == before and b["transport"].calls == 1


@pytest.mark.parametrize("mutation", ["on", "writes", "calls", "expiry", "tip", "store", "runtime", "operator"])
def test_closed_plan_refuses_effect_window_and_context_divergence(campaign, tmp_path, mutation):
    def change(value):
        if mutation == "on":
            value["continuity_enabled"] = True
        elif mutation == "writes":
            value["ledger_writes_allowed"] = True
        elif mutation == "calls":
            value["provider_calls_allowed"] = 1
        elif mutation == "expiry":
            value["expires_at_utc"] = value["issued_at_utc"]
        elif mutation == "tip":
            value["origin_tip_permission_sha256"] = "f" * 64
        elif mutation == "store":
            value["receipt_root_native_identity"]["inode"] += 1
        elif mutation == "runtime":
            value["target_runtime"] = {**value["target_runtime"], "sha256": "f" * 64}
        else:
            value["operator_delegation"] = {**value["operator_delegation"], "sha256": "f" * 64}
    b = campaign
    before = facts(b["root"])
    with pytest.raises(ValueError):
        F.P0UnknownOffComposition(**rebind(b, tmp_path, mutate_plan=change))
    assert facts(b["root"]) == before


@pytest.mark.parametrize("mutation", ["missing_event", "result", "changed_event", "fourth_slot", "orphan", "lock", "missing_lock", "source", "package", "adoption", "ancestor"])
def test_fresh_reads_refuse_changed_history_and_identities_without_new_send(campaign, mutation):
    b = campaign
    off = F.P0UnknownOffComposition(**b["args"])
    root, selected = b["root"], b["selected"]
    if mutation == "missing_event":
        # Move synthetic fixture file only; no historical production receipt.
        p = root / (selected["namespace_sha256"] + ".UNKNOWN.json")
        p.rename(p.with_suffix(".SYNTHETIC_HELD"))
    elif mutation == "result":
        (root / (selected["namespace_sha256"] + ".RESULT.json")).write_bytes(canonical({"schema": "SYNTHETIC_EXTRA"}))
    elif mutation == "changed_event":
        p = root / (selected["namespace_sha256"] + ".UNKNOWN.json")
        data = json.loads(p.read_bytes())
        data["provider_attempts"] = 0
        p.write_bytes(canonical(data))
    elif mutation == "fourth_slot":
        (root / (b["current"]._ledger().prefix + "f" * 64 + ".json")).write_bytes(canonical(selected))
    elif mutation == "orphan":
        (root / ("f" * 64 + ".UNKNOWN.json")).write_bytes(canonical(b["files"]["UNKNOWN"]))
    elif mutation == "lock":
        (root / (b["current"]._ledger().prefix + "LOCK")).write_bytes(b"SYNTHETIC_CHANGED_LOCK")
    elif mutation == "missing_lock":
        p = root / (b["current"]._ledger().prefix + "LOCK")
        p.rename(p.with_name("SYNTHETIC_HELD_LOCK"))
    elif mutation in {"source", "package"}:
        p = Path(b["plan"]["source_manifest" if mutation == "source" else "package"]["path"])
        p.write_bytes(p.read_bytes() + b"SYNTHETIC_CHANGED")
    elif mutation == "adoption":
        b["args"]["adoption_path"].write_bytes(canonical({"schema": "SYNTHETIC_CHANGED"}))
    else:
        Path(b["f"]["root"].envelope["decision"]["path"]).write_bytes(canonical({"schema": "SYNTHETIC_CHANGED"}))
    before = facts(root)
    outcome = inspect(off)
    assert not outcome.success and outcome.side_effects == ()
    assert facts(root) == before and b["transport"].calls == 1


def test_native_concurrent_original_lock_refuses_and_releases_without_rewrite(campaign):
    b = campaign
    off = F.P0UnknownOffComposition(**b["args"])
    context = off._validate()
    from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
        P0ContinuityProductLedger,
    )
    held = P0ContinuityProductLedger(root=b["root"], permission=context.chain.current.permission,
        chain_loader=lambda: context.chain, broker_identity=object(), clock=lambda: datetime.now(UTC))
    before = facts(b["root"])
    with held.locked():
        outcome = inspect(off)
        assert not outcome.success and outcome.application_failure.kind is ApplicationFailureKind.AF_CONCURRENCY
    assert facts(b["root"]) == before and inspect(off).success


def test_reader_failure_and_concurrent_change_return_closed_failure_no_private_data(campaign, monkeypatch):
    b = campaign
    off = F.P0UnknownOffComposition(**b["args"])
    def fail():
        raise OSError("SYNTHETIC_PRIVATE_FAILURE_SENTINEL")
    monkeypatch.setattr(off.reader, "_loader", fail)
    before = facts(b["root"])
    result = inspect(off)
    assert not result.success and result.application_failure.kind is ApplicationFailureKind.AF_PORT_UNAVAILABLE
    assert "SYNTHETIC_PRIVATE_FAILURE_SENTINEL" not in str(result)
    assert facts(b["root"]) == before and b["transport"].calls == 1


@pytest.mark.parametrize("change", ["bytes", "native_identity"])
def test_mutation_during_inspection_refuses_even_same_bytes_replacement(campaign, monkeypatch, change):
    b = campaign
    off = F.P0UnknownOffComposition(**b["args"])
    loader, calls = off.reader._loader, []
    target = b["root"] / (b["selected"]["namespace_sha256"] + ".UNKNOWN.json")
    before = facts(b["root"])
    def changed():
        value = loader()
        calls.append(True)
        if len(calls) == 3:
            raw = target.read_bytes()
            if change == "bytes":
                target.write_bytes(raw + b" ")
            else:
                target.rename(target.with_name("SYNTHETIC_HELD_ORIGINAL"))
                target.write_bytes(raw)
        return value
    monkeypatch.setattr(off.reader, "_loader", changed)
    result = inspect(off)
    assert len(calls) == 3 and not result.success
    assert result.application_failure.kind is ApplicationFailureKind.AF_MAPPING_CORRUPTION
    after = facts(b["root"])
    if change == "native_identity":
        assert before[target.name][0] == after[target.name][0]
        assert before[target.name][1:] != after[target.name][1:]
    assert b["transport"].calls == 1 and not b["receipt"].exists("CONSUMED")
