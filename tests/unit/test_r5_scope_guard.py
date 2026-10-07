from pathlib import Path

import pytest

from tests.support import r5_scope_guard as guard

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.usefixtures("historical_guard_sources")


def test_exact_successor_and_unknown_path():
    assert guard.violations(ROOT, changed=set(guard.PATHS)) == []
    assert guard.violations(ROOT, changed=set(guard.PATHS) | {"backend/extra.py"}) == ["R5_UNAPPROVED:backend/extra.py"]
    assert not guard.authenticated(expected="0" * 64)


@pytest.mark.parametrize("path", guard.PATHS)
def test_each_file_mutation_missing_and_wrong_index_rejected(tmp_path, path):
    destination = tmp_path / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not guard.exact(tmp_path, path)
    raw = (ROOT / path).read_bytes()
    destination.write_bytes(raw)
    assert guard.exact(tmp_path, path)
    assert guard.index_matches(tmp_path, path, raw)
    assert not guard.index_matches(tmp_path, path, raw + b"\n# not approved\n")
    destination.write_bytes(raw + b"\n# not approved\n")
    assert not guard.exact(tmp_path, path)


def test_old_unlisted_symbol_preserved_even_if_post_changed():
    path = "backend/modules/pedagogical_design/contracts/dto/conversation_draft.py"
    raw = (ROOT / path).read_bytes()
    mutation = raw.replace(b"R2-ASSESSMENT-SECTIONS-1.0", b"UNAPPROVED-OUTPUT-CONTRACT")
    assert guard.outside_scope(path, raw) == guard.outside_scope(path, guard.baseline(path))
    assert guard.outside_scope(path, mutation) != guard.outside_scope(path, guard.baseline(path))
