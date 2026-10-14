"""Real Windows handles/DACL/publications, exclusively on fresh synthetic fixtures."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from backend.adapters.outbound.resource_library.local_contribution_store import (
    LocalContributionFileStore,
    LocalContributionTarget,
    _owner_only,
    directory_lease,
    native_operator,
)
from backend.core_contracts.outcome import OutcomeStatus
from backend.infrastructure.composition.factories.local_contribution import (
    build_local_contribution_application,
)
from backend.modules.resource_library.contracts.dto.local_contribution import (
    LocalContributionRequest,
)
from backend.modules.resource_library.ports.outbound.local_contribution_store import (
    LocalContributionPersistenceError,
)
from tests.unit.test_local_contribution import fixture, fixture_v2, read_request

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Native Windows overlay contract")


def native_fixture(tmp_path, *, provenance_v2=False):
    target = LocalContributionTarget.prepare(tmp_path / "new-overlay")
    make = fixture_v2 if provenance_v2 else fixture
    args, request, calls = make(target_sha=target.sha256, profile_sha=target.operator_profile_sha256)
    store = LocalContributionFileStore(target, binding_sha256=args["authority"].sha256)
    args["store"] = store
    return args, request, calls, target, store


def files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_real_append_close_reopen_exact_dacl_and_retained_stage_aliases(tmp_path):
    args, request, _, target, store = native_fixture(tmp_path)
    app = build_local_contribution_application(**args, enabled=True)
    result = app.register(request, correlation="synthetic-native")
    assert result.success, result
    read = {"contract_id": "LOCAL-CONTRIBUTION-READ-1.0", **{k: result.data["record"][k] for k in ("object_ref", "version_ref", "passage_ref")},
        "record_sha256": result.data["record_sha256"]}
    before = files(target.root)
    assert len(before) == 9  # marker, lock, three finals, four retained stages
    sid = native_operator()["windows_sid"]
    for path in (target.root, *target.root.rglob("*")):
        _owner_only(path, sid)
    stages = tuple((target.root / "staging").iterdir())
    finals = [target.root / "OVERLAY", *tuple((target.root / "intents").iterdir()),
        *tuple((target.root / "versions").iterdir()), *tuple((target.root / "commits").iterdir())]
    assert len(stages) == len(finals) == 4
    assert all(sum(os.path.samefile(stage, final) for stage in stages) == 1 for final in finals)
    # Retained aliases designate the same native file, not independent backups.
    reopened = LocalContributionFileStore(LocalContributionTarget.prepare(target.root), binding_sha256=args["authority"].sha256)
    args["store"] = reopened
    new_app = build_local_contribution_application(**args, enabled=True)
    projection = new_app.read(read)["source_snapshot"]
    assert projection["excerpt"] == request["text"] and len(projection["excerpt"]) > 320
    assert files(target.root) == before
    duplicate = new_app.register(request, correlation="synthetic-native")
    assert duplicate.success and duplicate.data["record_sha256"] == result.data["record_sha256"]
    assert duplicate.side_effects[0]["new_effect"] is False
    assert files(target.root) == before
    with store.session():
        assert store.inspect_operation(LocalContributionRequest(request).sha256, args["authority"].sha256)["state"] == "COMMITTED"


def test_second_command_refuses_without_new_files_or_allocation(tmp_path, monkeypatch):
    args, request, _, target, _ = native_fixture(tmp_path)
    app = build_local_contribution_application(**args, enabled=True)
    assert app.register(request, correlation="synthetic").success
    before = files(target.root)
    changed = dict(request, command_key="f" * 64)
    def forbidden():
        raise AssertionError("NO_SECOND_ALLOCATION")
    monkeypatch.setattr("backend.modules.resource_library.application.commands.register_local_contribution.uuid4", forbidden)
    result = app.register(changed, correlation="synthetic")
    assert result.success is False and result.outcome_status == OutcomeStatus.INDETERMINATE
    assert result.side_effects[0]["reconciliation_required"] is True
    assert files(target.root) == before


def test_off_does_not_create_root_or_query_reference(tmp_path):
    args, request, calls, target, _ = native_fixture(tmp_path)
    app = build_local_contribution_application(**args)
    with pytest.raises(ValueError, match="DISABLED"):
        app.register(request, correlation="synthetic")
    assert not target.root.exists() and calls == []


def test_another_binding_is_rejected_before_root_creation(tmp_path):
    args, request, calls, target, _ = native_fixture(tmp_path)
    args["store"] = LocalContributionFileStore(target, binding_sha256="f" * 64)
    with pytest.raises(ValueError, match="TARGET_CHANGED"):
        build_local_contribution_application(**args, enabled=True).register(request, correlation="synthetic")
    assert not target.root.exists() and calls == []


def test_unmarked_existing_root_is_never_hardened_or_populated(tmp_path):
    args, request, _, target, _ = native_fixture(tmp_path)
    target.root.mkdir()
    sentinel = target.root / "unrelated.txt"
    sentinel.write_bytes(b"SYNTHETIC_EXISTING_DO_NOT_TOUCH")
    before = files(target.root)
    # Capture security descriptor bytes before/after; no persistent security change.
    import subprocess
    acl_before = subprocess.run(["icacls", str(target.root)], check=True, capture_output=True).stdout
    result = build_local_contribution_application(**args, enabled=True).register(request, correlation="synthetic")
    assert not result.success
    assert files(target.root) == before
    acl_after = subprocess.run(["icacls", str(target.root)], check=True, capture_output=True).stdout
    assert acl_after == acl_before


def test_commit_failure_preserves_intent_version_and_stages_then_stops(tmp_path, monkeypatch):
    args, request, _, target, store = native_fixture(tmp_path)
    original = store._fresh
    def fail_commit(destination, value):
        if destination.parent.name == "commits":
            raise OSError("SYNTHETIC_COMMIT_FAILURE")
        original(destination, value)
    monkeypatch.setattr(store, "_fresh", fail_commit)
    app = build_local_contribution_application(**args, enabled=True)
    result = app.register(request, correlation="synthetic")
    assert result.outcome_status == OutcomeStatus.INDETERMINATE and result.success is False
    assert len(tuple((target.root / "intents").iterdir())) == len(tuple((target.root / "versions").iterdir())) == 1
    assert len(tuple((target.root / "staging").iterdir())) == 3
    before = files(target.root)
    assert app.inspect_operation(LocalContributionRequest(request).sha256)["state"] == "UNKNOWN"
    monkeypatch.setattr(store, "_fresh", original)
    def forbidden():
        raise AssertionError("NO_REALLOCATION_AFTER_HISTORICAL_UNKNOWN")
    monkeypatch.setattr("backend.modules.resource_library.application.commands.register_local_contribution.uuid4", forbidden)
    again = app.register(request, correlation="synthetic")
    assert not again.success and again.outcome_status == OutcomeStatus.INDETERMINATE
    assert again.application_failure.message_key == "LOCAL_CONTRIBUTION_RECONCILE_REQUIRED"
    assert again.side_effects[0]["effect_state"] == "UNKNOWN"
    assert again.side_effects[0]["reconciliation_required"] is True
    assert files(target.root) == before


def test_failure_after_stage_before_intent_publish_never_restores_absent(tmp_path, monkeypatch):
    args, request, _, target, _ = native_fixture(tmp_path)
    link = os.link
    def fail_intent(source, destination, *a, **kw):
        if Path(destination).parent.name == "intents":
            raise OSError("SYNTHETIC_PUBLISH_FAILURE")
        return link(source, destination, *a, **kw)
    monkeypatch.setattr(os, "link", fail_intent)
    app = build_local_contribution_application(**args, enabled=True)
    result = app.register(request, correlation="synthetic")
    assert not result.success and result.outcome_status == OutcomeStatus.INDETERMINATE
    assert len(tuple((target.root / "staging").iterdir())) == 2
    assert not tuple((target.root / "intents").iterdir())
    assert app.inspect_operation(LocalContributionRequest(request).sha256)["state"] == "UNKNOWN"
    before = files(target.root)
    def forbidden(*_a, **_kw):
        raise AssertionError("NO_REALLOCATION_OR_PUBLICATION_AFTER_HISTORICAL_UNKNOWN")
    monkeypatch.setattr("backend.modules.resource_library.application.commands.register_local_contribution.uuid4", forbidden)
    monkeypatch.setattr(os, "link", forbidden)
    again = app.register(request, correlation="synthetic")
    assert not again.success and again.outcome_status == OutcomeStatus.INDETERMINATE
    assert again.application_failure.message_key == "LOCAL_CONTRIBUTION_RECONCILE_REQUIRED"
    assert again.side_effects[0]["effect_state"] == "UNKNOWN"
    assert again.side_effects[0]["reconciliation_required"] is True
    assert files(target.root) == before


def test_flush_failure_keeps_created_objects_and_reports_unknown(tmp_path, monkeypatch):
    args, request, _, target, _ = native_fixture(tmp_path)
    def fail_flush(_):
        raise OSError("SYNTHETIC_FLUSH_FAILURE")
    monkeypatch.setattr(os, "fsync", fail_flush)
    result = build_local_contribution_application(**args, enabled=True).register(request, correlation="synthetic")
    assert result.outcome_status == OutcomeStatus.INDETERMINATE and not result.success
    assert target.root.exists() and (target.root / "writer.lock").exists()


@pytest.mark.parametrize("corruption", ["duplicate_json", "wrong_record", "missing_commit"])
def test_corrupt_or_incomplete_committed_graph_is_not_readable(tmp_path, corruption):
    args, request, _, target, _ = native_fixture(tmp_path)
    app = build_local_contribution_application(**args, enabled=True)
    assert app.register(request, correlation="synthetic").success
    version = next((target.root / "versions").iterdir())
    with args["store"].session():
        record = args["store"].inspect_operation(LocalContributionRequest(request).sha256, args["authority"].sha256)["record"]
    from backend.modules.resource_library.contracts.dto.local_contribution import (
        LocalContributionRecord,
    )
    typed = LocalContributionRecord(record)
    read = read_request(typed)
    if corruption == "missing_commit":
        next((target.root / "commits").iterdir()).rename(target.root / "commits" / "synthetic-displaced.json")
    else:
        version.write_bytes(b'{"contract_id":"x","contract_id":"y"}' if corruption == "duplicate_json" else b'{}')
    before = files(target.root)
    with pytest.raises((ValueError, LocalContributionPersistenceError)):
        app.read(read)
    assert files(target.root) == before


def test_native_directory_lease_prevents_replacement(tmp_path):
    held = tmp_path / "synthetic-held"
    held.mkdir()
    with directory_lease(held, allowed_root=tmp_path):
        with pytest.raises(OSError):
            held.rename(tmp_path / "synthetic-replaced")
    assert held.exists()


def test_writer_lock_refuses_concurrent_store_without_extra_effects(tmp_path):
    args, request, _, target, store = native_fixture(tmp_path)
    app = build_local_contribution_application(**args, enabled=True)
    assert app.register(request, correlation="synthetic").success
    another = LocalContributionFileStore(target, binding_sha256=args["authority"].sha256)
    before = files(target.root)
    with store.session(), pytest.raises(LocalContributionPersistenceError):
        with another.session():
            raise AssertionError("SECOND_WRITER_MUST_NOT_ENTER")
    assert files(target.root) == before


def test_changed_operator_is_rejected_before_any_creation(tmp_path, monkeypatch):
    args, request, calls, target, _ = native_fixture(tmp_path)
    monkeypatch.setattr("backend.adapters.outbound.resource_library.local_contribution_store.native_operator",
        lambda: {"windows_sid": "SYNTHETIC_OTHER_SID", "windows_profile": "SYNTHETIC_OTHER_PROFILE"})
    with pytest.raises(ValueError, match="OPERATOR_CHANGED"):
        build_local_contribution_application(**args, enabled=True).register(request, correlation="synthetic")
    assert not target.root.exists() and calls == []


@pytest.mark.parametrize("folder", ["versions", "commits", "staging", "."])
def test_orphan_inventory_after_commit_is_unknown_and_not_readable(tmp_path, folder):
    args, request, _, target, store = native_fixture(tmp_path)
    app = build_local_contribution_application(**args, enabled=True)
    result = app.register(request, correlation="synthetic")
    assert result.success
    read = {"contract_id": "LOCAL-CONTRIBUTION-READ-1.0", **{k: result.data["record"][k] for k in ("object_ref", "version_ref", "passage_ref")},
        "record_sha256": result.data["record_sha256"]}
    (target.root / folder / "synthetic-orphan.json").write_bytes(b"{}")
    before = files(target.root)
    assert app.inspect_operation(LocalContributionRequest(request).sha256)["state"] == "UNKNOWN"
    with pytest.raises((ValueError, LocalContributionPersistenceError)):
        app.read(read)
    assert not app.register(request, correlation="synthetic").success
    assert files(target.root) == before


def test_retained_stage_alias_cannot_be_replaced_by_a_byte_identical_file(tmp_path):
    args, request, _, target, _ = native_fixture(tmp_path)
    app = build_local_contribution_application(**args, enabled=True)
    assert app.register(request, correlation="synthetic").success
    stage = next((target.root / "staging").iterdir())
    replacement = target.root / "staging" / "synthetic-replacement.pending"
    replacement.write_bytes(stage.read_bytes())
    stage.rename(target.root / "synthetic-displaced.pending")
    replacement.rename(stage)
    assert app.inspect_operation(LocalContributionRequest(request).sha256)["state"] == "UNKNOWN"


def test_target_requires_existing_parent_and_refuses_repository_or_relative_path(tmp_path):
    from backend.adapters.outbound.resource_library.local_contribution_store import _ROOT
    for path in (Path("relative"), _ROOT / "overlay", tmp_path / "absent-parent" / "overlay"):
        with pytest.raises((ValueError, RuntimeError)):
            LocalContributionTarget.prepare(path)


def test_native_reparse_parent_is_rejected_without_following_target(tmp_path):
    import subprocess
    original = tmp_path / "synthetic-original"
    original.mkdir()
    sentinel = original / "do-not-touch.txt"
    sentinel.write_bytes(b"SYNTHETIC_ORIGINAL")
    junction = tmp_path / "synthetic-junction"
    probe = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(junction), str(original)], capture_output=True)
    assert probe.returncode == 0, "Synthetic NTFS junction prerequisite absent"
    with pytest.raises((ValueError, RuntimeError)):
        LocalContributionTarget.prepare(junction / "new-overlay")
    assert sentinel.read_bytes() == b"SYNTHETIC_ORIGINAL" and not (original / "new-overlay").exists()


def test_effective_dacl_widened_on_new_synthetic_record_is_rejected(tmp_path):
    import subprocess
    args, request, _, target, _ = native_fixture(tmp_path)
    app = build_local_contribution_application(**args, enabled=True)
    result = app.register(request, correlation="synthetic")
    assert result.success
    read = {"contract_id": "LOCAL-CONTRIBUTION-READ-1.0", **{k: result.data["record"][k] for k in ("object_ref", "version_ref", "passage_ref")},
        "record_sha256": result.data["record_sha256"]}
    record_path = next((target.root / "versions").iterdir())
    altered = subprocess.run(["icacls", str(record_path), "/grant", "*S-1-1-0:(R)"], capture_output=True)
    assert altered.returncode == 0, "Synthetic owner DACL alteration prerequisite absent"
    with pytest.raises((ValueError, LocalContributionPersistenceError)):
        app.read(read)
    # Only a test-owned object changed; no repair, cleanup or permission reset.
    assert record_path.exists()


def test_v2_real_append_reopen_and_duplicate_preserve_unknown_creation_and_original_recording(tmp_path, monkeypatch):
    args, request, _, target, _ = native_fixture(tmp_path, provenance_v2=True)
    original_raw = args["original_proposal_receipt_evidence"]
    app = build_local_contribution_application(**args, enabled=True)
    result = app.register(request, correlation="synthetic-v2-native")
    assert result.success
    record = result.data["record"]
    provenance = record["provenance"]
    assert provenance["contract_id"] == "LOCAL-CONTRIBUTION-PROVENANCE-2.0"
    assert provenance["draft_created_at"] is None and provenance["draft_creation_status"] == "NOT_ESTABLISHED"
    assert provenance["draft_recorded_at"] == "2001-01-01T01:02:03+00:00"
    assert record["created_at"] != provenance["draft_recorded_at"]
    before = files(target.root)
    args["store"] = LocalContributionFileStore(LocalContributionTarget.prepare(target.root), binding_sha256=args["authority"].sha256)
    reopened = build_local_contribution_application(**args, enabled=True)
    read = {"contract_id": "LOCAL-CONTRIBUTION-READ-1.0", **{k: record[k] for k in ("object_ref", "version_ref", "passage_ref")},
        "record_sha256": result.data["record_sha256"]}
    projection = reopened.read(read)["source_snapshot"]
    assert projection["excerpt"] == request["text"] and projection["provenance"]["origin"] == provenance
    def forbidden():
        raise AssertionError("NO_V2_DUPLICATE_ALLOCATION")
    monkeypatch.setattr("backend.modules.resource_library.application.commands.register_local_contribution.uuid4", forbidden)
    duplicate = reopened.register(request, correlation="synthetic-v2-native")
    assert duplicate.success and duplicate.data["record_sha256"] == result.data["record_sha256"]
    assert duplicate.side_effects[0]["new_effect"] is False
    assert files(target.root) == before and args["original_proposal_receipt_evidence"] == original_raw
