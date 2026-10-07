"""Candidate bytes are never executed; every approved source is independently closed."""
from pathlib import Path

import pytest

from tests.support import r3_d3_scope_guard as guard
from tests.support.r3_guard_oracle import PREPARATION
from tests.support.r3_portable_clone_guard import _inspect_preparations

ROOT = Path(__file__).resolve().parents[2]


def copy_sources(root: Path) -> None:
    for path in guard.PATHS:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / path).read_bytes())


@pytest.mark.parametrize("path", guard.PATHS)
@pytest.mark.usefixtures("historical_guard_sources")
def test_every_file_mutation_missing_and_same_count_replacement(tmp_path: Path, path: str) -> None:
    copy_sources(tmp_path)
    assert guard.violations(tmp_path) == []
    target = tmp_path / path
    raw = target.read_bytes()
    target.write_bytes(raw + b"\n# UNAPPROVED D3 DRIFT\n")
    assert guard.violations(tmp_path)
    assert not guard.index_matches(tmp_path, path, raw)
    target.unlink()
    assert guard.violations(tmp_path)
    replacement = target.with_name(target.name + ".replacement")
    replacement.write_bytes(raw)
    assert guard.violations(tmp_path)


@pytest.mark.parametrize("path", guard.PATHS)
@pytest.mark.usefixtures("historical_guard_sources")
def test_index_is_independent_from_valid_worktree(path: str) -> None:
    raw = (ROOT / path).read_bytes()
    assert guard.index_matches(ROOT, path, raw)
    assert not guard.index_matches(ROOT, path, raw + b"\nINDEX_ONLY_DRIFT")
    if path in guard.PRE:
        assert guard.index_matches(ROOT, path, guard.baseline_bytes(path))


@pytest.mark.parametrize("path", [guard.SELF, guard.PORTABLE])
def test_pin_and_selfhash_cannot_be_self_approved(tmp_path: Path, path: str) -> None:
    copy_sources(tmp_path)
    target = tmp_path / path
    target.write_bytes(target.read_bytes().replace(guard.ORACLE_SHA256.encode(), b"f" * 64))
    assert not guard.authenticated(tmp_path)
    assert not guard.authenticated(tmp_path, expected="f" * 64)


def test_unapproved_ast_and_guard_signatures_rejected() -> None:
    for path in guard.PRE:
        raw = guard.baseline_bytes(path)
        if path.endswith(".py"):
            assert guard.outside_scope(raw, path) != guard.outside_scope(raw + b"\nOUTSIDE_SCOPE = 1\n", path)
    path = guard.PORTABLE
    raw = guard.baseline_bytes(path)
    assert guard.outside_scope(raw, path) != guard.outside_scope(raw.replace(b"def violations(root: Path,", b"def violations(root: str,"), path)


def test_private_sources_absent_not_attested_and_indexed_rejected(tmp_path: Path) -> None:
    copy_sources(tmp_path)
    absent = _inspect_preparations(tmp_path, PREPARATION, require_complete=False, git_paths=set())
    assert not absent.errors
    # Existing private-source guard carries the detailed absence/partial/symlink matrix.
    assert "NOT_PERFORMED_ABSENT" in repr(absent)
    indexed = _inspect_preparations(
        tmp_path, PREPARATION, require_complete=False, git_paths={next(iter(PREPARATION))}
    )
    assert indexed.status == "FAIL"
    assert indexed.errors == ("PROTECTED_DOCUMENT_INDEXED:" + next(iter(PREPARATION)),)
    assert set(guard.PATHS).isdisjoint(PREPARATION)
    assert guard.violations(tmp_path, changed=set(guard.PATHS) | {next(iter(PREPARATION))})
