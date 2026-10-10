"""Persistence, Application and Windows cycle qualification on synthetic fixtures."""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

import backend.adapters.outbound.persistence.sql_successor as adapter
from backend.adapters.outbound.persistence.sql_successor import (
    definitions,
    fingerprints,
    install_reviewed_successor,
)
from backend.adapters.outbound.persistence.sql_successor_sql import READ
from backend.adapters.outbound.persistence.sql_successor_stability import pinned_windows_paths
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.runtime_schema_inspection import (
    build_runtime_schema_inspection_inbound,
)
from backend.infrastructure.composition.factories.sql_successor import build_sql_successor_inbound
from backend.modules.local_provisioning.application.sql_successor import (
    CurrentVersionResolution,
    ResolveSuccessorCurrentVersion,
    SQLSuccessorBinding,
    SQLSuccessorRequest,
)
from tests.support.sql_successor_fixture import BASE_DDL


def version(c, identifier, *, status="DRAFT", created="2024", vf=None, vt=None, actor=None):
    c.execute(
        "INSERT INTO resource_version(id,resource_id,title,body,lifecycle_status,created_at,"
        "valid_from,valid_to,created_by_actor_id) VALUES(?, 'r1','Synthetic','Synthetic',?,?,?,?,?)",
        (identifier, status, created, vf, vt, actor),
    )


@pytest.fixture
def source(tmp_path):
    directory = tmp_path / "source"
    directory.mkdir()
    path = directory / "synthetic.sqlite"
    c = sqlite3.connect(path)
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("BEGIN")
    for sql in BASE_DDL:
        c.execute(sql)
    c.execute("PRAGMA foreign_keys=ON")
    c.execute(
        "INSERT INTO actor(id,actor_type,display_name) VALUES('actor:test','SYSTEM','Synthetic')"
    )
    for n in ("n1", "n2"):
        c.execute("INSERT INTO notion(id,canonical_label) VALUES(?, 'Synthetic')", (n,))
    for r in ("r1", "r2"):
        c.execute(
            "INSERT INTO resource(id,resource_type,canonical_title) VALUES(?, 'COURSE', 'Synthetic')",
            (r,),
        )
    c.execute(
        "INSERT INTO official_framework(id,framework_type,title) VALUES('fw','REFERENTIEL','Synthetic')"
    )
    for v in ("fv1", "fv2"):
        c.execute("INSERT INTO official_framework_version(id,framework_id) VALUES(?, 'fw')", (v,))
    for i, v, p in (("p1", "fv1", None), ("ch1", "fv1", "p1"), ("p2", "fv2", None)):
        c.execute(
            "INSERT INTO official_framework_element(id,framework_version_id,parent_element_id,"
            "element_type,official_label) VALUES(?,?,?, 'OTHER', 'Synthetic')",
            (i, v, p),
        )
    for code, reflex in (("strict", 0), ("reflex", 1)):
        c.execute(
            "INSERT INTO pedagogical_relation_type(code,label,allows_reflexive) VALUES(?, 'Synthetic',?)",
            (code, reflex),
        )
    c.execute(
        "INSERT INTO pedagogical_relation(id,source_notion_id,target_notion_id,relation_type_code) VALUES('rel1','n1','n2','strict')"
    )
    c.execute(
        "INSERT INTO pedagogical_relation(id,source_notion_id,target_notion_id,relation_type_code) VALUES('rel2','n1','n1','reflex')"
    )
    c.execute(
        "INSERT INTO institutional_attachment(id,notion_id,framework_element_id,attachment_type,origin_type) VALUES('att1','n1','p1','EXPLICIT','OFFICIAL')"
    )
    version(c, "vpub", status="PUBLISHED", actor="actor:test")
    version(c, "vdraft", created="2025")
    c.commit()
    c.close()
    return path


def target(path):
    return Read15RuntimeTarget(path, path.parent, hashlib.sha256(path.read_bytes()).hexdigest())


def binding(path):
    s = build_runtime_schema_inspection_inbound(target(path)).inspect()
    return SQLSuccessorBinding(
        "a" * 64,
        "b" * 64,
        "c" * 64,
        hashlib.sha256(json.dumps(asdict(s), sort_keys=True).encode()).hexdigest(),
        "d" * 64,
        s,
    )


def request(b):
    return SQLSuccessorRequest(b.plan_sha256, b.decision_sha256, b.review_sha256)


def database(source):
    b = binding(source)
    c = sqlite3.connect(source, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    install_reviewed_successor(c, b.snapshot)
    return c


@pytest.mark.parametrize(
    "sql,params",
    [
        ("UPDATE resource_version SET " + column + "=? WHERE id='vpub'", (value,))
        for column, value in {
            "id": "new",
            "resource_id": "r2",
            "version_number": "2",
            "previous_version_id": "vdraft",
            "title": "changed",
            "summary": "changed",
            "body": "changed",
            "validation_status": "VALIDATED",
            "published_at": "2025",
            "valid_from": "2020",
            "valid_to": "2999",
            "created_at": "2025",
            "created_by_actor_id": None,
        }.items()
    ]
    + [
        ("UPDATE resource_version SET lifecycle_status=? WHERE id='vpub'", (s,))
        for s in ("DRAFT", "REVIEW", "VALIDATED", "DEPRECATED", "REJECTED", "WITHDRAWN")
    ]
    + [
        (
            "UPDATE resource_version SET lifecycle_status='ARCHIVED',body='change' WHERE id='vpub'",
            (),
        ),
        ("DELETE FROM actor WHERE id='actor:test'", ()),
        ("DELETE FROM _pr4_published_version_seal", ()),
        ("UPDATE _pr4_published_version_seal SET resource_version_id='vdraft'", ()),
        ("INSERT INTO _pr4_published_version_seal VALUES('vdraft')", ()),
        ("DELETE FROM resource_version WHERE id='vpub'", ()),
        (
            "INSERT INTO resource_version(resource_id,title,lifecycle_status) VALUES('r1','Synthetic','PUBLISHED')",
            (),
        ),
        ("UPDATE resource_version SET id=NULL,lifecycle_status='PUBLISHED' WHERE id='vdraft'", ()),
        ("UPDATE pedagogical_relation SET target_notion_id='n1' WHERE id='rel1'", ()),
        (
            "INSERT INTO pedagogical_relation(id,source_notion_id,target_notion_id,relation_type_code) VALUES('bad','n1','n1','strict')",
            (),
        ),
        ("UPDATE pedagogical_relation_type SET allows_reflexive=0 WHERE code='reflex'", ()),
        (
            "INSERT OR REPLACE INTO pedagogical_relation_type(code,label,allows_reflexive) VALUES('reflex','Changed',0)",
            (),
        ),
        ("UPDATE institutional_attachment SET origin_type='AI_INFERENCE' WHERE id='att1'", ()),
        (
            "INSERT INTO institutional_attachment(id,notion_id,framework_element_id,attachment_type,origin_type) VALUES('bad','n2','p1','EXPLICIT','AI_INFERENCE')",
            (),
        ),
        ("UPDATE official_framework_element SET framework_version_id='fv2' WHERE id='ch1'", ()),
        ("UPDATE official_framework_element SET framework_version_id='fv2' WHERE id='p1'", ()),
        (
            "INSERT INTO official_framework_element(id,framework_version_id,parent_element_id,element_type,official_label) VALUES('bad','fv2','p1','OTHER','Synthetic')",
            (),
        ),
        (
            "INSERT OR REPLACE INTO official_framework_element(id,framework_version_id,element_type,official_label) VALUES('p1','fv2','OTHER','Synthetic')",
            (),
        ),
        ("INSERT INTO notion(canonical_label) VALUES('Synthetic')", ()),
        ("UPDATE notion SET id=NULL WHERE id='n2'", ()),
    ],
)
def test_refusals_preserve_all_rows(source, sql, params):
    c = database(source)
    tables = tuple(
        row[0]
        for row in c.execute("SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name")
    )
    before = fingerprints(c, tables)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(sql, params)
    assert fingerprints(c, tables) == before
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    c.close()


@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize(
    "sql",
    [
        *[
            f"INSERT OR {mode} INTO _pr4_published_version_seal VALUES('vpub')"
            for mode in ("REPLACE", "IGNORE", "ABORT", "FAIL", "ROLLBACK")
        ],
        *[
            f"INSERT OR {mode} INTO resource_version(id,resource_id,title) VALUES('vpub','r1','Changed')"
            for mode in ("REPLACE", "IGNORE", "ABORT", "FAIL", "ROLLBACK")
        ],
        "INSERT INTO resource_version(id,resource_id,title) VALUES('vpub','r1','Changed') ON CONFLICT(id) DO UPDATE SET title=excluded.title",
        "INSERT INTO _pr4_published_version_seal VALUES('vpub') ON CONFLICT(resource_version_id) DO UPDATE SET resource_version_id='vdraft'",
        "UPDATE OR REPLACE resource_version SET id='vpub' WHERE id='vdraft'",
        "INSERT OR REPLACE INTO resource_version(rowid,id,resource_id,title) SELECT rowid,'different','r1','Changed' FROM resource_version WHERE id='vpub'",
    ],
)
def test_conflicts_do_not_bypass_seal(source, recursive, sql):
    c = database(source)
    c.execute(f"PRAGMA recursive_triggers={recursive}")
    before = fingerprints(c, ("resource_version", "_pr4_published_version_seal"))
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(sql)
    assert fingerprints(c, ("resource_version", "_pr4_published_version_seal")) == before
    c.close()


def test_positive_paths_and_old_objects_preserved(source):
    b = binding(source)
    c = sqlite3.connect(source, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    old = definitions(c)
    rows = fingerprints(c, tuple(t.name for t in b.snapshot.tables))
    assert install_reviewed_successor(c, b.snapshot) == rows
    lookup = {r[1]: r for r in definitions(c)}
    assert all(lookup[r[1]] == r for r in old if r[1] != "v_current_resource_version")
    c.execute("UPDATE resource_version SET lifecycle_status='PUBLISHED' WHERE id='vdraft'")
    c.execute("UPDATE resource_version SET lifecycle_status=lifecycle_status WHERE id='vpub'")
    c.execute("UPDATE resource_version SET lifecycle_status='ARCHIVED' WHERE id='vpub'")
    assert c.execute("SELECT COUNT(*) FROM _pr4_published_version_seal").fetchone() == (2,)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("UPDATE resource_version SET summary='changed' WHERE id='vpub'")
    version(c, "child")
    c.execute("UPDATE resource_version SET previous_version_id='vpub' WHERE id='child'")
    c.execute("INSERT INTO notion(id,canonical_label) VALUES('valid','Synthetic')")
    c.execute("UPDATE official_framework_element SET parent_element_id=NULL WHERE id='ch1'")
    c.close()


@pytest.mark.parametrize(
    "guard,sql",
    [
        (
            "pr4_relation_reflexive_insert",
            "INSERT INTO pedagogical_relation(id,source_notion_id,target_notion_id,relation_type_code) VALUES('bad','n2','n2','strict')",
        ),
        (
            "pr4_relation_reflexive_update",
            "UPDATE pedagogical_relation SET target_notion_id='n1' WHERE id='rel1'",
        ),
        (
            "pr4_relation_type_reflexive_insert",
            "INSERT OR REPLACE INTO pedagogical_relation_type(code,label,allows_reflexive) VALUES('reflex','Changed',0)",
        ),
        (
            "pr4_relation_type_reflexive_update",
            "UPDATE pedagogical_relation_type SET allows_reflexive=0 WHERE code='reflex'",
        ),
        (
            "pr4_attachment_origin_insert",
            "INSERT INTO institutional_attachment(id,notion_id,framework_element_id,attachment_type,origin_type) VALUES('bad','n2','p1','EXPLICIT','AI_INFERENCE')",
        ),
        (
            "pr4_attachment_origin_update",
            "UPDATE institutional_attachment SET origin_type='AI_INFERENCE' WHERE id='att1'",
        ),
        (
            "pr4_framework_parent_insert",
            "INSERT INTO official_framework_element(id,framework_version_id,parent_element_id,element_type,official_label) VALUES('bad','fv2','p1','OTHER','Synthetic')",
        ),
        (
            "pr4_framework_parent_update",
            "UPDATE official_framework_element SET framework_version_id='fv2' WHERE id='ch1'",
        ),
        ("pr4_notion_id_insert", "INSERT INTO notion(canonical_label) VALUES('Synthetic')"),
        ("pr4_notion_id_update", "UPDATE notion SET id=NULL WHERE id='n2'"),
        ("pr4_seal_insert", "INSERT OR IGNORE INTO _pr4_published_version_seal VALUES('vpub')"),
        (
            "pr4_seal_update",
            "UPDATE _pr4_published_version_seal SET resource_version_id=resource_version_id",
        ),
        ("pr4_seal_delete", "DELETE FROM _pr4_published_version_seal"),
        (
            "pr4_version_sealed_insert",
            "INSERT OR IGNORE INTO resource_version(id,resource_id,title) VALUES('vpub','r1','Changed')",
        ),
        (
            "pr4_version_sealed_update",
            "UPDATE resource_version SET summary='changed' WHERE id='vpub'",
        ),
        ("pr4_version_sealed_delete", "DELETE FROM resource_version WHERE id='vpub'"),
        (
            "pr4_version_publish_insert",
            "INSERT INTO resource_version(id,resource_id,title,lifecycle_status) VALUES('newpub','r1','Synthetic','PUBLISHED')",
        ),
        (
            "pr4_version_publish_update",
            "UPDATE resource_version SET lifecycle_status='PUBLISHED' WHERE id='vdraft'",
        ),
    ],
)
def test_each_trigger_mutation_has_isolated_counterexample(source, guard, sql):
    c = database(source)
    # Historical constraints stay present. Where they independently protect the
    # same effect, first prove the mutation in the schema, then isolate it only
    # inside this synthetic counterexample (never in production).
    c.execute("DROP TRIGGER " + guard)
    assert not any(row[1] == guard for row in definitions(c))
    if guard == "pr4_relation_reflexive_insert":
        c.execute("DROP TRIGGER trg_pedagogical_relation_reflexive_guard")
    if guard == "pr4_framework_parent_insert":
        c.execute("DROP TRIGGER trg_framework_element_parent_same_version_insert")
    if guard == "pr4_framework_parent_update":
        c.execute("DROP TRIGGER trg_framework_element_parent_same_version_update")
    if guard == "pr4_version_sealed_update":
        c.execute("DROP TRIGGER trg_resource_version_immutable_business_fields")
    if guard == "pr4_attachment_origin_insert":
        c.execute("DROP TRIGGER trg_official_attachment_requires_official_origin")
    if guard in ("pr4_version_sealed_delete", "pr4_relation_type_reflexive_insert"):
        c.execute("PRAGMA foreign_keys=OFF")
    if guard == "pr4_notion_id_update":
        c.execute("INSERT INTO notion(id,canonical_label) VALUES('free','Synthetic')")
        sql = sql.replace("id='n2'", "id='free'")
    c.execute(sql)
    if guard.startswith("pr4_version_publish_"):
        ref = "newpub" if guard.endswith("insert") else "vdraft"
        assert (
            c.execute(
                "SELECT 1 FROM _pr4_published_version_seal WHERE resource_version_id=?", (ref,)
            ).fetchone()
            is None
        )
    c.close()


@pytest.mark.parametrize(
    "versions,expected",
    [
        ([], ("ABSENT", 0, None)),
        ([("v1", "PUBLISHED", "2024", None, None)], ("EXACT", 1, "v1")),
        ([("v1", "DRAFT", "2024", None, None)], ("ABSENT", 0, None)),
        (
            [("v1", "PUBLISHED", "2024", None, None), ("v2", "PUBLISHED", "2025", None, None)],
            ("EXACT", 1, "v2"),
        ),
        (
            [("v1", "PUBLISHED", "2024", None, None), ("v2", "PUBLISHED", "2024", None, None)],
            ("AMBIGUOUS_CURRENT_VERSION", 2, None),
        ),
        (
            [("v2", "PUBLISHED", "2024", None, None), ("v1", "PUBLISHED", "2024", None, None)],
            ("AMBIGUOUS_CURRENT_VERSION", 2, None),
        ),
        (
            [("v1", "PUBLISHED", "2024", None, None), ("v2", "PUBLISHED", "2025", None, "2000")],
            ("EXACT", 1, "v1"),
        ),
        (
            [("v1", "PUBLISHED", "2024", None, None), ("v2", "PUBLISHED", "2025", "2999", None)],
            ("EXACT", 1, "v1"),
        ),
        (
            [("v1", "PUBLISHED", "2024", None, None), ("v2", "DRAFT", "2025", None, None)],
            ("EXACT", 1, "v1"),
        ),
        ([("v1", "ARCHIVED", "2024", None, None)], ("ABSENT", 0, None)),
        ([("v1", "PUBLISHED", "2024", "2000", "2999")], ("EXACT", 1, "v1")),
        (
            [
                ("v1", "PUBLISHED", "2024", None, None),
                ("v2", "PUBLISHED", "2024", None, None),
                ("v3", "PUBLISHED", "2024", None, None),
            ],
            ("AMBIGUOUS_CURRENT_VERSION", 3, None),
        ),
    ],
)
def test_single_statement_current_diagnostic(source, versions, expected):
    c = sqlite3.connect(source, isolation_level=None)
    c.execute("DELETE FROM resource_version")
    for i, status, created, vf, vt in versions:
        version(c, i, status=status, created=created, vf=vf, vt=vt)
    c.close()
    b = binding(source)
    c = sqlite3.connect(source, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    old_ids = [r[0] for r in c.execute("SELECT id FROM v_current_resource_version")]
    install_reviewed_successor(c, b.snapshot)
    assert c.execute(READ, ("r1",)).fetchone() == expected
    assert len(old_ids) == expected[1]
    assert [r[0] for r in c.execute("SELECT id FROM v_current_resource_version")] == (
        [expected[2]] if expected[1] == 1 else []
    )
    assert c.execute(READ, ("unknown",)).fetchone() == ("ABSENT", 0, None)
    assert [r[0] for r in c.execute("SELECT * FROM v_current_resource_version").description] == [
        r[1] for t in b.snapshot.tables if t.name == "resource_version" for r in t.columns
    ]
    c.close()


def test_sql05_single_read_survives_concurrent_writer(source):
    c = database(source)
    c.close()
    reader = sqlite3.connect(source)
    reader.execute("PRAGMA journal_mode=WAL")
    reader.execute("BEGIN")
    assert reader.execute(READ, ("r1",)).fetchone() == ("EXACT", 1, "vpub")
    with sqlite3.connect(source) as writer:
        version(writer, "tie", status="PUBLISHED")
    writer.close()
    assert reader.execute(READ, ("r1",)).fetchone() == ("EXACT", 1, "vpub")
    reader.rollback()
    assert reader.execute(READ, ("r1",)).fetchone() == ("AMBIGUOUS_CURRENT_VERSION", 2, None)
    reader.close()


def test_transaction_error_rolls_back_all_ddl_and_rows(source, monkeypatch):
    b = binding(source)
    c = sqlite3.connect(source, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    old = definitions(c)
    before = fingerprints(c, tuple(t.name for t in b.snapshot.tables))
    original = adapter._integrity

    def fail(conn):
        original(conn)
        raise ValueError("INJECTED_POSTCONDITION")

    monkeypatch.setattr(adapter, "_integrity", fail)
    with pytest.raises(ValueError, match="INJECTED_POSTCONDITION"):
        install_reviewed_successor(c, b.snapshot)
    assert (
        definitions(c) == old
        and fingerprints(c, tuple(t.name for t in b.snapshot.tables)) == before
    )
    c.close()


@pytest.mark.parametrize("field", ("DDL", "READ", "PRECONDITIONS"))
def test_sql_bytes_substitution_rejected(source, monkeypatch, field):
    monkeypatch.setattr(adapter, field, getattr(adapter, field) + "\n")
    c = sqlite3.connect(source, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(ValueError, match="SQL_SUBSTITUTION"):
        install_reviewed_successor(c, binding(source).snapshot)
    c.close()


def test_closed_cycle_application_and_idempotence(source, tmp_path, monkeypatch):
    b = binding(source)
    root = tmp_path / "successor"
    raw = source.read_bytes()
    inbound = build_sql_successor_inbound(target(source), root, b)
    calls = []
    original = adapter.publish_pinned_fresh

    def publish(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "publish_pinned_fresh", publish)
    first = inbound.apply(request(b))
    assert first.state == "APPLIED" and len(calls) == 1
    assert first.backup_sha256 == b.snapshot.source_sha256
    assert source.read_bytes() == raw and (root / "before-sql-successor.sqlite").read_bytes() == raw
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()}
    assert inbound.apply(request(b)).state == "ALREADY_APPLIED"
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()} == before
    assert len(calls) == 1 and len(list(root.glob("restore-control-*.sqlite"))) == 1
    assert inbound.resolve_current("r1") == CurrentVersionResolution("EXACT", 1, "vpub")


@pytest.mark.parametrize("mutation", ("source", "binding", "root", "backup", "final", "receipt"))
def test_cycle_substitution_or_collision_refused(source, tmp_path, mutation):
    b = binding(source)
    root = tmp_path / "successor"
    inbound = build_sql_successor_inbound(target(source), root, b)
    if mutation in ("backup", "final", "receipt"):
        inbound.apply(request(b))
        names = {
            "backup": "before-sql-successor.sqlite",
            "final": "runtime-copy.sqlite",
            "receipt": "applied-receipt.json",
        }
        (root / names[mutation]).write_bytes(b"substitution")
    elif mutation == "root":
        root.mkdir()
    elif mutation == "source":
        source.write_bytes(b"substitution")
    else:
        with pytest.raises(ValueError, match="REQUEST_MISMATCH"):
            inbound.apply(replace(request(b), plan_sha256="0" * 64))
        assert not root.exists()
        return
    with pytest.raises((ValueError, sqlite3.DatabaseError, json.JSONDecodeError)):
        inbound.apply(request(b))


@pytest.mark.parametrize(
    "operation",
    ("write_main", "write_wal", "write_shm", "replace", "rename_parent", "sqlite_writer"),
)
def test_windows_stability_rejects_real_child_process(source, operation):
    wal = Path(str(source) + "-wal")
    shm = Path(str(source) + "-shm")
    wal.write_bytes(b"")
    shm.write_bytes(b"S" * 32768)
    code = {
        "write_main": "p.write_bytes(b'change')",
        "write_wal": "Path(str(p)+'-wal').write_bytes(b'change')",
        "write_shm": "Path(str(p)+'-shm').write_bytes(b'change')",
        "replace": "q=p.parent/'replacement';q.write_bytes(b'change');os.replace(q,p)",
        "rename_parent": "p.parent.rename(p.parent.with_name('replaced'))",
        "sqlite_writer": "c=sqlite3.connect(p);c.execute(\"INSERT INTO notion(id,canonical_label) VALUES('child','Synthetic')\");c.commit();c.close()",
    }[operation]
    before = (source.read_bytes(), wal.read_bytes(), shm.read_bytes())
    with pinned_windows_paths(root=source.parent, files=(source, wal, shm)):
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path;import sys,os,sqlite3;p=Path(sys.argv[1]);" + code,
                str(source),
            ],
            capture_output=True,
        )
        assert child.returncode != 0
        assert b"PermissionError" in child.stderr or b"OperationalError" in child.stderr
    assert (source.read_bytes(), wal.read_bytes(), shm.read_bytes()) == before


def test_existing_writer_blocks_before_any_destination(source, tmp_path):
    b = binding(source)
    inbound = build_sql_successor_inbound(target(source), tmp_path / "successor", b)
    writer = source.open("r+b")
    try:
        with pytest.raises(ValueError, match="SOURCE_WRITER_PRESENT"):
            inbound.apply(request(b))
        assert not (tmp_path / "successor").exists()
    finally:
        writer.close()


def test_fresh_collision_is_preserved_without_receipt(source, tmp_path, monkeypatch):
    b = binding(source)
    root = tmp_path / "successor"
    original = adapter.publish_pinned_fresh

    def collision(src, dst, **kwargs):
        dst.write_bytes(b"concurrent independent occupant")
        return original(src, dst, **kwargs)

    monkeypatch.setattr(adapter, "publish_pinned_fresh", collision)
    with pytest.raises(RuntimeError):
        build_sql_successor_inbound(target(source), root, b).apply(request(b))
    assert (root / "runtime-copy.sqlite").read_bytes() == b"concurrent independent occupant"
    assert not (root / "applied-receipt.json").exists()
    assert (root / "before-sql-successor.sqlite").read_bytes() == source.read_bytes()


@pytest.mark.parametrize(
    "value",
    [
        CurrentVersionResolution("EXACT", 2, "vpub"),
        CurrentVersionResolution("ABSENT", 0, "vpub"),
        CurrentVersionResolution("AMBIGUOUS_CURRENT_VERSION", 2, "vpub"),
    ],
)
def test_application_rejects_false_diagnostic(value):
    class Gateway:
        def resolve_current(self, ref):
            return value

    with pytest.raises(ValueError, match="CURRENT_DIAGNOSTIC"):
        ResolveSuccessorCurrentVersion(Gateway()).execute("r1")


def test_maintenance_has_no_agent_http_or_free_sql_path():
    from inspect import signature

    from backend.adapters.inbound.application.sql_successor import SQLSuccessorInbound

    assert tuple(signature(SQLSuccessorInbound.apply).parameters) == ("self", "request")
    assert set(SQLSuccessorRequest.__dataclass_fields__) == {
        "plan_sha256",
        "decision_sha256",
        "review_sha256",
    }
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "backend/modules/local_provisioning/application/sql_successor.py",
        "backend/adapters/inbound/application/sql_successor.py",
    ):
        tree = ast.parse((root / relative).read_text())
        names = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        names += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any(
            n
            and n.startswith(
                ("sqlite3", "pathlib", "backend.infrastructure", "backend.adapters.outbound")
            )
            for n in names
        )
    for path in list((root / "backend/adapters/inbound/api").rglob("*.py")) + list(
        (root / "backend/adapters/inbound/agent_tools").rglob("*.py")
    ):
        assert "sql_successor" not in path.read_text()


@pytest.mark.parametrize("effect", ("journal", "backup_bytes", "working_bytes"))
def test_concurrent_change_blocks_publication_and_keeps_history(
    source, tmp_path, monkeypatch, effect
):
    b = binding(source)
    root = tmp_path / "successor"
    original = adapter._Session.migrate_and_check

    def changed(session):
        original(session)
        if effect == "journal":
            Path(str(source) + "-journal").write_bytes(b"independent journal")
        elif effect == "backup_bytes":
            # An attempted write to the pinned backup must fail under Windows.
            with pytest.raises(PermissionError):
                (root / "before-sql-successor.sqlite").write_bytes(b"changed")
            raise ValueError("INJECTED_BACKUP_WRITER_REFUSAL")
        else:
            session.temporary.write_bytes(b"changed candidate")

    monkeypatch.setattr(adapter._Session, "migrate_and_check", changed)
    with pytest.raises((ValueError, sqlite3.DatabaseError, PermissionError)):
        build_sql_successor_inbound(target(source), root, b).apply(request(b))
    assert not (root / "runtime-copy.sqlite").exists()
    assert not (root / "applied-receipt.json").exists()
    assert (root / "before-sql-successor.sqlite").read_bytes() == source.read_bytes()
    assert (root / "FAILED.json").is_file()


def test_preexisting_internal_copy_and_alias_root_are_rejected(source):
    b = binding(source)
    with pytest.raises(ValueError, match="DISTINCT_ROOT"):
        build_sql_successor_inbound(target(source), source.parent / "nested", b)


def test_precondition_violation_keeps_ddl_and_data(source):
    c = sqlite3.connect(source, isolation_level=None)
    c.execute("DROP TRIGGER trg_official_attachment_requires_official_origin")
    c.execute("UPDATE institutional_attachment SET origin_type='AI_INFERENCE' WHERE id='att1'")
    c.close()
    b = binding(source)
    c = sqlite3.connect(source, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    before = definitions(c)
    with pytest.raises(ValueError, match="PRECONDITION_VIOLATION"):
        install_reviewed_successor(c, b.snapshot)
    assert definitions(c) == before
    assert c.execute("SELECT origin_type FROM institutional_attachment").fetchone() == (
        "AI_INFERENCE",
    )
    c.close()


@pytest.mark.parametrize(
    "object_name",
    (
        "_pr4_published_version_seal",
        "pr4_version_sealed_update",
        "v_pr4_current_resource_version_ambiguity",
        "v_current_resource_version",
    ),
)
def test_missing_successor_objects_cannot_be_reused(source, tmp_path, object_name):
    b = binding(source)
    root = tmp_path / "successor"
    inbound = build_sql_successor_inbound(target(source), root, b)
    inbound.apply(request(b))
    kind = (
        "TABLE"
        if object_name.startswith("_")
        else "TRIGGER"
        if object_name.startswith("pr4_")
        else "VIEW"
    )
    with sqlite3.connect(root / "runtime-copy.sqlite") as c:
        c.execute("DROP " + kind + " " + object_name)
    c.close()
    with pytest.raises(ValueError, match="FINAL_CHANGED"):
        inbound.apply(request(b))


def test_recovery_contract_never_uses_unchecked_replace():
    path = Path(adapter.__file__)
    text = path.read_text()
    assert "atomic_replace_checked" not in text
    assert "STOP_PENDING_SAFE_REPLACEMENT_REVIEW" in text


def test_copy_refuses_hardlink_without_truncating_other_file(tmp_path):
    import os

    source = tmp_path / "source"
    source.write_bytes(b"new bytes")
    original = tmp_path / "original"
    original.write_bytes(b"original bytes")
    destination = tmp_path / "destination"
    os.link(original, destination)
    with pytest.raises(ValueError, match="DESTINATION_SUBSTITUTION"):
        adapter._copy_exact(source, destination, tmp_path, hashlib.sha256(b"new bytes").hexdigest())
    assert original.read_bytes() == destination.read_bytes() == b"original bytes"


def test_exclusive_destination_rejects_child_write_and_replace(tmp_path):
    from backend.adapters.outbound.persistence.sql_successor_stability import (
        exclusive_copy_destination,
    )

    path = tmp_path / "fresh-copy"
    path.write_bytes(b"")
    with exclusive_copy_destination(path, tmp_path) as writer:
        for operation in (
            "p.write_bytes(b'changed')",
            "q=p.with_name('intruder');q.write_bytes(b'changed');os.replace(q,p)",
        ):
            child = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from pathlib import Path;import os,sys;p=Path(sys.argv[1]);" + operation,
                    str(path),
                ],
                capture_output=True,
            )
            assert child.returncode != 0 and b"PermissionError" in child.stderr
        writer.write(b"verified bytes")
    assert path.read_bytes() == b"verified bytes"


def test_complete_metadata_binding_not_only_definition_digest(source, tmp_path):
    b = binding(source)
    original = b.snapshot.tables
    changed = replace(original[0], columns=())
    wrong = replace(b, snapshot=replace(b.snapshot, tables=(changed, *original[1:])))
    inbound = build_sql_successor_inbound(target(source), tmp_path / "successor", wrong)
    with pytest.raises(ValueError, match="FULL_SOURCE_BINDING_CHANGED"):
        inbound.apply(request(wrong))
    assert not (tmp_path / "successor").exists()


@pytest.mark.parametrize("corruption", ("schema", "data", "seal"))
def test_coordinated_receipt_and_target_forgery_is_rejected(source, tmp_path, corruption):
    b = binding(source)
    root = tmp_path / "successor"
    inbound = build_sql_successor_inbound(target(source), root, b)
    inbound.apply(request(b))
    final = root / "runtime-copy.sqlite"
    c = sqlite3.connect(final)
    if corruption == "schema":
        c.execute("DROP TRIGGER pr4_version_sealed_update")
    elif corruption == "data":
        c.execute("UPDATE resource_version SET title='forged draft' WHERE id='vdraft'")
    else:
        original = c.execute(
            "SELECT sql FROM sqlite_schema WHERE name='pr4_seal_delete'"
        ).fetchone()[0]
        c.execute("DROP TRIGGER pr4_seal_delete")
        c.execute("DELETE FROM _pr4_published_version_seal WHERE resource_version_id='vpub'")
        c.execute(original)
    c.commit()
    rows = fingerprints(c, tuple(t.name for t in b.snapshot.tables))
    c.close()
    current = build_runtime_schema_inspection_inbound(target(final)).inspect()
    receipt = json.loads((root / "applied-receipt.json").read_text())
    receipt["result"]["final_sha256"] = hashlib.sha256(final.read_bytes()).hexdigest()
    receipt["result"]["post_schema_sha256"] = current.schema_sha256
    receipt["result"]["table_fingerprints"] = rows
    (root / "applied-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(
        ValueError, match="POST_SCHEMA_MISMATCH|FINAL_ROWS_CHANGED|INITIAL_SEAL_MISMATCH"
    ):
        inbound.apply(request(b))


@pytest.mark.parametrize(
    "transition", ("after_backup", "before_transaction", "after_reference", "after_transaction")
)
def test_initial_application_rejects_rows_not_bound_to_backup(
    source, tmp_path, monkeypatch, transition
):
    b = binding(source)
    root = tmp_path / "successor"
    source_bytes = source.read_bytes()

    def alter(c):
        c.execute(
            "UPDATE resource_version SET title='changed only working draft' WHERE id='vdraft'"
        )

    if transition == "after_backup":
        previous = adapter._Session.backup_and_verify_restore

        def injected(session):
            previous(session)
            with sqlite3.connect(session.temporary) as c:
                alter(c)
            c.close()

        monkeypatch.setattr(adapter._Session, "backup_and_verify_restore", injected)
    elif transition == "after_reference":
        previous = adapter.fingerprints
        changed = False

        def injected(c, tables):
            nonlocal changed
            rows = previous(c, tables)
            path = Path(c.execute("PRAGMA database_list").fetchone()[2])
            if c.in_transaction and path.name.startswith("initial-") and not changed:
                changed = True
                alter(c)
            return rows

        monkeypatch.setattr(adapter, "fingerprints", injected)
    else:
        previous = adapter.install_reviewed_successor

        def injected(c, snapshot, *args, **kwargs):
            if transition == "before_transaction":
                alter(c)
            result = previous(c, snapshot, *args, **kwargs)
            if transition == "after_transaction":
                alter(c)
            return result

        monkeypatch.setattr(adapter, "install_reviewed_successor", injected)
    with pytest.raises(ValueError, match="ROWS_CHANGED|INITIAL_COPY_CHANGED"):
        build_sql_successor_inbound(target(source), root, b).apply(request(b))
    assert source.read_bytes() == source_bytes
    assert (root / "before-sql-successor.sqlite").read_bytes() == source_bytes
    assert not (root / "runtime-copy.sqlite").exists()
    assert not (root / "applied-receipt.json").exists()
    assert (root / "FAILED.json").is_file()


def test_continuous_windows_binding_across_open_transaction_freeze_and_publication(
    source, tmp_path, monkeypatch
):
    b = binding(source)
    root = tmp_path / "successor"
    phases = []
    real_connect = sqlite3.connect
    real_fingerprints = adapter.fingerprints
    real_migrate = adapter._Session.migrate_and_check
    real_publish = adapter.publish_pinned_fresh

    def child_refused(path, operation):
        code = {
            "replace": "q=p.with_name('child-replacement');q.write_bytes(b'replacement');os.replace(q,p)",
            "write": "p.write_bytes(b'changed')",
            "sqlite": "c=sqlite3.connect(p,timeout=0);c.execute(\"UPDATE resource_version SET title='child' WHERE id='vdraft'\");c.commit()",
        }[operation]
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path;import os,sys,sqlite3;p=Path(sys.argv[1]);" + code,
                str(path),
            ],
            capture_output=True,
        )
        assert child.returncode != 0
        assert b"PermissionError" in child.stderr or b"OperationalError" in child.stderr

    def connected(path, *args, **kwargs):
        if isinstance(path, Path) and path.name.startswith("initial-"):
            child_refused(path, "replace")
            phases.append("SQLITE_OPEN_IDENTITY")
        return real_connect(path, *args, **kwargs)

    transaction_seen = False

    def fingerprinted(c, tables):
        nonlocal transaction_seen
        db_path = Path(c.execute("PRAGMA database_list").fetchone()[2])
        if c.in_transaction and db_path.name.startswith("initial-") and not transaction_seen:
            transaction_seen = True
            child_refused(db_path, "replace")
            child_refused(db_path, "sqlite")
            phases.append("TRANSACTION_IDENTITY_AND_SQLITE_WRITER")
        return real_fingerprints(c, tables)

    def migrated(session):
        real_migrate(session)
        child_refused(session.temporary, "replace")
        child_refused(session.temporary, "write")
        phases.append("READ_FREEZE")

    def published(src, dst, **kwargs):
        child_refused(src, "write")
        child_refused(src, "replace")
        real_publish(src, dst, **kwargs)
        assert src.is_file() and src.stat().st_ino == dst.stat().st_ino
        child_refused(dst, "write")
        child_refused(dst, "replace")
        phases.append("PUBLICATION_CONTINUOUS_FREEZE")

    monkeypatch.setattr(adapter.sqlite3, "connect", connected)
    monkeypatch.setattr(adapter, "fingerprints", fingerprinted)
    monkeypatch.setattr(adapter._Session, "migrate_and_check", migrated)
    monkeypatch.setattr(adapter, "publish_pinned_fresh", published)
    inbound = build_sql_successor_inbound(target(source), root, b)
    first = inbound.apply(request(b))
    assert first.state == "APPLIED"
    assert phases == [
        "SQLITE_OPEN_IDENTITY",
        "TRANSACTION_IDENTITY_AND_SQLITE_WRITER",
        "READ_FREEZE",
        "PUBLICATION_CONTINUOUS_FREEZE",
    ]
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()}
    assert inbound.apply(request(b)).state == "ALREADY_APPLIED"
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()} == before
    assert (root / "before-sql-successor.sqlite").read_bytes() == source.read_bytes()


def test_child_mutation_after_backup_refused_before_publication(source, tmp_path, monkeypatch):
    b = binding(source)
    root = tmp_path / "successor"
    old = adapter._Session.backup_and_verify_restore

    def injected(session):
        old(session)
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);c.execute(\"UPDATE resource_version SET title='child mutation' WHERE id='vdraft'\");c.commit();c.close()",
                str(session.temporary),
            ],
            capture_output=True,
        )
        assert child.returncode == 0

    monkeypatch.setattr(adapter._Session, "backup_and_verify_restore", injected)
    with pytest.raises(ValueError, match="INITIAL_COPY_CHANGED"):
        build_sql_successor_inbound(target(source), root, b).apply(request(b))
    assert not (root / "runtime-copy.sqlite").exists()
    assert not (root / "applied-receipt.json").exists()
    assert (root / "before-sql-successor.sqlite").read_bytes() == source.read_bytes()


def test_final_name_substitution_during_link_acquisition_never_receives_applied(
    source, tmp_path, monkeypatch
):
    import backend.adapters.outbound.persistence.sql_successor_stability as stability

    b = binding(source)
    root = tmp_path / "successor"
    original = stability.os.link

    def switched(src, dst, *args, **kwargs):
        original(src, dst, *args, **kwargs)
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path;import os,sys;p=Path(sys.argv[1]);q=p.with_name('substituted');q.write_bytes(b'foreign occupant');os.replace(q,p)",
                str(dst),
            ],
            capture_output=True,
        )
        assert child.returncode == 0

    monkeypatch.setattr(stability.os, "link", switched)
    with pytest.raises(ValueError, match="PUBLICATION_SUBSTITUTION"):
        build_sql_successor_inbound(target(source), root, b).apply(request(b))
    assert not (root / "applied-receipt.json").exists()
    assert (root / "runtime-copy.sqlite").read_bytes() == b"foreign occupant"
    assert (root / "before-sql-successor.sqlite").read_bytes() == source.read_bytes()
    assert (root / "FAILED.json").is_file()
