"""Closed archival inventory plus all original identities and real index checks."""
from __future__ import annotations

import subprocess
from pathlib import Path

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

GUARDS = (r3_cap_a01_guard, r3_d3_scope_guard, r3_editorial_correction_guard,
    r3_locator_materialization_guard, r3_portable_clone_guard,
    r3_prepare_contract_alignment_guard, r3_serializer_8192_guard, r4_scope_guard, r5_scope_guard)
OWNERS = tuple(sorted(set().union(r3_guard_oracle.R3_PATHS,
    r3_parse_observability_guard.PATCH_PATHS, *(g.PATHS for g in GUARDS))
    - set(r3_guard_oracle.PREPARATION)))


def assert_historical_git_state(root: Path) -> None:
    # Exact global inventory already composes the admitted R4/R5 successors.
    # It invokes the original locator/CAP/serializer/portable/editorial/parse
    # identity predicates transitively, including the alignment successor.
    assert r3_guard_oracle.active_inventory(root) == []
    assert r5_scope_guard.violations(root) == []
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=root,
        check=True, capture_output=True).stdout.decode().split("\0")
    assert not set(tracked) & set(r3_guard_oracle.PREPARATION)
    for path in OWNERS:
        staged = subprocess.run(["git", "show", ":" + path], cwd=root,
            check=True, capture_output=True).stdout
        working = (root / path).read_bytes()
        assert staged.replace(b"\r\n", b"\n") == working.replace(b"\r\n", b"\n"), path
