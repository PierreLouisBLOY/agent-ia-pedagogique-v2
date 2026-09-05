from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.support.historical_hash_freeze import B01_FREEZE, assert_current_historical_hashes
from tests.support.repository_hygiene import (
    forbidden_source_paths,
    repository_paths,
    require_external_temp_root,
    retention_inventory,
)

ROOT = Path(__file__).resolve().parents[2]
POSITIVE = (
    "backup.bak", "deep/backup.backup", "backup.bak.manifest.json",
    "deep/backup.backup.manifest.json", "scratch.tmp", "deep/index.building",
    "deep/events.jsonl",
)
NEGATIVE = (
    "MANIFEST_SHA256.txt", "docs/evidence.json", "docs/manifest.json",
    "docs/backup_policy.md", "database/migrations/002_contract.sql",
    "backend/adapters/outbound/artifacts/__init__.py", "tests/test_log_policy.py",
    "pyproject.toml", "requirements/lock/dev-py312-win.txt",
)


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=root, check=True,
                          capture_output=True, text=True)


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "--quiet")
    (tmp_path / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
    return tmp_path


@pytest.mark.parametrize("relative", POSITIVE)
def test_four_assigned_ignore_families(checkout: Path, relative: str) -> None:
    _git(checkout, "check-ignore", "--no-index", "--", relative)


@pytest.mark.parametrize("relative", NEGATIVE)
def test_ignore_does_not_mask_canonical_candidates(checkout: Path, relative: str) -> None:
    result = subprocess.run(["git", "check-ignore", "--no-index", "--", relative],
                            cwd=checkout, check=False, capture_output=True)
    assert result.returncode == 1


def test_git_inventory_is_deterministic_with_ignored_nested_clone(checkout: Path) -> None:
    (checkout / "source.py").write_text("value = 1\n", encoding="utf-8")
    _git(checkout, "add", "--", ".gitignore", "source.py")
    before = repository_paths(checkout)
    nested = checkout / ".tmp" / "nested-clone"
    nested.mkdir(parents=True)
    _git(nested, "init", "--quiet")
    (nested / "runtime.sqlite").write_bytes(b"test fixture only")
    (nested / "bad.py").write_text("not source", encoding="utf-8")
    for name in (".venv-validation", "artifacts", ".mypy_cache"):
        (checkout / name).mkdir()
        (checkout / name / "nested.db").write_bytes(b"test fixture only")
    assert repository_paths(checkout) == before
    (checkout / "new_source.py").write_text("", encoding="utf-8")
    assert repository_paths(checkout) == tuple(sorted((*before, "new_source.py")))


@pytest.mark.parametrize("relative", ("hidden.db", "data.db-wal", "backup.bak", ".env",
                                     "local.env", "log.jsonl", "index.building", "out.tmp"))
def test_force_added_ignored_or_config_file_cannot_evade_guard(checkout: Path, relative: str) -> None:
    (checkout / relative).write_bytes(b"synthetic fixture")
    _git(checkout, "add", "--force", "--", relative)
    assert forbidden_source_paths(repository_paths(checkout)) == (relative,)


def test_git_failure_is_not_reported_as_clean(tmp_path: Path) -> None:
    with pytest.raises(subprocess.CalledProcessError):
        repository_paths(tmp_path)


@pytest.mark.parametrize("relative", (".", ".tmp/new", "tests/../tmp/new"))
def test_temporary_output_inside_checkout_rejected(tmp_path: Path, relative: str) -> None:
    with pytest.raises(ValueError, match="outside"):
        require_external_temp_root(tmp_path / relative, tmp_path)


def test_system_temporary_output_allowed(tmp_path: Path) -> None:
    assert require_external_temp_root(tmp_path / "scratch", tmp_path / "checkout") == tmp_path / "scratch"


def test_retention_is_metadata_only_and_never_removes_old_artifacts(checkout: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    directory = checkout / ".tmp" / "old-test"
    directory.mkdir(parents=True)
    artifact = directory / "runtime.sqlite"
    artifact.write_bytes(b"must never be read by inventory")
    os.utime(artifact, (1, 1))
    os.utime(directory, (1, 1))

    def forbidden_read(*args: object, **kwargs: object) -> None:
        pytest.fail("Local file contents must not be opened")

    monkeypatch.setattr(Path, "open", forbidden_read)
    before = retention_inventory(checkout)
    after = retention_inventory(checkout)
    assert before == after
    assert before["deletion_count"] == 0
    item = before["items"][0]
    assert item["older_than_review_age"] is True
    assert item["safe_to_remove"] is False
    assert item["disposition"] == "RETAIN_LOCAL_NO_DELETE_AUTHORITY"
    assert artifact.exists()


def test_unreadable_subtree_is_explicitly_retained(checkout: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    directory = checkout / ".tmp" / "unreadable"
    directory.mkdir(parents=True)
    original = os.scandir

    def inaccessible(path: object) -> object:
        if Path(str(path)) == directory:
            raise PermissionError("synthetic private error not to disclose")
        return original(path)

    monkeypatch.setattr(os, "scandir", inaccessible)
    inventory = retention_inventory(checkout)
    assert inventory["items"][0]["unreadable_count"] == 1
    assert inventory["items"][0]["disposition"] == "RETAIN_UNKNOWN"
    assert "private error" not in json.dumps(inventory)


def test_runtime_and_secrets_not_in_git_candidates() -> None:
    assert forbidden_source_paths(repository_paths(ROOT)) == ()


def test_all_canonical_tracked_evidence_is_not_masked() -> None:
    paths = repository_paths(ROOT, tracked_only=True)
    evidence = [p for p in paths if p.startswith(("docs/", "architecture/", "database/", "requirements/"))]
    result = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"],
                            cwd=ROOT, input="\0".join(evidence) + "\0",
                            check=False, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout


def test_b01_evidence_stays_tracked_and_historical_freeze_stays_intact() -> None:
    allowlist = ROOT / "docs/development/phase_12_17_08_b01_consolidation_de_provenance/12_STAGING_ALLOWLIST.txt"
    paths = {p.strip() for p in allowlist.read_text(encoding="utf-8").splitlines() if p.strip()}
    assert paths <= set(repository_paths(ROOT, tracked_only=True))
    freeze = json.loads((ROOT / B01_FREEZE).read_text(encoding="utf-8"))
    from tests.architecture.test_conversation_product_boundary import (
        r2_historical_entry_sha256,
    )
    evolved = "tests/calibration/pedagogical/repair_tranche_v4_2.py"
    entries = [entry["path"] for entry in freeze["entries"]]
    assert len(entries) == 40 and entries.count(evolved) == 1
    entry = next(entry for entry in freeze["entries"] if entry["path"] == evolved)
    assert r2_historical_entry_sha256(ROOT, evolved) == entry["sha256_current"]
    assert_current_historical_hashes(ROOT, [path for path in entries if path != evolved])
    # The freeze manifest itself must stay byte-identical to the B06 entry baseline.
    baseline = _git(ROOT, "show", f"313d574cc0aca15529978db622939ed648d0c1c7:{B01_FREEZE.as_posix()}")
    current = (ROOT / B01_FREEZE).read_text(encoding="utf-8")
    assert hashlib.sha256(baseline.stdout.encode()).digest() == hashlib.sha256(current.encode()).digest()
