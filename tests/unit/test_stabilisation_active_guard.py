"""Archival fixtures never exempt their active owners from exact protection."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.architecture.test_conversation_product_boundary import CORRECTION_PATHS, R2_PATHS
from tests.support import (
    r3_cap_a01_guard,
    r3_d3_scope_guard,
    r3_editorial_correction_guard,
    r3_guard_oracle,
    r3_locator_materialization_guard,
    r3_parse_observability_guard,
    r3_portable_clone_guard,
    r3_prepare_contract_alignment_guard,
    r3_serializer_8192_guard,
    r4_scope_guard,
    r5_scope_guard,
)
from tests.support import (
    r6_scope_guard as guard,
)

ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_OWNERS = tuple(sorted(set().union(
    R2_PATHS,
    CORRECTION_PATHS,
    r3_guard_oracle.R3_PATHS,
    r3_cap_a01_guard.PATHS,
    r3_d3_scope_guard.PATHS,
    r3_editorial_correction_guard.PATHS,
    r3_locator_materialization_guard.PATHS,
    r3_parse_observability_guard.PATCH_PATHS,
    r3_portable_clone_guard.PATHS,
    r3_prepare_contract_alignment_guard.PATHS,
    r3_serializer_8192_guard.PATHS,
    r4_scope_guard.PATHS,
    r5_scope_guard.PATHS,
    {"backend/adapters/outbound/review/openai/adapter.py"},
) - set(r3_guard_oracle.PREPARATION)))


def git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=root, input=input_bytes,
                          capture_output=True, check=True).stdout


@pytest.fixture(scope="module")
def active_clone(tmp_path_factory):
    root = tmp_path_factory.mktemp("active-stabilisation")
    for path in (*guard.PATHS, guard.SELF, guard.MANIFEST):
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / path).read_bytes())
    git(root, "init", "--quiet")
    paths = (*guard.PATHS, guard.SELF, guard.MANIFEST)
    git(root, "add", "--pathspec-from-file=-", "--pathspec-file-nul",
        input_bytes=b"\0".join(path.encode("utf-8") for path in paths) + b"\0")
    assert guard.violations(root) == []
    return root


@pytest.mark.parametrize("path", guard.PATHS)
def test_active_owner_working_and_real_index_mutations(active_clone, path):
    root = active_clone
    target = root / path
    raw = target.read_bytes()
    original_oid = git(root, "rev-parse", ":" + path).decode().strip()
    assert guard.exact(root, path)
    assert guard.index_matches(root, path, git(root, "show", ":" + path))
    try:
        replacement = raw + b"\n# unapproved active substitution\n"
        target.write_bytes(replacement)
        assert not guard.exact(root, path)
        target.unlink()
        assert not guard.exact(root, path)
        target.write_bytes(b"# same-path replacement from an unapproved owner\n")
        assert not guard.exact(root, path)
        target.write_bytes(raw)
        replacement_oid = git(root, "hash-object", "-w", "--stdin", input_bytes=replacement).decode().strip()
        git(root, "update-index", "--cacheinfo", "100644", replacement_oid, path)
        assert guard.exact(root, path), "a valid worktree must not hide index substitution"
        assert not guard.index_matches(root, path, git(root, "show", ":" + path))
        git(root, "update-index", "--force-remove", "--", path)
        assert subprocess.run(["git", "show", ":" + path], cwd=root, capture_output=True).returncode != 0
    finally:
        target.write_bytes(raw)
        git(root, "update-index", "--add", "--cacheinfo", "100644", original_oid, path)
    assert guard.exact(root, path)
    assert guard.index_matches(root, path, git(root, "show", ":" + path))


def test_active_delta_uses_real_git_inventory_without_archival_exemption():
    changed = set(git(ROOT, "diff", "--name-only", guard.BASELINE, "--").decode().splitlines())
    changed.update(git(ROOT, "ls-files", "--others", "--exclude-standard").decode().splitlines())
    # Declared withdrawals stay visible in the delta; their bytes must never
    # regain authority through the current index.
    assert changed & set(r3_guard_oracle.PREPARATION) == set(guard.PRIVATE_PREPARATION_PATHS)
    indexed = set(git(ROOT, "ls-files").decode().splitlines())
    assert not indexed & set(r3_guard_oracle.PREPARATION)
    assert guard.active_delta_violations(ROOT, changed) == []
    assert set(HISTORICAL_OWNERS) <= set(guard.PATHS)


@pytest.mark.parametrize("path", [guard.SELF, guard.MANIFEST])
def test_guard_or_manifest_substitution_rejects_all_active_owners(active_clone, path):
    target = active_clone / path
    raw = target.read_bytes()
    try:
        target.write_bytes(raw + b"\n# substitution\n")
        assert not guard.authenticated(active_clone)
        assert not guard.exact(active_clone, HISTORICAL_OWNERS[0])
    finally:
        target.write_bytes(raw)


@pytest.mark.parametrize("stage", ("untracked", "staged", "committed"))
def test_portable_active_public_inventory_at_each_real_git_state(tmp_path, stage):
    """Current public ownership is separate from a private historical attestation."""
    root = tmp_path / stage
    root.mkdir()
    public = set(guard.PATHS) | {guard.SELF, guard.MANIFEST}
    assert not public & set(guard.PRIVATE_PREPARATION_PATHS)
    for path in sorted(public):
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / path).read_bytes())
    git(root, "init", "--quiet")
    if stage != "untracked":
        git(root, "add", "--pathspec-from-file=-", "--pathspec-file-nul",
            input_bytes=b"\0".join(path.encode("utf-8") for path in sorted(public)) + b"\0")
    if stage == "committed":
        git(root, "-c", "commit.gpgsign=false", "-c", "user.name=Portable synthetic fixture", "-c",
            "user.email=portable-fixture@example.invalid", "commit", "--quiet",
            "-m", "Synthetic public inventory only")
    tracked = set(git(root, "ls-files").decode().splitlines())
    untracked = set(git(root, "ls-files", "--others", "--exclude-standard").decode().splitlines())
    assert tracked == (set() if stage == "untracked" else public)
    assert untracked == (public if stage == "untracked" else set())
    assert not (tracked | untracked) & set(guard.PRIVATE_PREPARATION_PATHS)
    assert all(not (root / path).exists() for path in guard.PRIVATE_PREPARATION_PATHS)
    private = r3_portable_clone_guard._inspect_preparations(
        root, r3_guard_oracle.PREPARATION, require_complete=False, git_paths=tracked)
    assert private.status == "NOT_PERFORMED_ABSENT" and private.present_count == 0
    assert not private.errors
    required_private = r3_portable_clone_guard._inspect_preparations(
        root, r3_guard_oracle.PREPARATION, require_complete=True, git_paths=tracked)
    assert required_private.status == "FAIL", "public ownership cannot attest absent private bytes"
    assert set(HISTORICAL_OWNERS) <= set(guard.PATHS)
    assert guard.violations(root) == []
    if stage != "untracked":
        for path in guard.PATHS:
            assert guard.index_matches(root, path, git(root, "show", ":" + path))
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"],
                          cwd=root, capture_output=True)
    if stage == "committed":
        assert head.returncode == 0
        committed = set(git(root, "ls-tree", "-r", "--name-only", "HEAD").decode().splitlines())
        assert committed == public
        for path in guard.PATHS:
            assert guard.index_matches(root, path, git(root, "show", "HEAD:" + path))
    else:
        assert head.returncode != 0


@pytest.mark.parametrize("missing", ("contracts.py", "transport.py", "both"))
def test_portable_shared_modules_missing_worktree_and_real_index(active_clone, missing):
    """Module absence is a current defect, without private-fixture diagnostics."""
    root = active_clone
    modules = tuple("backend/adapters/outbound/openai/" + name
                    for name in ("contracts.py", "transport.py"))
    selected = modules if missing == "both" else tuple(p for p in modules if p.endswith(missing))
    saved = {path: ((root / path).read_bytes(), git(root, "rev-parse", ":" + path).decode().strip())
             for path in selected}
    assert set(modules) <= set(guard.PATHS)
    try:
        for path in selected:
            (root / path).unlink()
        assert set(guard.violations(root)) == {"R6_IDENTITY:" + path for path in selected}
        assert all(guard.index_matches(root, path, git(root, "show", ":" + path))
                   for path in modules)
        for path in selected:
            raw, _ = saved[path]
            (root / path).write_bytes(raw)
            replacement = raw + b"\n# synthetic rejected shared module substitution\n"
            oid = git(root, "hash-object", "-w", "--stdin", input_bytes=replacement).decode().strip()
            git(root, "update-index", "--cacheinfo", "100644", oid, path)
        assert guard.violations(root) == []
        for path in selected:
            assert not guard.index_matches(root, path, git(root, "show", ":" + path))
            git(root, "update-index", "--force-remove", "--", path)
            assert subprocess.run(["git", "show", ":" + path],
                                  cwd=root, capture_output=True).returncode != 0
        assert not set(selected) & set(git(root, "ls-files").decode().splitlines())
        assert not set(git(root, "ls-files").decode().splitlines()) & set(guard.PRIVATE_PREPARATION_PATHS)
    finally:
        for path, (raw, oid) in saved.items():
            (root / path).write_bytes(raw)
            git(root, "update-index", "--add", "--cacheinfo", "100644", oid, path)
    assert guard.violations(root) == []
    assert all(guard.index_matches(root, path, git(root, "show", ":" + path)) for path in modules)
