"""Portable guard regressions; no private preparation is copied or imported."""
from __future__ import annotations

import hashlib
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.support import r3_portable_clone_guard as guard
from tests.support.r3_guard_oracle import PREPARATION, READ_ONLY, active_inventory

ROOT = Path(__file__).resolve().parents[2]


def synthetic_set(root: Path) -> dict[str, str]:
    expected = {}
    for index in range(27):
        path = f"synthetic-private/item-{index:02d}.txt"
        raw = f"ARTIFICIAL FIXTURE {index}\n".encode()
        target = root / path
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(raw)
        expected[path] = hashlib.sha256(raw).hexdigest()
    assert not set(expected) & set(PREPARATION)
    return expected


def inspect(root: Path, expected: dict[str, str], *, author: bool = False,
            git_paths: set[str] | None = None) -> guard.PrivatePreparationResult:
    # Explicit synthetic map, never a canonical hash override or a production flag.
    return guard._inspect_preparations(
        root, expected, require_complete=author, git_paths=git_paths or set()
    )


def copy_successor(root: Path) -> None:
    assert not set(guard.PATHS) & set(PREPARATION)
    for path in guard.PATHS:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / path).read_bytes())


def test_absent_private_set_never_reads_private_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("NO_PRIVATE_READ_PERMITTED")
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    result = inspect(tmp_path, PREPARATION)
    assert result.status == "NOT_PERFORMED_ABSENT" and result.present_count == 0
    assert result.errors == ()
    assert inspect(tmp_path, PREPARATION, author=True).status == "FAIL"


@pytest.mark.parametrize("author", [False, True])
def test_explicit_synthetic_complete_attestation(tmp_path: Path, author: bool) -> None:
    expected = synthetic_set(tmp_path)
    result = inspect(tmp_path, expected, author=author)
    assert result.status == "PASS" and result.present_count == 27 and not result.errors


@pytest.mark.parametrize("fault", ["partial", "changed", "unreadable"])
@pytest.mark.parametrize("author", [False, True])
def test_private_inconsistency_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str, author: bool) -> None:
    expected = synthetic_set(tmp_path)
    path = next(iter(expected))
    target = tmp_path / path
    if fault == "partial":
        target.unlink()  # Synthetic fixture only.
    elif fault == "changed":
        target.write_bytes(b"ARTIFICIAL MUTATION\n")
    else:
        read = Path.read_bytes
        def unreadable(file: Path) -> bytes:
            if file == target:
                raise PermissionError("synthetic")
            return read(file)
        monkeypatch.setattr(Path, "read_bytes", unreadable)
    result = inspect(tmp_path, expected, author=author)
    assert result.status == "FAIL"
    assert result.errors


@pytest.mark.parametrize("kind", ["symlink", "junction"])
@pytest.mark.parametrize("location", ["parent", "file"])
def test_redirected_preparations_fail_before_payload_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, location: str) -> None:
    expected = synthetic_set(tmp_path)
    target = tmp_path / next(iter(expected))
    redirected = target.parent if location == "parent" else target
    lstat = Path.lstat
    read = Path.read_bytes
    def redirected_stat(file: Path) -> Any:
        if file == redirected:
            return SimpleNamespace(st_mode=stat.S_IFLNK if kind == "symlink" else stat.S_IFDIR,
                                   st_file_attributes=0x400 if kind == "junction" else 0)
        return lstat(file)
    def no_follow(file: Path) -> bytes:
        assert file != target
        return read(file)
    monkeypatch.setattr(Path, "lstat", redirected_stat)
    monkeypatch.setattr(Path, "read_bytes", no_follow)
    assert inspect(tmp_path, expected).status == "FAIL"


@pytest.mark.parametrize("present", [False, True])
def test_tracked_private_is_forbidden_even_when_absent(tmp_path: Path, present: bool) -> None:
    expected = synthetic_set(tmp_path)
    path = next(iter(expected))
    if not present:
        (tmp_path / path).unlink()
    result = inspect(tmp_path, expected, git_paths={path})
    assert "PROTECTED_DOCUMENT_INDEXED:" + path in result.errors


@pytest.mark.parametrize("which", ["index", "head"])
def test_production_entry_checks_head_and_index_independently(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, which: str) -> None:
    path = next(iter(PREPARATION))
    calls: list[list[str]] = []
    def inventory(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        selected = ("ls-files" in args) if which == "index" else ("ls-tree" in args)
        return subprocess.CompletedProcess(args, 0, stdout=path + "\0" if selected else "")
    monkeypatch.setattr(subprocess, "run", inventory)
    result = guard.private_preparations(tmp_path)
    assert "PROTECTED_DOCUMENT_INDEXED:" + path in result.errors
    assert len(calls) == 2


def test_production_entry_has_no_reference_map_override() -> None:
    import inspect as signatures
    assert list(signatures.signature(guard.private_preparations).parameters) == ["root", "require_complete"]


@pytest.mark.parametrize("path", guard.PATHS)
def test_every_successor_dependency_missing_or_modified_is_rejected(tmp_path: Path, path: str) -> None:
    copy_successor(tmp_path)
    assert guard.violations(tmp_path) == []
    target = tmp_path / path
    raw = target.read_bytes()
    target.write_bytes(raw + b"\n# unauthorized successor drift\n")
    assert guard.violations(tmp_path)
    if path in guard.PRE:
        assert not guard.source_matches(tmp_path, path, guard.PRE[path])
    target.unlink()
    assert guard.violations(tmp_path)


@pytest.mark.parametrize("fault", ["extra", "missing", "same_count"])
def test_exact_effective_inventory_cannot_be_redeclared(fault: str) -> None:
    changed = set(guard.PATHS)
    if fault != "extra":
        changed.remove(guard.PATHS[0])
    if fault != "missing":
        changed.add("tests/support/unapproved_guard.py")
    assert guard.violations(ROOT, changed=changed)


def test_candidate_self_hash_and_editorial_pin_are_not_authority(tmp_path: Path) -> None:
    copy_successor(tmp_path)
    target = tmp_path / guard.SELF
    raw = target.read_bytes() + b"\n# fabricated authority\n"
    claimed = guard.digest(guard.canonical_bytes(guard.SELF, raw))
    target.write_bytes(raw.replace(guard.ORACLE_SHA256.encode(), claimed.encode()))
    editor = tmp_path / guard.EDITORIAL
    editor.write_bytes(editor.read_bytes().replace(guard.ORACLE_SHA256.encode(), claimed.encode()))
    assert not guard.authenticated(tmp_path)
    assert not guard.authenticated(tmp_path, expected=claimed)


def test_binding_value_cannot_be_changed_in_isolation(tmp_path: Path) -> None:
    copy_successor(tmp_path)
    target = tmp_path / guard.EDITORIAL
    target.write_bytes(target.read_bytes().replace(guard.ORACLE_SHA256.encode(), b"f" * 64))
    assert not guard.authenticated(tmp_path)


@pytest.mark.parametrize("path", guard.PATHS)
def test_every_staged_mutation_rejected_with_valid_worktree(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    run = subprocess.run
    def corrupt(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        if args == ["git", "show", ":" + path]:
            return subprocess.CompletedProcess(args, 0, stdout=(ROOT / path).read_bytes() + b"\nDRIFT\n")
        return run(args, **kwargs)
    monkeypatch.setattr(subprocess, "run", corrupt)
    with pytest.raises(AssertionError):
        guard.assert_git_state(ROOT)


@pytest.mark.parametrize("path", tuple(guard.PRE))
def test_signatures_and_outside_scope_nodes_remain_protected(path: str) -> None:
    before = guard.baseline_bytes(path)
    after = (ROOT / path).read_bytes()
    assert guard.outside_scope(before, path) == guard.outside_scope(after, path)
    assert guard.outside_scope(before, path) != guard.outside_scope(after + b"\nUNAPPROVED = 1\n", path)


@pytest.mark.parametrize("fault", ["missing", "altered"])
@pytest.mark.parametrize("private_mode", ["absent", "author"])
def test_read_only_source_failure_is_never_private_absence_tolerance(monkeypatch: pytest.MonkeyPatch, fault: str, private_mode: str) -> None:
    from tests.support import r3_parse_observability_guard as historical
    path = next(iter(READ_ONLY))
    original = historical.active_source_matches
    def changed(root: Path, item: str, expected: str) -> bool:
        return False if item == path else original(root, item, expected)
    monkeypatch.setattr(historical, "active_source_matches", changed)
    if fault == "missing":
        is_file = Path.is_file
        monkeypatch.setattr(Path, "is_file", lambda file: False if file == ROOT / path else is_file(file))
    status = "PASS" if private_mode == "author" else "NOT_PERFORMED_ABSENT"
    monkeypatch.setattr(guard, "private_preparations",
                        lambda *a, **kw: guard.PrivatePreparationResult(status, 27 if status == "PASS" else 0, ()))
    assert "PROTECTED_DOCUMENT_CHANGED:" + path in active_inventory(ROOT)


def test_tracked_inventory_and_exact_successor_are_valid_without_attesting_private_absence() -> None:
    guard.assert_scope(ROOT)
    guard.assert_git_state(ROOT)
    assert active_inventory(ROOT) == []
    result = guard.private_preparations(ROOT)
    assert result.status in {"PASS", "NOT_PERFORMED_ABSENT"}
    if result.status == "NOT_PERFORMED_ABSENT":
        assert result.present_count == 0
        assert guard.private_preparations(ROOT, require_complete=True).status == "FAIL"
