from pathlib import Path

import pytest

from tests.support import r5_worker_guard as guard

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.usefixtures("historical_guard_sources")


def test_worker_guard_closed_current_and_predecessor():
    assert guard.violations(ROOT) == []
    assert not guard.authenticated(expected="0" * 64)
    assert not guard.exact(ROOT, "backend/unapproved.py")
    for path in guard.PRE:
        assert guard.outside_scope(path, (ROOT / path).read_bytes()) == guard.outside_scope(path, guard.baseline(path))


@pytest.mark.parametrize("path", guard.PATHS)
def test_each_worker_source_missing_mutated_and_index_substitution_rejected(tmp_path, path):
    dest = tmp_path / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    assert not guard.exact(tmp_path, path)
    raw = (ROOT / path).read_bytes()
    dest.write_bytes(raw)
    assert guard.exact(tmp_path, path)
    assert guard.index_matches(tmp_path, path, raw)
    assert not guard.index_matches(tmp_path, path, raw + b"\n# mutation\n")
    dest.write_bytes(raw + b"\n# mutation\n")
    assert not guard.exact(tmp_path, path)


def test_untouched_worker_and_mapping_symbols_are_not_exempted():
    path = "backend/infrastructure/composition/bootstrap/conversation_worker.py"
    raw = (ROOT / path).read_bytes()
    mutant = raw.replace(b"size <= FRAME_LIMIT", b"size <= FRAME_LIMIT * 100")
    assert mutant != raw
    assert guard.outside_scope(path, mutant) != guard.outside_scope(path, raw)
