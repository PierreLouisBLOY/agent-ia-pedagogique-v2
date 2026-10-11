from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path

from backend.adapters.outbound.persistence.migrations import (
    CANONICAL_SEED_SHA256,
    MigrationRegistry,
    apply_registered_migrations,
    create_runtime_backup,
    inspect_database,
    inspect_migration_history,
    migration_registry,
)
from backend.infrastructure.filesystem import (
    LocalFileSecurityError,
    assert_local_data_root,
    atomic_publish_fresh,
    capture_secure_path,
    ensure_private_directory,
    harden_private_file,
    hash_file_nofollow,
    inspect_permission_status,
    private_temporary_file,
    read_file_nofollow,
    resolve_secure_path,
)
from backend.modules.local_provisioning.application.contracts import (
    MigrationExpectation,
    ProvisioningTargetInspectionResult,
    RuntimeMigrationState,
    SeedCandidate,
    SeedExpectation,
    SeedInspection,
)

_MAX_SCAN_DEPTH = 8
_MAX_SCAN_ENTRIES = 50_000
_CANDIDATE_SUFFIXES = {".sqlite", ".sqlite3", ".db"}
_CONFIG_NAMES = (
    "PROJET_V2_DATA_DIR",
    "PROJET_V2_CANONICAL_DB",
    "PROJET_V2_RUNTIME_DB",
)


class LocalProvisioningAdapter:
    """Filesystem/SQLite adapter for the trusted local Application use cases."""

    def __init__(self, *, repository_root: Path, old_data_root: Path) -> None:
        self._repository_root = repository_root.resolve()
        self._old_data_root = old_data_root.resolve()

    def inspect_target(
        self, data_root: Path, project_identity: str
    ) -> ProvisioningTargetInspectionResult:
        safe_root = assert_local_data_root(data_root)
        if not safe_root.exists():
            return ProvisioningTargetInspectionResult(False, False, (), (), ())
        if not safe_root.is_dir():
            return ProvisioningTargetInspectionResult(
                True, False, (), (), ("DATA_ROOT_NOT_DIRECTORY",)
            )
        marker = safe_root / ".r5-root.json"
        marker_valid = False
        try:
            marker_snapshot = capture_secure_path(marker, allowed_root=safe_root)
            if marker_snapshot.is_file:
                payload = json.loads(
                    read_file_nofollow(marker, allowed_root=safe_root, maximum_bytes=4096)
                )
                marker_valid = payload == {
                    "schema": "R5-USER-DATA-ROOT-1.0",
                    "project_identity": project_identity,
                }
        except (FileNotFoundError, ValueError, json.JSONDecodeError, LocalFileSecurityError):
            marker_valid = False
        observed: list[str] = []
        findings: list[str] = []
        pending = [safe_root]
        remaining = _MAX_SCAN_ENTRIES
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    remaining -= 1
                    if remaining < 0:
                        raise ValueError("TARGET_INSPECTION_ENTRY_LIMIT_EXCEEDED")
                    path = Path(entry.path)
                    relative = path.relative_to(safe_root).as_posix()
                    try:
                        snapshot = capture_secure_path(path, allowed_root=safe_root)
                    except OSError:
                        findings.append("TARGET_CONTAINS_UNSAFE_ENTRY")
                        continue
                    observed.append(relative)
                    if snapshot.is_directory:
                        pending.append(path)
        return ProvisioningTargetInspectionResult(
            True,
            marker_valid,
            tuple(sorted(observed)),
            (),
            tuple(dict.fromkeys(findings)),
            (),
        )

    def discover_seed_candidates(
        self, roots: tuple[Path, ...], expectations: tuple[SeedExpectation, ...]
    ) -> tuple[SeedCandidate, ...]:
        by_size: dict[int, str] = {item.size_bytes: item.sha256 for item in expectations}
        observed: dict[str, SeedCandidate] = {}
        remaining = _MAX_SCAN_ENTRIES
        for root in roots:
            safe_root = assert_local_data_root(root)
            if not safe_root.exists():
                continue
            if safe_root == self._repository_root:
                raise ValueError("SEED_SEARCH_ROOT_INSIDE_REPOSITORY")
            pending: list[tuple[Path, int]] = [(safe_root, 0)]
            while pending:
                directory, depth = pending.pop()
                with os.scandir(directory) as entries:
                    for entry in entries:
                        remaining -= 1
                        if remaining < 0:
                            raise ValueError("SEED_SEARCH_ENTRY_LIMIT_EXCEEDED")
                        try:
                            entry_path = Path(entry.path)
                            snapshot = capture_secure_path(entry_path, allowed_root=safe_root)
                            if snapshot.is_directory:
                                if depth < _MAX_SCAN_DEPTH:
                                    pending.append((entry_path, depth + 1))
                                continue
                            if not snapshot.is_file:
                                continue
                            path = entry_path
                            if path.suffix.casefold() not in _CANDIDATE_SUFFIXES:
                                continue
                            if snapshot.size_bytes not in by_size:
                                continue
                            digest = hash_file_nofollow(path, allowed_root=safe_root)
                            expected = next(
                                (item for item in expectations if item.sha256 == digest), None
                            )
                            if expected is None or expected.size_bytes != snapshot.size_bytes:
                                continue
                            key = os.path.normcase(str(path.resolve()))
                            observed[key] = SeedCandidate(path, digest, expected.size_bytes)
                        except OSError:
                            raise ValueError("SEED_SEARCH_READ_FAILED") from None
        return tuple(observed[key] for key in sorted(observed))

    def measure_seed_file(self, path: Path, allowed_root: Path) -> SeedCandidate | None:
        safe_root = assert_local_data_root(allowed_root)
        if path.suffix.casefold() not in _CANDIDATE_SUFFIXES:
            return None
        try:
            snapshot = capture_secure_path(path, allowed_root=safe_root)
        except FileNotFoundError:
            return None
        if not snapshot.is_file:
            return None
        digest = hash_file_nofollow(path, allowed_root=safe_root)
        return SeedCandidate(path, digest, snapshot.size_bytes)

    def authenticate_seed(
        self, candidate: SeedCandidate, expectation: SeedExpectation
    ) -> SeedInspection:
        if candidate.sha256 != expectation.sha256 or candidate.size_bytes != expectation.size_bytes:
            raise ValueError("SEED_EXPECTATION_MISMATCH")
        if expectation.sha256 != CANONICAL_SEED_SHA256:
            return SeedInspection(candidate, False, "NOT_OPENED", "NOT_OPENED", 0, 0, 0, 0, 0)
        source_root = candidate.path.parent
        snapshot = capture_secure_path(candidate.path, allowed_root=source_root)
        if not snapshot.is_file or snapshot.size_bytes != expectation.size_bytes:
            raise ValueError("SEED_SOURCE_CHANGED")
        if hash_file_nofollow(candidate.path, allowed_root=source_root) != expectation.sha256:
            raise ValueError("SEED_SOURCE_CHANGED")
        permission = inspect_permission_status(
            candidate.path, allowed_root=source_root, external_readonly=True
        )
        if permission.value == "EXCESSIVE_WRITE":
            raise ValueError("SEED_SOURCE_WRITABLE")
        evidence = inspect_database(candidate.path, authenticate_seed=True)
        return SeedInspection(
            candidate,
            evidence.sha256 == expectation.sha256,
            evidence.integrity,
            evidence.quick,
            evidence.foreign_key_violations,
            evidence.tables,
            evidence.explicit_indexes,
            evidence.triggers,
            evidence.views,
        )

    def validate_migration_sources(self, migrations: tuple[MigrationExpectation, ...]) -> bool:
        self._registry(migrations)
        return True

    def inspect_runtime(
        self, path: Path, migrations: tuple[MigrationExpectation, ...]
    ) -> RuntimeMigrationState:
        if not path.exists():
            return RuntimeMigrationState(False, None, None, (), None, None, None)
        registry = self._registry(migrations)
        evidence = inspect_database(path)
        history = inspect_migration_history(path, registry)
        marker = path.with_name(path.name + ".r5-provenance.json")
        seed_sha256 = None
        if marker.exists():
            raw = read_file_nofollow(marker, allowed_root=path.parent.parent, maximum_bytes=4096)
            provenance = json.loads(raw)
            if provenance.get("schema") != "R5-RUNTIME-PROVENANCE-1.0":
                raise ValueError("RUNTIME_PROVENANCE_INVALID")
            seed_sha256 = provenance.get("seed_sha256")
        return RuntimeMigrationState(
            True,
            evidence.sha256,
            seed_sha256,
            history,
            evidence.integrity,
            evidence.quick,
            evidence.foreign_key_violations,
        )

    def create_data_root(self, path: Path) -> bool:
        safe = assert_local_data_root(path)
        if (
            safe == self._old_data_root
            or safe.is_relative_to(self._old_data_root)
            or self._old_data_root.is_relative_to(safe)
        ):
            raise ValueError("NEW_DATA_ROOT_OVERLAPS_OLD_ROOT")
        if safe == self._repository_root or safe.is_relative_to(self._repository_root):
            raise ValueError("DATA_ROOT_INSIDE_REPOSITORY")
        marker = safe / ".r5-root.json"
        if safe.exists():
            if not marker.exists():
                raise ValueError("EXISTING_DATA_ROOT_UNVERIFIED")
            data = json.loads(read_file_nofollow(marker, allowed_root=safe, maximum_bytes=4096))
            if data != {
                "schema": "R5-USER-DATA-ROOT-1.0",
                "project_identity": "agent-ia-pedagogique-v2",
            }:
                raise ValueError("EXISTING_DATA_ROOT_MARKER_INVALID")
            return False
        ensure_private_directory(safe, allowed_root=safe)
        marker_temp = private_temporary_file(
            safe, allowed_root=safe, prefix=".r5-root-", suffix=".tmp"
        )
        try:
            marker_temp.write_text(
                json.dumps(
                    {
                        "schema": "R5-USER-DATA-ROOT-1.0",
                        "project_identity": "agent-ia-pedagogique-v2",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            harden_private_file(marker_temp, allowed_root=safe)
            atomic_publish_fresh(marker_temp, marker, allowed_root=safe)
        finally:
            marker_temp.unlink(missing_ok=True)
        return True

    def copy_reference_seed(
        self, source: SeedInspection, target: Path, expected_sha256: str
    ) -> str:
        if not source.authenticated or source.candidate.sha256 != expected_sha256:
            raise ValueError("AUTHENTICATED_SEED_REQUIRED")
        root = target.parent.parent
        ensure_private_directory(target.parent, allowed_root=root)
        if target.exists():
            digest = hash_file_nofollow(target, allowed_root=root)
            if digest != expected_sha256:
                raise ValueError("REFERENCE_TARGET_COLLISION")
            marker_path = root / ".r5-root.json"
            marker = json.loads(
                read_file_nofollow(marker_path, allowed_root=root, maximum_bytes=4096)
            )
            if marker != {
                "schema": "R5-USER-DATA-ROOT-1.0",
                "project_identity": "agent-ia-pedagogique-v2",
            }:
                raise ValueError("EXISTING_DATA_ROOT_MARKER_INVALID")
            with os.scandir(target.parent) as entries:
                for entry in entries:
                    if not (entry.name.startswith(".seed-copy-") and entry.name.endswith(".tmp")):
                        continue
                    temporary = Path(entry.path)
                    snapshot = capture_secure_path(temporary, allowed_root=root)
                    if not snapshot.is_file:
                        raise ValueError("INTERRUPTED_SEED_COPY_TEMPORARY_INVALID")
                    # The verified target is the complete canonical copy. A named temporary
                    # in this newly provisioned reference directory is an interrupted copy,
                    # so it can be removed only after target identity and root marker pass.
                    if not snapshot.same_state(capture_secure_path(temporary, allowed_root=root)):
                        raise ValueError("INTERRUPTED_SEED_COPY_TEMPORARY_CHANGED")
                    os.chmod(temporary, stat.S_IREAD | stat.S_IWRITE)
                    temporary.unlink()
            harden_private_file(target, allowed_root=root)
            os.chmod(target, stat.S_IREAD)
            return digest
        if (
            hash_file_nofollow(source.candidate.path, allowed_root=source.candidate.path.parent)
            != expected_sha256
        ):
            raise ValueError("SEED_SOURCE_CHANGED")
        temporary = private_temporary_file(
            target.parent, allowed_root=root, prefix=".seed-copy-", suffix=".tmp"
        )
        try:
            shutil.copy2(source.candidate.path, temporary)
            if hash_file_nofollow(temporary, allowed_root=root) != expected_sha256:
                raise ValueError("REFERENCE_COPY_AUTHENTICATION_FAILED")
            harden_private_file(temporary, allowed_root=root)
            atomic_publish_fresh(temporary, target, allowed_root=root)
            os.chmod(target, stat.S_IREAD)
        finally:
            temporary.unlink(missing_ok=True)
        return hash_file_nofollow(target, allowed_root=root)

    def create_runtime_from_reference(
        self, reference: Path, runtime: Path, expected_sha256: str
    ) -> str:
        root = runtime.parent.parent
        ensure_private_directory(runtime.parent, allowed_root=root)
        if runtime.exists():
            raise ValueError("RUNTIME_TARGET_ALREADY_EXISTS")
        if hash_file_nofollow(reference, allowed_root=root) != expected_sha256:
            raise ValueError("REFERENCE_SEED_CHANGED")
        temporary = private_temporary_file(
            runtime.parent, allowed_root=root, prefix=".runtime-copy-", suffix=".tmp"
        )
        try:
            shutil.copy2(reference, temporary)
            os.chmod(temporary, stat.S_IREAD | stat.S_IWRITE)
            harden_private_file(temporary, allowed_root=root)
            if hash_file_nofollow(temporary, allowed_root=root) != expected_sha256:
                raise ValueError("RUNTIME_COPY_AUTHENTICATION_FAILED")
            atomic_publish_fresh(temporary, runtime, allowed_root=root)
        finally:
            temporary.unlink(missing_ok=True)
        runtime_hash = hash_file_nofollow(runtime, allowed_root=root)
        marker = runtime.with_name(runtime.name + ".r5-provenance.json")
        marker_temp = private_temporary_file(
            runtime.parent,
            allowed_root=root,
            prefix=".runtime-provenance-",
            suffix=".tmp",
        )
        payload = (
            json.dumps(
                {
                    "schema": "R5-RUNTIME-PROVENANCE-1.0",
                    "seed_sha256": expected_sha256,
                    "initial_runtime_sha256": runtime_hash,
                },
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        try:
            marker_temp.write_bytes(payload)
            harden_private_file(marker_temp, allowed_root=root)
            atomic_publish_fresh(marker_temp, marker, allowed_root=root)
        finally:
            marker_temp.unlink(missing_ok=True)
        return runtime_hash

    def create_backup(
        self, runtime: Path, backup: Path, reference: Path, migration_version: str
    ) -> str:
        root = runtime.parent.parent
        ensure_private_directory(backup.parent, allowed_root=root)
        if backup.exists():
            evidence = inspect_database(backup)
            manifest_path = backup.with_name(backup.name + ".manifest.json")
            payload = json.loads(
                read_file_nofollow(manifest_path, allowed_root=root, maximum_bytes=4096)
            )
            if payload.get("backup_sha256") != evidence.sha256:
                raise ValueError("BACKUP_MANIFEST_MISMATCH")
            if payload.get("migration_version") != migration_version:
                raise ValueError("BACKUP_MIGRATION_VERSION_MISMATCH")
            return evidence.sha256
        report = create_runtime_backup(
            runtime,
            backup,
            migration_version=migration_version,
            data_root=root,
            canonical_seed_path=reference,
        )
        return report.backup_sha256

    def inspect_backup(
        self,
        backup: Path,
        migrations: tuple[MigrationExpectation, ...],
        expected_migration_version: str,
    ) -> str | None:
        if not backup.exists():
            return None
        root = backup.parent.parent
        evidence = inspect_database(backup)
        manifest_path = backup.with_name(backup.name + ".manifest.json")
        payload = json.loads(read_file_nofollow(manifest_path, allowed_root=root, maximum_bytes=4096))
        if payload.get("schema_version") != "runtime-backup-v1":
            raise ValueError("BACKUP_MANIFEST_INVALID")
        if payload.get("backup_sha256") != evidence.sha256:
            raise ValueError("BACKUP_MANIFEST_MISMATCH")
        if payload.get("migration_version") != expected_migration_version:
            raise ValueError("BACKUP_MIGRATION_VERSION_MISMATCH")
        registry = self._registry(migrations)
        if inspect_migration_history(backup, registry):
            raise ValueError("PRE_MIGRATION_BACKUP_CONTAINS_MIGRATIONS")
        return evidence.sha256

    def apply_migrations(
        self, runtime: Path, migrations: tuple[MigrationExpectation, ...]
    ) -> tuple[str, ...]:
        registry = self._registry(migrations)
        result = apply_registered_migrations(runtime, registry)
        return result.applied

    def create_library_root(self, path: Path) -> bool:
        root = path.parent
        ensure_private_directory(path, allowed_root=root)
        probe = path / ".r5-write-probe"
        try:
            with probe.open("xb") as stream:
                stream.write(b"R5")
                stream.flush()
                os.fsync(stream.fileno())
            if probe.read_bytes() != b"R5":
                return False
        finally:
            probe.unlink(missing_ok=True)
        return True

    def read_user_config(self, names: tuple[str, ...]) -> tuple[tuple[str, str | None], ...]:
        if os.name != "nt":
            raise ValueError("WINDOWS_USER_CONFIG_REQUIRED")
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as key:
                values: dict[str, str | None] = {}
                for name in names:
                    try:
                        values[name] = str(winreg.QueryValueEx(key, name)[0])
                    except FileNotFoundError:
                        values[name] = None
        except FileNotFoundError:
            values = {name: None for name in names}
        return tuple((name, values[name]) for name in names)

    def write_user_config(self, values: tuple[tuple[str, str | None], ...]) -> None:
        if os.name != "nt":
            raise ValueError("WINDOWS_USER_CONFIG_REQUIRED")
        import winreg

        if {name for name, _ in values} != set(_CONFIG_NAMES):
            raise ValueError("USER_CONFIG_FIELDS_INVALID")
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
        ) as key:
            for name, value in values:
                if value is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                    os.environ.pop(name, None)
                else:
                    winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
                    os.environ[name] = value
        try:
            ctypes.windll.user32.SendMessageTimeoutW(
                0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None
            )
        except (AttributeError, OSError):
            pass

    def snapshot_old_root(self, path: Path) -> str:
        root = assert_local_data_root(path)
        if not root.exists():
            return "MISSING"
        digest = hashlib.sha256()
        count = 0
        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            safe_current = resolve_secure_path(current_path, allowed_root=root)
            dirs[:] = sorted(name for name in dirs if not (current_path / name).is_symlink())
            for name in sorted(files):
                file_path = current_path / name
                snapshot = capture_secure_path(file_path, allowed_root=safe_current)
                if not snapshot.is_file:
                    continue
                file_hash = hash_file_nofollow(file_path, allowed_root=safe_current)
                relative = file_path.relative_to(root).as_posix()
                digest.update(relative.encode("utf-8", "surrogatepass"))
                digest.update(b"\0")
                digest.update(str(snapshot.size_bytes).encode("ascii"))
                digest.update(b"\0")
                digest.update(file_hash.encode("ascii"))
                digest.update(b"\n")
                count += 1
                if count > _MAX_SCAN_ENTRIES:
                    raise ValueError("OLD_ROOT_INVENTORY_LIMIT_EXCEEDED")
        return digest.hexdigest()

    @staticmethod
    def _registry(migrations: tuple[MigrationExpectation, ...]) -> MigrationRegistry:
        if len(migrations) != 2 or tuple(item.version for item in migrations) != ("001", "002"):
            raise ValueError("APPROVED_MIGRATION_SEQUENCE_REQUIRED")
        for item in migrations:
            if (
                hash_file_nofollow(item.source_path, allowed_root=item.source_path.parent)
                != item.sha256
            ):
                raise ValueError("MIGRATION_HASH_MISMATCH")
        registry = migration_registry(migrations[0].source_path)
        if tuple(spec.checksum for spec in registry.specs) != tuple(
            item.sha256 for item in migrations
        ):
            raise ValueError("MIGRATION_REGISTRY_MISMATCH")
        return registry
