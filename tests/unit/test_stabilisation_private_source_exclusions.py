"""Canonical private originals are never copied; mutations use synthetic bytes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support import r6_scope_guard as guard
from tests.unit.test_stabilisation_active_guard import active_clone, git

# Reuse the existing declared fixture of current protected CODE owners only.
# Its PATHS exclude every original private preparation.
__all__ = ["active_clone"]


def test_only_exact_closed_private_inventory_is_accepted():
    assert len(guard.PRIVATE_PREPARATION_PATHS) == 27
    assert not guard.PRIVATE_PREPARATION_PATHS & set(guard.PATHS)
    assert guard.private_source_inventory(sorted(guard.PRIVATE_PREPARATION_PATHS)) == guard.PRIVATE_PREPARATION_PATHS


@pytest.mark.parametrize("fault", ["omission", "unknown", "duplicate", "tuple", "mapping", "traversal"])
def test_no_other_owner_can_be_excluded(fault):
    value = sorted(guard.PRIVATE_PREPARATION_PATHS)
    if fault == "omission":
        value.pop()
    elif fault == "unknown":
        value[0] = "backend/adapters/inbound/api/search.py"
    elif fault == "duplicate":
        value.append(value[0])
    elif fault == "tuple":
        value = tuple(value)
    elif fault == "mapping":
        value = {"private_source_exclusions": value}
    else:
        value[0] = "../unapproved.md"
    assert guard.private_source_inventory(value) is None


@pytest.mark.parametrize("path", sorted(guard.PRIVATE_PREPARATION_PATHS))
def test_each_forced_private_index_entry_is_rejected_without_reading_originals(active_clone: Path, path):
    declared = set(json.loads((active_clone / guard.MANIFEST).read_bytes())["active_delta_paths"])
    assert guard.active_delta_violations(active_clone, declared) == []
    synthetic = active_clone / path
    synthetic.parent.mkdir(parents=True, exist_ok=True)
    synthetic.write_bytes(b"EXPLICIT_SYNTHETIC_PRIVATE_INDEX_MUTATION; not an original document\n")
    # Ignored local files have no private attestation and acquire no source authority.
    assert guard.active_delta_violations(active_clone, declared) == []
    git(active_clone, "add", "-f", "--", path)
    try:
        assert guard.active_delta_violations(active_clone, declared) == ["R6_PRIVATE_SOURCE_INDEXED:" + path]
    finally:
        git(active_clone, "rm", "--cached", "--", path)
        synthetic.unlink()
    assert guard.active_delta_violations(active_clone, declared) == []
