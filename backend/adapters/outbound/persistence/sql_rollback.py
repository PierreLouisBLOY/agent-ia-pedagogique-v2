"""RBACK-83F closed rollback; no replacement, deletion or caller-supplied SQL."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import ExitStack, closing, contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from backend.adapters.outbound.persistence.runtime_schema_inspection import (
    SQLiteRuntimeSchemaInspectionAdapter,
)
from backend.adapters.outbound.persistence.sql_rollback_handles import (
    MAINTENANCE_LOCK,
    RollbackPin,
    rollback_pin,
)
from backend.adapters.outbound.persistence.sql_successor import (
    _copy_exact,
    fingerprints,
    reviewed_post_objects,
    verify_initial_seal,
)
from backend.adapters.outbound.persistence.sql_successor_stability import pinned_windows_paths
from backend.infrastructure.filesystem import (
    capture_secure_path,
    ensure_private_directory,
    harden_private_file,
    hash_file_nofollow,
    read_file_nofollow,
)
from backend.modules.local_provisioning.application.runtime_schema_snapshot import (
    RuntimeSchemaSnapshot,
    require_immutable_schema_file_set,
)
from backend.modules.local_provisioning.application.sql_rollback import (
    RollbackFileIdentity,
    SQLRollbackBinding,
    SQLRollbackResult,
)

STABILITY = "RBACK_83F_PINNED_NO_REPLACE_READ_ALIASES_PROCESS_RECOVERY_1_3"
LIMIT = 2 * 1024 * 1024


def _json(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fresh_evidence(path: Path, root: Path, value: object) -> bytes:
    raw = _json(value)
    if len(raw) > LIMIT:
        raise ValueError("SQL_ROLLBACK_EVIDENCE_BOUNDS")
    with path.open("xb") as writer:
        writer.write(raw)
        writer.flush()
        os.fsync(writer.fileno())
    harden_private_file(path, allowed_root=root)
    return raw


def _checkpoint(stage: str) -> None:
    """Internal transition point; process-stop tests replace this function only."""


class SQLiteSQLRollbackAdapter:
    def __init__(
        self, source: Path, source_root: Path, root: Path, binding: SQLRollbackBinding
    ) -> None:
        self.source, self.source_root, self.root, self.binding = source, source_root, root, binding
        self.final = root / "runtime-copy.sqlite"
        self.retained = root / binding.retained_initial_name
        self.backup = root / "before-sql-successor.sqlite"
        self.applied = root / "applied-receipt.json"
        self.lock = root / MAINTENANCE_LOCK
        self.operation = root / ("rollback-" + binding.operation_sha256)
        self.stage = self.operation / "restoration-staging.sqlite"
        self.alias = self.operation / "restoration-read.sqlite"
        self.archive = self.operation / "successor-archive.sqlite"
        self.intention = self.operation / "intention.json"
        self.receipt = self.operation / "rolled-back-receipt.json"
        self.bound = json.loads(_json(asdict(binding)))
        self.lock_raw = _json(
            {"schema": "RBACK-MAINTENANCE-LOCK-1", "binding_sha256": _hash(_json(self.bound))}
        )

    def _exists(self, path: Path) -> bool:
        return capture_secure_path(path, allowed_root=self.root).exists

    def _snapshot(self, path: Path, root: Path, digest: str) -> RuntimeSchemaSnapshot:
        return SQLiteRuntimeSchemaInspectionAdapter(path, root, digest).inspect_schema()

    def _sidecars(self, *paths: Path) -> None:
        for path in paths:
            for suffix in ("-wal", "-shm", "-journal"):
                if self._exists(Path(str(path) + suffix)):
                    raise ValueError("SQL_ROLLBACK_SIDECAR_PRESENT")

    def _source_identity(self) -> RollbackFileIdentity:
        snap = self.binding.successor.snapshot
        return RollbackFileIdentity(
            snap.source_device, snap.source_inode, snap.source_size, snap.source_sha256
        )

    @contextmanager
    def _originals(self, stack: ExitStack) -> Iterator[dict[str, Any]]:
        expected = self.binding.successor.snapshot
        reader = SQLiteRuntimeSchemaInspectionAdapter(
            self.source, self.source_root, expected.source_sha256
        )
        files = reader.inspect_files()
        require_immutable_schema_file_set(files)
        stack.enter_context(
            pinned_windows_paths(
                root=self.source_root,
                files=tuple(Path(str(self.source) + row.suffix) for row in files if row.exists),
            )
        )
        source_pin = stack.enter_context(rollback_pin(self.source, self.source_root))
        source_pin.verify(self.source, self._source_identity(), 1)
        if reader.inspect_schema() != expected:
            raise ValueError("SQL_ROLLBACK_FULL_SOURCE_CHANGED")
        backup_pin = stack.enter_context(rollback_pin(self.backup, self.root))
        backup_pin.verify(self.backup, self.binding.backup, 1)
        stack.enter_context(rollback_pin(self.applied, self.root))
        raw = read_file_nofollow(self.applied, allowed_root=self.root, maximum_bytes=LIMIT)
        if _hash(raw) != self.binding.applied_receipt_sha256:
            raise ValueError("SQL_ROLLBACK_APPLIED_RECEIPT_CHANGED")
        receipt = json.loads(raw)
        if receipt.get("binding") != json.loads(_json(asdict(self.binding.successor))):
            raise ValueError("SQL_ROLLBACK_APPLIED_BINDING_CHANGED")
        result = receipt.get("result", {})
        if (
            result.get("state") != "APPLIED"
            or result.get("final_sha256") != self.binding.published.sha256
            or result.get("source_sha256") != expected.source_sha256
            or result.get("backup_sha256") != expected.source_sha256
        ):
            raise ValueError("SQL_ROLLBACK_APPLIED_RESULT_CHANGED")
        self._sidecars(self.final, self.retained, self.backup, self.archive, self.stage, self.alias)
        yield result
        source_pin.verify(self.source, self._source_identity(), 1)
        backup_pin.verify(self.backup, self.binding.backup, 1)
        if reader.inspect_schema() != expected or _hash(
            read_file_nofollow(self.applied, allowed_root=self.root, maximum_bytes=LIMIT)
        ) != _hash(raw):
            raise ValueError("SQL_ROLLBACK_ORIGINALS_CHANGED")

    def _old_check(
        self, path: Path, old: RollbackPin, read: RollbackPin, applied: dict[str, Any]
    ) -> None:
        old.verify(path, self.binding.published, 2)
        read.verify(self.retained, self.binding.published, 2)
        snap = self._snapshot(self.retained, self.root, self.binding.published.sha256)
        if {o.name: (o.kind, o.name, o.table, o.definition) for o in snap.objects} != (
            reviewed_post_objects(self.binding.successor.snapshot)
        ):
            raise ValueError("SQL_ROLLBACK_PUBLISHED_SCHEMA_CHANGED")
        if snap.schema_sha256 != applied["post_schema_sha256"]:
            raise ValueError("SQL_ROLLBACK_PUBLISHED_SCHEMA_CHANGED")
        tables = tuple(t.name for t in self.binding.successor.snapshot.tables)
        with closing(
            sqlite3.connect(self.retained.as_uri() + "?mode=ro&immutable=1", uri=True)
        ) as c:
            c.execute("PRAGMA foreign_keys=ON")
            verify_initial_seal(c)
            observed = fingerprints(c, tables)
        with closing(sqlite3.connect(self.backup.as_uri() + "?mode=ro&immutable=1", uri=True)) as c:
            rows = fingerprints(c, tables)
        if observed != rows or tuple(tuple(row) for row in applied["table_fingerprints"]) != rows:
            raise ValueError("SQL_ROLLBACK_PUBLISHED_ROWS_CHANGED")

    def _restore_check(
        self, path: Path, renamed: RollbackPin, read: RollbackPin, identity: RollbackFileIdentity
    ) -> None:
        renamed.verify(path, identity, 2)
        read.verify(self.alias, identity, 2)
        original = self.binding.successor.snapshot
        if (identity.device, identity.inode) in {
            (original.source_device, original.source_inode),
            (self.binding.backup.device, self.binding.backup.inode),
            (self.binding.published.device, self.binding.published.inode),
        }:
            raise ValueError("SQL_ROLLBACK_RESTORATION_NOT_INDEPENDENT")
        if identity.sha256 != original.source_sha256 or identity.size != original.source_size:
            raise ValueError("SQL_ROLLBACK_RESTORATION_CHANGED")
        snap = self._snapshot(self.alias, self.root, original.source_sha256)
        if (
            snap.schema_sha256,
            snap.objects,
            snap.tables,
            snap.indexes,
            snap.integrity,
            snap.quick_check,
            snap.foreign_key_violations,
        ) != (
            original.schema_sha256,
            original.objects,
            original.tables,
            original.indexes,
            ("ok",),
            ("ok",),
            0,
        ):
            raise ValueError("SQL_ROLLBACK_RESTORATION_SCHEMA_CHANGED")
        # Exact original bytes also authenticate every row, beyond metadata.

    def _lock(self, stack: ExitStack, *, fresh: bool) -> RollbackPin:
        if fresh:
            _fresh_evidence(self.lock, self.root, json.loads(self.lock_raw))
        pin = stack.enter_context(rollback_pin(self.lock, self.root, exclusive=True))
        observed = pin.identity()
        if observed.sha256 != _hash(self.lock_raw) or os.fstat(pin.fd).st_nlink != 1:
            raise ValueError("SQL_ROLLBACK_LOCK_BINDING_CHANGED")
        return pin

    def _result(self, state: str, digest: str, identity: RollbackFileIdentity) -> SQLRollbackResult:
        from typing import Literal, cast

        return SQLRollbackResult(
            cast(Literal["PREPARED", "ROLLED_BACK", "ALREADY_ROLLED_BACK"], state),
            self.binding.operation_sha256,
            digest,
            identity,
            self.binding.successor.snapshot.source_sha256,
            self.binding.applied_receipt_sha256,
            STABILITY,
        )

    def prepare(self) -> SQLRollbackResult:
        self.binding.validate()
        with ExitStack() as stack:
            stack.enter_context(pinned_windows_paths(root=self.root, directories=(self.root,)))
            lock = self._lock(stack, fresh=True)
            with self._originals(stack) as applied:
                old = stack.enter_context(rollback_pin(self.final, self.root, rename=True))
                read = stack.enter_context(rollback_pin(self.retained, self.root))
                self._old_check(self.final, old, read, applied)
                if self._exists(self.archive) or self._exists(self.operation):
                    raise ValueError("SQL_ROLLBACK_OPERATION_COLLISION")
                self.operation.mkdir(exist_ok=False)
                ensure_private_directory(self.operation, allowed_root=self.root)
                stack.enter_context(
                    pinned_windows_paths(root=self.root, directories=(self.operation,))
                )
                with self.stage.open("xb"):
                    pass
                harden_private_file(self.stage, allowed_root=self.root)
                _copy_exact(self.backup, self.stage, self.root, self.binding.backup.sha256)
                # New identity comes only from newly made independent, verified bytes.
                staged = stack.enter_context(rollback_pin(self.stage, self.root, rename=True))
                identity = staged.identity()
                staged.verify(self.stage, identity, 1)
                os.link(self.stage, self.alias)
                alias = stack.enter_context(rollback_pin(self.alias, self.root))
                self._restore_check(self.stage, staged, alias, identity)
                self._old_check(self.final, old, read, applied)
                self._sidecars(self.final, self.retained, self.backup, self.stage, self.alias)
                intent = {
                    "schema": "RBACK-INTENTION-1.3",
                    "binding": self.bound,
                    "lock": asdict(lock.identity()),
                    "restored": asdict(identity),
                    "names": {
                        "stage": self.stage.name,
                        "alias": self.alias.name,
                        "archive": self.archive.name,
                        "final": self.final.name,
                    },
                    "restored_schema_sha256": self.binding.successor.snapshot.schema_sha256,
                    "non_atomic_namespace_gap": True,
                    "unobserved_transient_alias_excluded": False,
                    "power_loss_proved": False,
                }
                raw = _fresh_evidence(self.intention, self.root, intent)
                stack.enter_context(rollback_pin(self.intention, self.root))
                if (
                    read_file_nofollow(self.intention, allowed_root=self.root, maximum_bytes=LIMIT)
                    != raw
                ):
                    raise ValueError("SQL_ROLLBACK_INTENTION_SUBSTITUTION")
                _checkpoint("PREPARED_BEFORE_HASH_RETURN")
                return self._result("PREPARED", _hash(raw), identity)

    def execute(self, intention_sha256: str) -> SQLRollbackResult:
        self.binding.validate()
        with ExitStack() as stack:
            stack.enter_context(
                pinned_windows_paths(root=self.root, directories=(self.root, self.operation))
            )
            lock = self._lock(stack, fresh=False)
            stack.enter_context(rollback_pin(self.intention, self.root))
            raw = read_file_nofollow(self.intention, allowed_root=self.root, maximum_bytes=LIMIT)
            if _hash(raw) != intention_sha256:
                raise ValueError("SQL_ROLLBACK_STOP_PARTIAL_INTENTION_CHANGED")
            intent = json.loads(raw)
            if (
                intent.get("schema") != "RBACK-INTENTION-1.3"
                or intent.get("binding") != self.bound
                or intent.get("lock") != asdict(lock.identity())
                or intent.get("names")
                != {
                    "stage": self.stage.name,
                    "alias": self.alias.name,
                    "archive": self.archive.name,
                    "final": self.final.name,
                }
                or intent.get("restored_schema_sha256")
                != (self.binding.successor.snapshot.schema_sha256)
            ):
                raise ValueError("SQL_ROLLBACK_STOP_PARTIAL_BINDING_CHANGED")
            identity = RollbackFileIdentity(**intent["restored"])
            identity.validate()
            with self._originals(stack) as applied:
                retired = self._exists(self.archive)
                staged_present = self._exists(self.stage)
                final_present = self._exists(self.final)
                complete = self._exists(self.receipt)
                # Four and only four attested namespace states are recoverable.
                initial = not retired and staged_present and final_present and not complete
                after_retire = retired and staged_present and not final_present and not complete
                after_restore = retired and not staged_present and final_present
                if not (initial or after_retire or after_restore) or (
                    complete and not after_restore
                ):
                    raise ValueError("SQL_ROLLBACK_STOP_PARTIAL_UNKNOWN_STATE")
                old_path = self.final if initial else self.archive
                restore_path = self.stage if staged_present else self.final
                old = stack.enter_context(rollback_pin(old_path, self.root, rename=True))
                old_read = stack.enter_context(rollback_pin(self.retained, self.root))
                restored = stack.enter_context(rollback_pin(restore_path, self.root, rename=True))
                alias = stack.enter_context(rollback_pin(self.alias, self.root))
                self._old_check(old_path, old, old_read, applied)
                self._restore_check(restore_path, restored, alias, identity)
                if initial:
                    _checkpoint("BEFORE_RETIRE")
                    self._old_check(self.final, old, old_read, applied)
                    old.rename_fresh(self.archive)
                    _checkpoint("AFTER_RETIRE")
                    old_path = self.archive
                self._old_check(old_path, old, old_read, applied)
                self._restore_check(restore_path, restored, alias, identity)
                self._sidecars(
                    self.final, self.retained, self.backup, self.archive, self.stage, self.alias
                )
                if staged_present:
                    restored.rename_fresh(self.final)
                    _checkpoint("AFTER_RESTORE")
                self._old_check(self.archive, old, old_read, applied)
                self._restore_check(self.final, restored, alias, identity)
                self._sidecars(
                    self.final, self.retained, self.backup, self.archive, self.stage, self.alias
                )
                result = self._result("ROLLED_BACK", intention_sha256, identity)
                expected_receipt = {
                    "schema": "RBACK-RESULT-1.3",
                    "binding": self.bound,
                    "result": asdict(result),
                    "historical_applied_preserved": True,
                }
                if complete:
                    stack.enter_context(rollback_pin(self.receipt, self.root))
                    if read_file_nofollow(
                        self.receipt, allowed_root=self.root, maximum_bytes=LIMIT
                    ) != _json(expected_receipt):
                        raise ValueError("SQL_ROLLBACK_STOP_PARTIAL_FINAL_RECEIPT_CHANGED")
                    return replace(result, state="ALREADY_ROLLED_BACK")
                # Source/backup/APPLIED postconditions must precede durable success.
                if self._snapshot(
                    self.source, self.source_root, self.binding.successor.snapshot.source_sha256
                ) != (self.binding.successor.snapshot):
                    raise ValueError("SQL_ROLLBACK_SOURCE_CHANGED")
                if hash_file_nofollow(
                    self.backup, allowed_root=self.root
                ) != self.binding.backup.sha256 or _hash(
                    read_file_nofollow(self.applied, allowed_root=self.root, maximum_bytes=LIMIT)
                ) != (self.binding.applied_receipt_sha256):
                    raise ValueError("SQL_ROLLBACK_ORIGINALS_CHANGED")
                _fresh_evidence(self.receipt, self.root, expected_receipt)
                stack.enter_context(rollback_pin(self.receipt, self.root))
                if read_file_nofollow(
                    self.receipt, allowed_root=self.root, maximum_bytes=LIMIT
                ) != _json(expected_receipt):
                    raise ValueError("SQL_ROLLBACK_FINAL_RECEIPT_SUBSTITUTION")
                return result
