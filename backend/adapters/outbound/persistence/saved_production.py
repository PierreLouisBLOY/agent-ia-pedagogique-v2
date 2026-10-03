"""Explicit private R4 store. Atomic snapshots, immutable records, interprocess lock."""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from backend.infrastructure.filesystem import (
    assert_local_data_root,
    atomic_publish_fresh,
    atomic_replace_checked,
    capture_secure_path,
    ensure_private_directory,
    private_temporary_file,
    read_file_nofollow,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    encoded,
    fingerprint,
    identifier,
    object_data,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction

_MARKER = b"R4-PRIVATE-DOCUMENTARY-STORE-1.0\n"
_ROOT = Path(__file__).resolve().parents[4]
T = TypeVar("T")


class LocalSavedProductionStore:
    def __init__(self, root: Path, *, create: bool = False) -> None:
        # Check lexical containment before touching any selected target metadata.
        if not root.is_absolute() or root == Path(root.anchor) or root == _ROOT or _ROOT in root.parents:
            raise ValueError("R4_STORE_OUTSIDE_REPOSITORY_REQUIRED")
        self.root = assert_local_data_root(root)
        if create:
            if capture_secure_path(self.root, allowed_root=self.root.parent).exists:
                raise ValueError("R4_FRESH_ROOT_REQUIRED")
            ensure_private_directory(self.root, allowed_root=self.root.parent)
            self._publish(self.root / "catalog.json", {"records": {}, "actions": {}}, fresh=True)
            self._fresh_bytes("writer.lock", b"0")
            self._fresh_bytes("R4_STORE", _MARKER)
        self._verify()

    def _verify(self) -> None:
        if read_file_nofollow(self.root / "R4_STORE", allowed_root=self.root,
                              maximum_bytes=100) != _MARKER:
            raise ValueError("R4_STORE_IDENTITY")
        for name in ("catalog.json", "writer.lock"):
            if not capture_secure_path(self.root / name, allowed_root=self.root).is_file:
                raise ValueError("R4_STORE_INCOMPLETE")

    def _fresh_bytes(self, name: str, raw: bytes) -> None:
        temporary = private_temporary_file(self.root, allowed_root=self.root,
                                            prefix="r4-", suffix=".pending")
        with temporary.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_publish_fresh(temporary, self.root / name, allowed_root=self.root)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self._verify()
        path = self.root / "writer.lock"
        before = capture_secure_path(path, allowed_root=self.root)
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) != (before.device, before.inode):
                raise ValueError("R4_LOCK_CHANGED")
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(descriptor)  # OS releases the lock even after process termination.

    def _read(self) -> dict[str, object]:
        raw = read_file_nofollow(self.root / "catalog.json", allowed_root=self.root,
                                 maximum_bytes=16 * 1024 * 1024)
        data = object_data(json.loads(raw), {"catalog", "sha256"})
        catalog = object_data(data["catalog"], {"records", "actions"})
        if fingerprint(catalog) != data["sha256"]:
            raise ValueError("R4_CATALOG_INTEGRITY")
        return catalog

    def _publish(self, path: Path, catalog: Mapping[str, object], *, fresh: bool = False) -> None:
        expected = capture_secure_path(path, allowed_root=self.root)
        raw = encoded({"catalog": catalog, "sha256": fingerprint(catalog)})
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("R4_STORE_FULL")
        temporary = private_temporary_file(self.root, allowed_root=self.root,
                                            prefix="r4-", suffix=".pending")
        with temporary.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if fresh:
            atomic_publish_fresh(temporary, path, allowed_root=self.root)
        else:
            atomic_replace_checked(temporary, path, allowed_root=self.root,
                                   expected_destination=expected)
        # No partial success: read back the exact published bytes before returning.
        if read_file_nofollow(path, allowed_root=self.root, maximum_bytes=len(raw)) != raw:
            raise ValueError("R4_COMMIT_UNKNOWN")

    def _transaction(self, update: Callable[[dict[str, object]], tuple[T, bool]]) -> T:
        with self._locked():
            catalog = self._read()
            result, changed = update(catalog)
            if changed:
                self._publish(self.root / "catalog.json", catalog)
            return result

    @staticmethod
    def _key(production_ref: str, version_ref: str) -> str:
        return identifier(production_ref, "prod") + "/" + identifier(version_ref, "ver")

    def save(self, record: SavedProduction) -> bool:
        record = SavedProduction(record.data)
        key = self._key(record.production_ref, record.version_ref)
        def update(catalog: dict[str, object]) -> tuple[bool, bool]:
            records = object_data(catalog["records"])
            if key in records:
                if SavedProduction(object_data(records[key])).sha256 != record.sha256:
                    raise ValueError("R4_IDENTITY_CONFLICT")
                return False, False
            if sum(k.startswith(record.production_ref + "/") for k in records) >= 3:
                raise ValueError("R4_VERSION_LIMIT")
            if len(records) >= 300:
                raise ValueError("R4_STORE_FULL")
            records[key] = record.mutable_copy()
            catalog["records"] = records
            return True, True
        return self._transaction(update)

    def load(self, production_ref: str, version_ref: str) -> SavedProduction:
        key = self._key(production_ref, version_ref)
        self._verify()
        records = object_data(self._read()["records"])
        if key not in records:
            raise ValueError("R4_NOT_FOUND")
        record = SavedProduction(object_data(records[key]))
        if (record.production_ref, record.version_ref) != (production_ref, version_ref):
            raise ValueError("R4_CATALOG_INTEGRITY")
        return record

    def list_versions(self) -> tuple[SavedProduction, ...]:
        self._verify()
        records = object_data(self._read()["records"])
        result = tuple(SavedProduction(object_data(records[key])) for key in sorted(records))
        if any(self._key(r.production_ref, r.version_ref) not in records for r in result):
            raise ValueError("R4_CATALOG_INTEGRITY")
        return result

    def append_action(self, record: SavedProduction, action_id: str,
                      action: Mapping[str, object], *,
                      expected_actions_sha256: str | None = None) -> Mapping[str, object]:
        identifier(action_id, "action")
        key = self._key(record.production_ref, record.version_ref)
        entry: dict[str, object] = {"record_sha256": record.sha256, "key": key, "action": dict(action)}
        def update(catalog: dict[str, object]) -> tuple[Mapping[str, object], bool]:
            saved = object_data(catalog["records"]).get(key)
            if saved is None or SavedProduction(object_data(saved)).sha256 != record.sha256:
                raise ValueError("R4_IDENTITY_CONFLICT")
            actions = object_data(catalog["actions"])
            if action_id in actions:
                previous = object_data(actions[action_id])
                if (previous.get("record_sha256") != record.sha256 or previous.get("key") != key
                        or fingerprint(previous.get("action")) != fingerprint(action)):
                    raise ValueError("R4_IDEMPOTENCY_CONFLICT")
                return dict(action), False
            if (expected_actions_sha256 is not None
                    and fingerprint(self._ordered_actions(actions, record)) != expected_actions_sha256):
                raise ValueError("R4_ACTIONS_CHANGED")
            if len(actions) >= 3000:
                raise ValueError("R4_STORE_FULL")
            entry["sequence"] = len(actions) + 1
            actions[action_id] = entry
            catalog["actions"] = actions
            return dict(action), True
        return self._transaction(update)

    def actions(self, record: SavedProduction) -> tuple[Mapping[str, object], ...]:
        self._verify()
        entries = object_data(self._read()["actions"])
        return self._ordered_actions(entries, record)

    @staticmethod
    def _ordered_actions(entries: Mapping[str, object], record: SavedProduction) -> tuple[Mapping[str, object], ...]:
        values = [object_data(value) for value in entries.values()]
        sequences = [value.get("sequence") for value in values]
        if (any(type(seq) is not int or seq < 1 for seq in sequences)
                or len(set(sequences)) != len(sequences)):
            raise ValueError("R4_CATALOG_INTEGRITY")
        values.sort(key=lambda value: int(str(value["sequence"])))
        return tuple(object_data(value["action"]) for value in values
                     if value.get("record_sha256") == record.sha256)

    def read_version(self, *, conversation_id: str, production_ref: str,
                     version_ref: str) -> ProductionReadView | None:
        try:
            view = self.load(production_ref, version_ref).view
        except ValueError as error:
            if str(error) == "R4_NOT_FOUND":
                return None
            raise
        if not isinstance(view, ProductionReadView):
            return None
        return view if view.conversation_id == conversation_id else None

    def contains_production(self, *, conversation_id: str, production_ref: str) -> bool:
        return any(r.production_ref == production_ref and r.view.conversation_id == conversation_id
                   for r in self.list_versions())
