"""Test-only seed gate regression; no canonical SQLite file is opened here."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from backend.adapters.outbound.persistence.migrations import (
    CANONICAL_SEED_SHA256,
    CANONICAL_SEED_SIZE,
    DatabaseEvidence,
    FileEvidence,
    SQLiteFileSetSnapshot,
    snapshot_sqlite_files,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from tests.integration import test_sqlite_runtime_real_gate as seed_gate


def _snapshot() -> SQLiteFileSetSnapshot:
    main = FileEvidence(True, CANONICAL_SEED_SIZE, 1, CANONICAL_SEED_SHA256, 1, 1)
    absent = FileEvidence(False, None, None, None, None, None)
    return SQLiteFileSetSnapshot(main, absent, absent, absent)


@pytest.mark.parametrize("invalid", ["missing", "size", "sha256"])
def test_seed_identity_is_checked_before_any_sqlite_open(
    monkeypatch: pytest.MonkeyPatch, invalid: str,
) -> None:
    snapshot = _snapshot()
    if invalid == "missing":
        main = replace(snapshot.main, exists=False)
    elif invalid == "size":
        main = replace(snapshot.main, size_bytes=0)
    else:
        main = replace(snapshot.main, sha256="0" * 64)
    monkeypatch.setattr(seed_gate, "snapshot_sqlite_files",
                        lambda path: replace(snapshot, main=main))

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("SQLite must not be reached before identity authentication")

    monkeypatch.setattr(seed_gate, "inspect_database", forbidden)
    monkeypatch.setattr(seed_gate, "connect_sqlite", forbidden)
    with pytest.raises(AssertionError):
        seed_gate.test_seed_gate_is_exact_and_read_only(Path("unused-seed.sqlite"))


@pytest.mark.parametrize("changed_sidecar", [None, "wal", "shm", "journal"])
def test_seed_gate_uses_immutable_closes_and_detects_sidecar_drift(
    monkeypatch: pytest.MonkeyPatch, changed_sidecar: str | None,
) -> None:
    before = _snapshot()
    events: list[str] = []

    def snapshot(path: Path) -> SQLiteFileSetSnapshot:
        events.append("snapshot")
        if changed_sidecar is not None and "close" in events:
            changed = FileEvidence(True, 1, 2, "f" * 64, 1, 2)
            return replace(before, **{changed_sidecar: changed})
        return before

    def inspect(path: Path, *, authenticate_seed: bool) -> DatabaseEvidence:
        assert events[0] == "snapshot"
        assert authenticate_seed is True
        events.append("inspect")
        return DatabaseEvidence(CANONICAL_SEED_SIZE, CANONICAL_SEED_SHA256,
                                98, 20, 7, 2, "ok", "ok", 0)

    class Connection:
        def execute(self, sql: str) -> None:
            assert sql == "CREATE TABLE forbidden_seed_write(id INTEGER)"
            events.append("write_rejected")
            raise sqlite3.OperationalError("readonly test double")

        def close(self) -> None:
            events.append("close")

    def connect(path: Path, *, readonly: bool, immutable: bool) -> Connection:
        assert events[:2] == ["snapshot", "inspect"]
        assert readonly is True
        assert immutable is True
        events.append("connect")
        return Connection()

    monkeypatch.setattr(seed_gate, "snapshot_sqlite_files", snapshot)
    monkeypatch.setattr(seed_gate, "inspect_database", inspect)
    monkeypatch.setattr(seed_gate, "connect_sqlite", connect)

    def forbidden_mutation(*args: object, **kwargs: object) -> None:
        pytest.fail("Seed gate must never provision or migrate a database")

    monkeypatch.setattr(seed_gate, "provision_runtime", forbidden_mutation)
    monkeypatch.setattr(seed_gate, "apply_migration", forbidden_mutation)
    if changed_sidecar is None:
        seed_gate.test_seed_gate_is_exact_and_read_only(Path("unused-seed.sqlite"))
    else:
        with pytest.raises(AssertionError):
            seed_gate.test_seed_gate_is_exact_and_read_only(Path("unused-seed.sqlite"))
    assert events.count("connect") == 1
    assert events.count("close") == 1
    assert "write_rejected" in events


def test_validated_reader_emits_immutable_uri_for_temporary_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert not tmp_path.resolve().is_relative_to(Path(__file__).resolve().parents[2])
    fixture = tmp_path / "temporary fixture #.sqlite"
    with closing(sqlite3.connect(fixture)) as writer:
        writer.execute("CREATE TABLE fixture(id INTEGER)")
        writer.commit()
    before = snapshot_sqlite_files(fixture)
    original_connect = sqlite3.connect
    locators: list[str] = []

    def capture(database: str, *, uri: bool) -> sqlite3.Connection:
        assert uri is True
        locators.append(database)
        return original_connect(database, uri=uri)

    monkeypatch.setattr(sqlite3, "connect", capture)
    with closing(connect_sqlite(fixture, readonly=True, immutable=True)) as reader:
        assert reader.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("INSERT INTO fixture VALUES (1)")
    assert locators == [fixture.as_uri() + "?mode=ro&immutable=1"]
    assert snapshot_sqlite_files(fixture) == before
