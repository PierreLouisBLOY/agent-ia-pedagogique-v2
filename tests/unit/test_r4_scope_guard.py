import shutil

import pytest

from tests.support import r4_scope_guard as guard


@pytest.mark.usefixtures("historical_guard_sources")
def test_each_r4_source_mutation_is_rejected(tmp_path):
    from tests.support.r5_scope_guard import PATHS as R5_PATHS
    for path in set(guard.PATHS) | set(R5_PATHS):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(guard.ROOT / path, target)
    assert guard.violations(tmp_path) == []
    for path in guard.PATHS:
        target = tmp_path / path
        raw = target.read_bytes()
        target.write_bytes(raw + b"\n# unapproved mutation\n")
        assert not guard.exact(tmp_path, path), path
        target.write_bytes(raw)
    assert guard.violations(tmp_path, changed=set(guard.PATHS) | {"backend/modules/extra.py"})
    assert guard.violations(tmp_path, changed=set(guard.PATHS) - {guard.PATHS[0]})


def test_unlisted_historical_symbol_cannot_hide_in_r4_projection(tmp_path):
    path = "backend/adapters/inbound/api/server.py"
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    raw = (guard.ROOT / path).read_bytes()
    mutated = raw.replace(b"if size > 16384:", b"if size > 99999999:")
    assert mutated != raw
    target.write_bytes(mutated)
    assert guard.baseline_view(tmp_path, path) == mutated
    assert guard.outside_scope(path, mutated) != guard.outside_scope(path, guard.baseline(path))
