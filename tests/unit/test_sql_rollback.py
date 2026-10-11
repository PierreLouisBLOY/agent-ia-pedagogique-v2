"""Native Windows rollback via Application on synthetic fixtures exclusively."""

import ast
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

import backend.adapters.outbound.persistence.sql_rollback as adapter
from backend.adapters.outbound.persistence.sql_rollback_handles import rollback_pin
from backend.infrastructure.composition.factories.runtime_schema_inspection import (
    build_runtime_schema_inspection_inbound,
)
from backend.infrastructure.composition.factories.sql_rollback import build_sql_rollback_inbound
from backend.infrastructure.composition.factories.sql_successor import build_sql_successor_inbound
from backend.modules.local_provisioning.application.sql_rollback import (
    RollbackFileIdentity,
    SQLRollbackBinding,
    SQLRollbackRequest,
)
from tests.unit.test_sql_successor import binding, request, target
from tests.unit.test_sql_successor import source as source_fixture


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path):
    row = path.stat()
    return RollbackFileIdentity(row.st_dev, row.st_ino, row.st_size, digest(path))


@pytest.fixture
def source(tmp_path):
    return source_fixture.__wrapped__(tmp_path)


@pytest.fixture
def case(source, tmp_path):
    initial = binding(source)
    root = tmp_path / "successor"
    migration = build_sql_successor_inbound(target(source), root, initial)
    migration.apply(request(initial))
    retained = tuple(root.glob("initial-*.sqlite"))
    assert len(retained) == 1
    bound = SQLRollbackBinding(
        initial,
        "e" * 64,
        "f" * 64,
        "1" * 64,
        "2" * 64,
        digest(root / "applied-receipt.json"),
        retained[0].name,
        identity(root / "runtime-copy.sqlite"),
        identity(root / "before-sql-successor.sqlite"),
    )
    req = SQLRollbackRequest(
        bound.plan_sha256, bound.decision_sha256, bound.review_sha256, bound.operation_sha256
    )
    inbound = build_sql_rollback_inbound(target(source), root, bound)
    return {
        "source": source,
        "root": root,
        "binding": bound,
        "request": req,
        "inbound": inbound,
        "migration": migration,
        "operation": root / ("rollback-" + bound.operation_sha256),
    }


@pytest.fixture
def prepared(case):
    case["preparation"] = case["inbound"].prepare(case["request"])
    return case


def execute(case):
    return case["inbound"].execute(case["request"], case["preparation"].intention_sha256)


def run_worker(case, point):
    config = case["root"].parent / ("external-binding-" + point + ".json")
    value = {
        "source": str(case["source"]),
        "root": str(case["root"]),
        "binding": asdict(case["binding"]),
        "intention_sha256": case["preparation"].intention_sha256 if "preparation" in case else None,
    }
    with config.open("x", encoding="utf-8") as out:
        json.dump(value, out)
    return subprocess.run(
        [sys.executable, "-m", "tests.support.sql_rollback_worker", str(config), point],
        capture_output=True,
        text=True,
        timeout=90,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def test_nominal_reopens_and_repeat_is_readonly(prepared):
    c = prepared
    root = c["root"]
    original = c["source"].read_bytes()
    applied = (root / "applied-receipt.json").read_bytes()
    assert execute(c).state == "ROLLED_BACK"
    snap = build_runtime_schema_inspection_inbound(target(root / "runtime-copy.sqlite")).inspect()
    assert snap.objects == c["binding"].successor.snapshot.objects
    assert (root / "runtime-copy.sqlite").read_bytes() == original
    assert (root / "before-sql-successor.sqlite").read_bytes() == original
    assert (root / "applied-receipt.json").read_bytes() == applied
    before = {
        str(p): (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_ino)
        for p in root.rglob("*")
        if p.is_file()
    }
    assert execute(c).state == "ALREADY_ROLLED_BACK"
    assert before == {
        str(p): (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_ino)
        for p in root.rglob("*")
        if p.is_file()
    }
    with pytest.raises(ValueError, match="ROLLBACK_HISTORY_RETAINED"):
        c["migration"].apply(request(c["binding"].successor))
    with pytest.raises(ValueError, match="ROLLBACK_HISTORY_RETAINED"):
        c["migration"].resolve_current("r1")


def test_archive_collision_preserved(prepared):
    c = prepared
    archive = c["operation"] / "successor-archive.sqlite"
    archive.write_bytes(b"FOREIGN ARCHIVE")
    before = (c["root"] / "runtime-copy.sqlite").read_bytes()
    with pytest.raises(ValueError):
        execute(c)
    assert archive.read_bytes() == b"FOREIGN ARCHIVE"
    assert (c["root"] / "runtime-copy.sqlite").read_bytes() == before
    assert not (c["operation"] / "rolled-back-receipt.json").exists()


def test_final_collision_after_retirement_preserved(prepared, monkeypatch):
    c = prepared

    def collision(stage):
        if stage == "AFTER_RETIRE":
            (c["root"] / "runtime-copy.sqlite").write_bytes(b"FOREIGN FINAL")

    monkeypatch.setattr(adapter, "_checkpoint", collision)
    with pytest.raises(ValueError, match="DESTINATION_COLLISION"):
        execute(c)
    assert (c["root"] / "runtime-copy.sqlite").read_bytes() == b"FOREIGN FINAL"
    assert (c["operation"] / "successor-archive.sqlite").exists()
    assert (c["operation"] / "restoration-staging.sqlite").exists()
    assert not (c["operation"] / "rolled-back-receipt.json").exists()


def test_equal_bytes_different_inode_substitution_is_refused(prepared):
    c = prepared
    stage = c["operation"] / "restoration-staging.sqlite"
    substitute = c["operation"] / "foreign.sqlite"
    substitute.write_bytes(stage.read_bytes())
    os.replace(substitute, stage)
    with pytest.raises(ValueError, match="IDENTITY_OR_LINK_CHANGED"):
        execute(c)
    assert not (c["operation"] / "successor-archive.sqlite").exists()


@pytest.mark.parametrize(
    "name",
    [
        "runtime-copy.sqlite",
        "before-sql-successor.sqlite",
        "restoration-staging.sqlite",
        "restoration-read.sqlite",
    ],
)
def test_unexpected_hardlink_refused(prepared, name):
    c = prepared
    base = c["operation"] if name.startswith("restoration") else c["root"]
    os.link(base / name, c["root"].parent / "unexpected-alias.sqlite")
    with pytest.raises(ValueError, match="IDENTITY_OR_LINK_CHANGED"):
        execute(c)
    assert not (c["operation"] / "rolled-back-receipt.json").exists()


def test_active_writer_refused(prepared):
    with (prepared["root"] / "runtime-copy.sqlite").open("r+b"):
        with pytest.raises(ValueError, match="WRITER_OR_MAINTENANCE_PRESENT"):
            execute(prepared)
    assert not (prepared["operation"] / "successor-archive.sqlite").exists()


@pytest.mark.parametrize("point", ["AFTER_RETIRE", "AFTER_RESTORE"])
def test_process_crash_and_new_process_resume(prepared, point):
    c = prepared
    child = run_worker(c, point)
    assert child.returncode == 23, child.stderr
    assert (c["operation"] / "successor-archive.sqlite").exists()
    assert not (c["operation"] / "rolled-back-receipt.json").exists()
    if point == "AFTER_RETIRE":
        assert not (c["root"] / "runtime-copy.sqlite").exists()
    else:
        assert (c["root"] / "runtime-copy.sqlite").exists()
    resumed = run_worker(c, "NONE")
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)["state"] == "ROLLED_BACK"
    assert (c["root"] / "runtime-copy.sqlite").read_bytes() == c["source"].read_bytes()
    assert execute(c).state == "ALREADY_ROLLED_BACK"


def test_prepare_crash_does_not_auto_admit_intention(case):
    c = case
    child = run_worker(c, "PREPARED_BEFORE_HASH_RETURN")
    assert child.returncode == 23, child.stderr
    assert (c["operation"] / "intention.json").exists()
    with pytest.raises(ValueError, match="INTENTION_CHANGED"):
        c["inbound"].execute(c["request"], "0" * 64)
    with pytest.raises(FileExistsError):
        c["inbound"].prepare(c["request"])
    assert not (c["operation"] / "successor-archive.sqlite").exists()


def test_coordinated_applied_and_target_forgery_refused(prepared):
    c = prepared
    final = c["root"] / "runtime-copy.sqlite"
    final.write_bytes(b"COORDINATED FORGERY")
    receipt = c["root"] / "applied-receipt.json"
    row = json.loads(receipt.read_bytes())
    row["result"]["final_sha256"] = digest(final)
    receipt.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="APPLIED_RECEIPT_CHANGED"):
        execute(c)
    assert not (c["operation"] / "successor-archive.sqlite").exists()


def test_backup_modification_refused(prepared):
    (prepared["root"] / "before-sql-successor.sqlite").write_bytes(b"MODIFIED BACKUP")
    with pytest.raises(ValueError, match="IDENTITY_OR_LINK_CHANGED"):
        execute(prepared)
    assert not (prepared["operation"] / "successor-archive.sqlite").exists()


def test_archive_modification_after_crash_refused(prepared):
    c = prepared
    assert run_worker(c, "AFTER_RETIRE").returncode == 23
    (c["operation"] / "successor-archive.sqlite").write_bytes(b"MODIFIED ARCHIVE")
    with pytest.raises(ValueError, match="IDENTITY_OR_LINK_CHANGED"):
        execute(c)
    assert not (c["root"] / "runtime-copy.sqlite").exists()


def test_other_request_or_binding_refused(prepared):
    c = prepared
    with pytest.raises(ValueError, match="REQUEST_MISMATCH"):
        c["inbound"].execute(
            replace(c["request"], operation_sha256="3" * 64), c["preparation"].intention_sha256
        )
    other = replace(c["binding"], decision_sha256="4" * 64)
    inbound = build_sql_rollback_inbound(target(c["source"]), c["root"], other)
    req = replace(c["request"], decision_sha256="4" * 64)
    with pytest.raises(ValueError, match="LOCK_BINDING_CHANGED"):
        inbound.execute(req, c["preparation"].intention_sha256)


@pytest.mark.parametrize("mutation", ["missing", "truncated", "foreign_hash"])
def test_untrusted_intention_refused(prepared, mutation):
    c = prepared
    intent = c["operation"] / "intention.json"
    if mutation == "missing":
        intent.rename(c["operation"] / "retained-intention.json")
    elif mutation == "truncated":
        intent.write_bytes(b"{")
    expected = "0" * 64 if mutation == "foreign_hash" else c["preparation"].intention_sha256
    with pytest.raises(ValueError):
        c["inbound"].execute(c["request"], expected)
    assert not (c["operation"] / "successor-archive.sqlite").exists()


def test_false_final_receipt_refused(prepared):
    c = prepared
    assert execute(c).state == "ROLLED_BACK"
    receipt = c["operation"] / "rolled-back-receipt.json"
    receipt.write_bytes(b'{"state":"ROLLED_BACK"}')
    with pytest.raises(ValueError, match="FINAL_RECEIPT_CHANGED"):
        execute(c)


def test_maintenance_lock_interprocess_contention(prepared):
    c = prepared
    with rollback_pin(c["root"] / "rollback-maintenance.lock", c["root"], exclusive=True):
        child = run_worker(c, "NONE")
        assert child.returncode != 0
        assert "WRITER_OR_MAINTENANCE_PRESENT" in child.stderr
    assert not (c["operation"] / "successor-archive.sqlite").exists()


@pytest.mark.parametrize(
    "name",
    [
        "runtime-copy.sqlite",
        "restoration-staging.sqlite",
        "restoration-read.sqlite",
        "before-sql-successor.sqlite",
    ],
)
def test_sidecar_on_any_relevant_alias_refused(prepared, name):
    c = prepared
    base = c["operation"] if name.startswith("restoration") else c["root"]
    (base / (name + "-journal")).write_bytes(b"UNKNOWN SIDECAR")
    with pytest.raises(ValueError, match="SIDECAR_PRESENT"):
        execute(c)
    assert not (c["operation"] / "successor-archive.sqlite").exists()


def test_no_default_http_tools_launcher_or_free_sql_surface():
    root = Path(__file__).resolve().parents[2]
    for path in (
        root / "backend/modules/local_provisioning/application/sql_rollback.py",
        root / "backend/adapters/inbound/application/sql_rollback.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(
            str(n).startswith(("sqlite3", "backend.infrastructure", "backend.adapters"))
            for n in imports
        )
    for directory in (
        "backend/adapters/inbound/api",
        "backend/adapters/inbound/agent_tools",
        "tools",
    ):
        for path in (root / directory).rglob("*.py"):
            assert "build_sql_rollback_inbound" not in path.read_text(encoding="utf-8")
    fields = SQLRollbackRequest.__dataclass_fields__
    assert not {"sql", "path", "root", "destination", "force"}.intersection(fields)


def test_substitution_between_capture_and_handle_open_refused(prepared, monkeypatch):
    import backend.adapters.outbound.persistence.sql_rollback_handles as handles

    c = prepared
    stage = c["operation"] / "restoration-staging.sqlite"
    original = handles.capture_secure_path
    done = False

    def replace_after_capture(path, *, allowed_root):
        nonlocal done
        observed = original(path, allowed_root=allowed_root)
        if path == stage and observed.exists and not done:
            done = True
            substitute = c["operation"] / "foreign-at-open.sqlite"
            substitute.write_bytes(stage.read_bytes())
            os.replace(substitute, stage)
        return observed

    monkeypatch.setattr(handles, "capture_secure_path", replace_after_capture)
    with pytest.raises(ValueError, match="OPENED_SUBSTITUTION"):
        execute(c)
    assert done
    assert not (c["operation"] / "successor-archive.sqlite").exists()


def test_hardlink_added_after_retirement_stops_partial(prepared, monkeypatch):
    c = prepared

    def alias(stage):
        if stage == "AFTER_RETIRE":
            os.link(
                c["operation"] / "successor-archive.sqlite", c["root"].parent / "late-alias.sqlite"
            )

    monkeypatch.setattr(adapter, "_checkpoint", alias)
    with pytest.raises(ValueError, match="IDENTITY_OR_LINK_CHANGED"):
        execute(c)
    assert not (c["root"] / "runtime-copy.sqlite").exists()
    assert not (c["operation"] / "rolled-back-receipt.json").exists()


def test_both_file_pairs_refuse_concurrent_write_and_replace(prepared, monkeypatch):
    c = prepared
    attempts = []

    def attack(stage):
        if stage != "AFTER_RESTORE":
            return
        names = [
            c["root"] / "runtime-copy.sqlite",
            c["operation"] / "restoration-read.sqlite",
            c["operation"] / "successor-archive.sqlite",
            c["root"] / c["binding"].retained_initial_name,
        ]
        code = "import os,json,sys;from pathlib import Path;out=[]\nfor arg in sys.argv[1:]:\n p=Path(arg)\n for op in ('write','replace'):\n  try:\n   if op=='write':p.write_bytes(b'ATTACK')\n   else:os.replace(p,p.with_name('foreign-'+p.name))\n   out.append('PERMITTED')\n  except OSError:out.append('REFUSED')\nprint(json.dumps(out))"
        child = subprocess.run(
            [sys.executable, "-c", code, *map(str, names)],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        assert child.returncode == 0, child.stderr
        attempts.extend(json.loads(child.stdout))

    monkeypatch.setattr(adapter, "_checkpoint", attack)
    assert execute(c).state == "ROLLED_BACK"
    assert attempts == ["REFUSED"] * 8


def test_lock_equal_bytes_different_inode_refused(prepared):
    c = prepared
    lock = c["root"] / "rollback-maintenance.lock"
    substitute = c["root"] / "foreign-lock"
    substitute.write_bytes(lock.read_bytes())
    os.replace(substitute, lock)
    with pytest.raises(ValueError, match="BINDING_CHANGED"):
        execute(c)
    assert not (c["operation"] / "successor-archive.sqlite").exists()


def test_other_operation_cannot_prepare_a_second_namespace(prepared):
    c = prepared
    other = replace(c["binding"], operation_sha256="9" * 64)
    inbound = build_sql_rollback_inbound(target(c["source"]), c["root"], other)
    with pytest.raises(FileExistsError):
        inbound.prepare(replace(c["request"], operation_sha256="9" * 64))
    assert not (c["root"] / ("rollback-" + "9" * 64)).exists()


def test_reuse_after_prepare_is_explicitly_refused(prepared):
    c = prepared
    with pytest.raises(ValueError, match="ROLLBACK_HISTORY_RETAINED"):
        c["migration"].apply(request(c["binding"].successor))
    with pytest.raises(ValueError, match="ROLLBACK_HISTORY_RETAINED"):
        c["migration"].resolve_current("r1")


def test_writable_mapping_without_file_handle_is_refused(prepared):
    import mmap

    c = prepared
    with (c["root"] / "runtime-copy.sqlite").open("r+b") as file:
        view = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_WRITE)
    try:
        with pytest.raises(ValueError, match="WRITER_OR_MAINTENANCE_PRESENT"):
            execute(c)
    finally:
        view.close()
    assert not (c["operation"] / "successor-archive.sqlite").exists()
    assert not (c["operation"] / "rolled-back-receipt.json").exists()
