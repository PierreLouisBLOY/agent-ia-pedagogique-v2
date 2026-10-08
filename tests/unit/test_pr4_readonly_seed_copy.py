"""A read-only authenticated seed must yield a private writable runtime copy."""
import stat
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import provision_runtime
from tests.unit.test_sqlite_local_boundary import MIGRATION, _sha256, _synthetic_seed


def test_readonly_seed_preserves_attributes_and_provisions_distinct_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed = _synthetic_seed(tmp_path, monkeypatch)
    seed.chmod(stat.S_IREAD)
    before_hash = _sha256(seed)
    before_mode = seed.stat().st_mode
    root = (tmp_path / "data").resolve()
    runtime = root / "runtime.sqlite"
    try:
        report = provision_runtime(seed, runtime, MIGRATION, data_root=root)
        assert report.runtime_created
        assert report.journal_mode == "wal"
        assert report.runtime_permission_status == "PRIVATE_OWNER_ONLY"
        assert runtime.is_file() and runtime != seed
        assert tuple(root.glob("*.tmp")) == ()
        assert _sha256(seed) == before_hash
        assert seed.stat().st_mode == before_mode
    finally:
        seed.chmod(stat.S_IREAD | stat.S_IWRITE)
