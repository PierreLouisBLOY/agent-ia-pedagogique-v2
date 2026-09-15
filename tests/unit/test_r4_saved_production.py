import json
import subprocess
import sys

import pytest

from backend.adapters.outbound.persistence import saved_production as adapter
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.support.r4_synthetic import record


def test_atomic_idempotent_exact_and_restart(tmp_path):
    root = tmp_path / "r4"
    store = adapter.LocalSavedProductionStore(root, create=True)
    value = record()
    assert store.save(value) is True
    before = (root / "catalog.json").read_bytes()
    assert store.save(value) is False
    assert (root / "catalog.json").read_bytes() == before
    child = subprocess.run([sys.executable, "-B", "-c",
        "import sys,json; from pathlib import Path; "
        "from backend.adapters.outbound.persistence.saved_production import LocalSavedProductionStore; "
        "s=LocalSavedProductionStore(Path(sys.argv[1])); "
        "print(json.dumps([r.sha256 for r in s.list_versions()]))", str(root)],
        check=True, capture_output=True, text=True)
    assert json.loads(child.stdout) == [value.sha256]
    reopened = adapter.LocalSavedProductionStore(root)
    assert reopened.load(value.production_ref, value.version_ref).data == value.data
    assert reopened.actions(value) == ()


def test_same_identity_different_content_and_version_four_refused(tmp_path):
    store = adapter.LocalSavedProductionStore(tmp_path / "r4", create=True)
    value = record()
    store.save(value)
    changed = value.mutable_copy()
    changed["reservations"].append("Contenu différent")
    with pytest.raises(ValueError, match="IDENTITY_CONFLICT"):
        store.save(SavedProduction(changed))
    store.save(record(2))
    store.save(record(3))
    with pytest.raises(ValueError, match="VERSION_LIMIT"):
        store.save(record(4))
    assert len(store.list_versions()) == 3


def test_failure_before_replace_keeps_prior_catalog(tmp_path, monkeypatch):
    root = tmp_path / "r4"
    store = adapter.LocalSavedProductionStore(root, create=True)
    store.save(record())
    before = (root / "catalog.json").read_bytes()
    def failure(*args, **kwargs):
        raise OSError("ARTIFICIAL_WRITE_FAILURE")
    monkeypatch.setattr(adapter, "atomic_replace_checked", failure)
    with pytest.raises(OSError):
        store.save(record(2))
    assert (root / "catalog.json").read_bytes() == before
    assert len(adapter.LocalSavedProductionStore(root).list_versions()) == 1


def test_draft_and_import_are_passive_and_reports_bound(tmp_path):
    store = adapter.LocalSavedProductionStore(tmp_path / "r4", create=True)
    value = record(imported=True)
    store.save(value)
    assert store.load(value.production_ref, value.version_ref).data["origin"] == "IMPORTED_DOCUMENTARY"
    assert not store.actions(value)
    changed = value.mutable_copy()
    changed["validations"] = [{"production_ref": value.production_ref, "version_ref": record(2).version_ref}]
    with pytest.raises(ValueError, match="REPORT_MISMATCH"):
        SavedProduction(changed)
    store.save(record(2, draft=True))
    assert store.load(value.production_ref, record(2).version_ref).bundle is None


def test_explicit_fresh_root_identity_and_corruption(tmp_path):
    with pytest.raises(ValueError, match="FRESH_ROOT_REQUIRED"):
        adapter.LocalSavedProductionStore(tmp_path, create=True)
    root = tmp_path / "r4"
    store = adapter.LocalSavedProductionStore(root, create=True)
    store.save(record())
    data = json.loads((root / "catalog.json").read_bytes())
    data["sha256"] = "0" * 64
    (root / "catalog.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="CATALOG_INTEGRITY"):
        store.list_versions()
    with pytest.raises(ValueError, match="OUTSIDE_REPOSITORY"):
        adapter.LocalSavedProductionStore(adapter._ROOT / "forbidden")


def test_action_order_and_atomic_compare_and_append(tmp_path):
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
    store = adapter.LocalSavedProductionStore(tmp_path / "r4", create=True)
    value = record()
    store.save(value)
    first = {"action_id": "action:" + "f" * 32, "kind": "TEST"}
    second = {"action_id": "action:" + "a" * 32, "kind": "TEST"}
    initial = fingerprint(store.actions(value))
    store.append_action(value, first["action_id"], first, expected_actions_sha256=initial)
    with pytest.raises(ValueError, match="ACTIONS_CHANGED"):
        store.append_action(value, second["action_id"], second, expected_actions_sha256=initial)
    store.append_action(value, second["action_id"], second)
    assert [a["action_id"] for a in store.actions(value)] == [first["action_id"], second["action_id"]]


def test_process_death_before_commit_releases_lock_and_preserves_catalog(tmp_path):
    root = tmp_path / "r4"
    store = adapter.LocalSavedProductionStore(root, create=True)
    value = record()
    store.save(value)
    before = (root / "catalog.json").read_bytes()
    child = subprocess.run([sys.executable, "-B", "-c",
        "import sys,os; from pathlib import Path; "
        "from backend.adapters.outbound.persistence.saved_production import LocalSavedProductionStore; "
        "from tests.support.r4_synthetic import record; "
        "s=LocalSavedProductionStore(Path(sys.argv[1])); "
        "s._publish=lambda *a, **k: os._exit(73); s.save(record(2))", str(root)],
        capture_output=True, text=True)
    assert child.returncode == 73
    assert (root / "catalog.json").read_bytes() == before
    restarted = adapter.LocalSavedProductionStore(root)
    assert restarted.save(record(2)) is True
    assert len(restarted.list_versions()) == 2
