"""Synthetic archival source/index counterexamples; no private attestation."""
from pathlib import Path

import pytest

from tests.support.historical_git_successor import assert_historical_git_state
from tests.support.historical_guard_fixture import materialize_historical_guard_sources
from tests.unit.test_stabilisation_active_guard import git

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("fault", ["source", "index", "untracked", "staged_unknown", "missing"])
@pytest.mark.usefixtures("historical_guard_sources")
def test_historical_successor_checks_positive_then_each_real_mutation(tmp_path, fault):
    root = materialize_historical_guard_sources(tmp_path / "source")
    assert_historical_git_state(root)
    path = "frontend/app.js"
    target = root / path
    if fault == "source":
        target.write_bytes(target.read_bytes() + b"\n// unapproved substitution\n")
    elif fault == "index":
        oid = git(root, "hash-object", "-w", "--stdin", input_bytes=b"// substituted index\n").decode().strip()
        git(root, "update-index", "--cacheinfo", "100644", oid, path)
    elif fault == "missing":
        target.unlink()
    else:
        unknown = root / "backend" / "unapproved.py"
        unknown.write_text("# synthetic unapproved owner\n", "utf-8")
        if fault == "staged_unknown":
            git(root, "add", "--", "backend/unapproved.py")
    with pytest.raises((AssertionError, OSError)):
        assert_historical_git_state(root)
