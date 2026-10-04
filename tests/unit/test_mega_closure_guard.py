"""The closure delta remains pinned; no unknown owner is accepted."""
from pathlib import Path

import pytest

from tests.support import r6_scope_guard as guard

ROOT = Path(__file__).resolve().parents[2]
OWNERS = (
    "backend/adapters/outbound/review/p0_review.py",
    "backend/adapters/outbound/review/openai/adapter.py",
    "tests/unit/test_mega_closure_review.py",
    "docs/development/MEGA_LOT_LOCAL_CLOSURE_REVIEW.md",
)


@pytest.mark.parametrize("owner", OWNERS)
def test_active_closure_owner_is_pinned_and_mutation_rejected(tmp_path, owner):
    for path in (*guard.PATHS, guard.SELF, guard.MANIFEST):
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / path).read_bytes())
    assert guard.violations(tmp_path) == []
    raw = (ROOT / owner).read_bytes()
    assert guard.index_matches(tmp_path, owner, raw)
    assert not guard.index_matches(tmp_path, owner, raw + b"\n# changed\n")
    (tmp_path / owner).write_bytes(raw + b"\n# changed\n")
    assert guard.violations(tmp_path) == ["R6_IDENTITY:" + owner]
