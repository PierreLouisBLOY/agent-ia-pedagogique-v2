from __future__ import annotations

import ast
import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.runtime_schema_inspection import (
    build_runtime_schema_inspection_inbound,
)
from backend.modules.local_provisioning.application.inspect_runtime_schema import (
    InspectRuntimeSchema,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def schema_file(tmp_path):
    path = tmp_path / "schema.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE parent(id TEXT PRIMARY KEY NOT NULL);
            CREATE TABLE child(id TEXT PRIMARY KEY NOT NULL,
                parent_id TEXT REFERENCES parent(id), amount INTEGER,
                doubled INTEGER GENERATED ALWAYS AS (amount*2) STORED);
            CREATE UNIQUE INDEX child_amount ON child(amount);
            CREATE VIEW current_child AS SELECT * FROM child WHERE amount IS NOT NULL;
            CREATE TRIGGER child_reject BEFORE INSERT ON child WHEN NEW.amount < 0
                BEGIN SELECT RAISE(ABORT, 'NEGATIVE'); END;
        """)
    return path


def target(path):
    return Read15RuntimeTarget(path, path.parent, hashlib.sha256(path.read_bytes()).hexdigest())


def test_full_schema_generated_columns_fk_indexes_view_trigger_and_no_writes(schema_file):
    raw = schema_file.read_bytes()
    stat = schema_file.stat()
    inbound = build_runtime_schema_inspection_inbound(target(schema_file))
    result = inbound.inspect()
    assert {(o.kind, o.name) for o in result.objects} >= {
        ("table", "parent"), ("table", "child"), ("view", "current_child"),
        ("trigger", "child_reject"), ("index", "child_amount"),
    }
    child = next(table for table in result.tables if table.name == "child")
    assert child.columns[-1][-1] == 3
    assert child.foreign_keys[0][2:5] == ("parent", "parent_id", "id")
    assert any(index.name == "child_amount" and index.columns for index in result.indexes)
    assert result.integrity == result.quick_check == ("ok",)
    assert result.foreign_key_violations == 0
    assert inbound.inspect().schema_sha256 == result.schema_sha256
    assert schema_file.read_bytes() == raw
    assert schema_file.stat().st_mtime_ns == stat.st_mtime_ns
    assert list(schema_file.parent.iterdir()) == [schema_file]


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_sidecar_presence_refused_before_opening(schema_file, suffix, monkeypatch):
    inbound = build_runtime_schema_inspection_inbound(target(schema_file))
    schema_file.with_name(schema_file.name + suffix).write_bytes(b"synthetic sidecar")
    def forbidden(*args, **kwargs):
        pytest.fail("SQLite must not be opened")
    monkeypatch.setattr(
        "backend.adapters.outbound.persistence.runtime_schema_inspection.connect_sqlite",
        forbidden,
    )
    with pytest.raises(ValueError, match="SIDECAR_PRESENT"):
        inbound.inspect()


def test_substitution_after_composition_refused(schema_file):
    inbound = build_runtime_schema_inspection_inbound(target(schema_file))
    schema_file.write_bytes(b"synthetic substitution")
    with pytest.raises(ValueError, match="SOURCE_MISMATCH"):
        inbound.inspect()


def test_concurrent_source_substitution_after_snapshot_refused(schema_file, monkeypatch):
    import backend.adapters.outbound.persistence.runtime_schema_inspection as adapter
    original = adapter.SQLiteRuntimeSchemaInspectionAdapter._capture
    captures = 0
    def changed(self):
        nonlocal captures
        captures += 1
        if captures == 2:
            schema_file.write_bytes(b"synthetic concurrent change")
        return original(self)
    monkeypatch.setattr(adapter.SQLiteRuntimeSchemaInspectionAdapter, "_capture", changed)
    with pytest.raises(ValueError, match="SOURCE_MISMATCH"):
        build_runtime_schema_inspection_inbound(target(schema_file)).inspect()


@pytest.mark.parametrize("field,value,error", [
    ("source_sha256", "0"*64, "SOURCE_MISMATCH"),
    ("schema_sha256", "invalid", "BOUNDS"),
    ("objects", (), "BOUNDS"),
    ("connection_flags", (("query_only", 0),), "READ_ONLY_REQUIRED"),
    ("absent_sidecars", (), "READ_ONLY_REQUIRED"),
])
def test_application_rejects_false_gateway_attestation(schema_file, field, value, error):
    current = build_runtime_schema_inspection_inbound(target(schema_file)).inspect()
    class Gateway:
        def inspect_schema(self):
            return replace(current, **{field: value})
    with pytest.raises(ValueError, match=error):
        InspectRuntimeSchema(Gateway(), current.source_sha256).execute()


def test_schema_change_is_visible_and_old_identity_refused(schema_file):
    before = target(schema_file)
    result = build_runtime_schema_inspection_inbound(before).inspect()
    with sqlite3.connect(schema_file) as connection:
        connection.execute("DROP TRIGGER child_reject")
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        build_runtime_schema_inspection_inbound(before)
    current = build_runtime_schema_inspection_inbound(target(schema_file)).inspect()
    assert current.schema_sha256 != result.schema_sha256
    assert not any(obj.kind == "trigger" for obj in current.objects)


def test_reader_surface_has_no_sql_path_or_mutation_parameter():
    from inspect import signature

    from backend.adapters.inbound.application.runtime_schema_inspection import (
        RuntimeSchemaInspectionInbound,
    )
    assert tuple(signature(RuntimeSchemaInspectionInbound.inspect).parameters) == ("self",)
    for relative in (
        "backend/modules/local_provisioning/application/inspect_runtime_schema.py",
        "backend/modules/local_provisioning/application/runtime_schema_snapshot.py",
        "backend/modules/local_provisioning/ports/runtime_schema_inspection.py",
        "backend/adapters/inbound/application/runtime_schema_inspection.py",
    ):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any(m and (m == "sqlite3" or m.startswith(
            ("backend.infrastructure", "backend.adapters.outbound", "openai", "httpx")
        )) for m in modules)

def test_sidecar_evidence_is_read_without_sqlite_or_mutation(schema_file, monkeypatch):
    inbound = build_runtime_schema_inspection_inbound(target(schema_file))
    side = schema_file.with_name(schema_file.name + "-wal")
    side.write_bytes(b"synthetic nonempty WAL")
    def forbidden(*args, **kwargs):
        pytest.fail("SQLite must not be opened for file evidence")
    monkeypatch.setattr(
        "backend.adapters.outbound.persistence.runtime_schema_inspection.connect_sqlite",
        forbidden,
    )
    result = inbound.inspect_files()
    assert tuple(row.suffix for row in result) == ("", "-wal", "-shm", "-journal")
    assert result[0].sha256 == hashlib.sha256(schema_file.read_bytes()).hexdigest()
    assert result[1].exists and result[1].size == len(b"synthetic nonempty WAL")
    assert result[1].sha256 == hashlib.sha256(side.read_bytes()).hexdigest()
    assert not result[2].exists and not result[3].exists
    assert side.read_bytes() == b"synthetic nonempty WAL"

def test_passive_empty_wal_and_standard_shm_are_preserved_for_immutable_read(schema_file):
    wal = schema_file.with_name(schema_file.name + "-wal")
    shm = schema_file.with_name(schema_file.name + "-shm")
    wal.write_bytes(b"")
    shm.write_bytes(b"synthetic passive SHM".ljust(32768, b"0"))
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
              for p in schema_file.parent.iterdir()}
    result = build_runtime_schema_inspection_inbound(target(schema_file)).inspect()
    assert result.absent_sidecars == ("-journal",)
    assert result.file_set[1].exists and result.file_set[1].size == 0
    assert result.file_set[2].exists and result.file_set[2].size == 32768
    assert result.integrity == ("ok",)
    assert before == {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                      for p in schema_file.parent.iterdir()}


def test_sidecar_change_during_reader_is_refused(schema_file, monkeypatch):
    import backend.adapters.outbound.persistence.runtime_schema_inspection as adapter
    wal = schema_file.with_name(schema_file.name + "-wal")
    wal.write_bytes(b"")
    inbound = build_runtime_schema_inspection_inbound(target(schema_file))
    original = adapter.SQLiteRuntimeSchemaInspectionAdapter._capture
    calls = 0
    def changed(self):
        nonlocal calls
        calls += 1
        if calls == 2:
            wal.write_bytes(b"new concurrent WAL frame")
        return original(self)
    monkeypatch.setattr(adapter.SQLiteRuntimeSchemaInspectionAdapter, "_capture", changed)
    with pytest.raises(ValueError, match="SIDECAR_PRESENT"):
        inbound.inspect()
