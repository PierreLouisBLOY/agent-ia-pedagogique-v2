"""Typed, redaction-safe local paths for seed and runtime databases."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from backend.infrastructure.filesystem import (
    LocalFileSecurityCode,
    LocalFileSecurityError,
    assert_distinct_paths,
    assert_local_data_root,
    resolve_secure_path,
)


class SQLitePathErrorCode(StrEnum):
    MISSING_OS_DATA_DIRECTORY = "MISSING_OS_DATA_DIRECTORY"
    EMPTY_SETTING = "EMPTY_SETTING"
    LEGACY_SETTING_FORBIDDEN = "LEGACY_SETTING_FORBIDDEN"
    RELATIVE_PATH = "RELATIVE_PATH"
    PATH_RESOLUTION_FAILED = "PATH_RESOLUTION_FAILED"
    SEED_RUNTIME_COLLISION = "SEED_RUNTIME_COLLISION"
    NON_LOCAL_DATA_DIRECTORY = "NON_LOCAL_DATA_DIRECTORY"
    RUNTIME_OUTSIDE_DATA_DIRECTORY = "RUNTIME_OUTSIDE_DATA_DIRECTORY"
    PATH_REDIRECTION_FORBIDDEN = "PATH_REDIRECTION_FORBIDDEN"


class SQLitePathConfigurationError(ValueError):
    """Closed configuration error that never includes a local path value."""

    def __init__(self, code: SQLitePathErrorCode) -> None:
        if not isinstance(code, SQLitePathErrorCode):
            raise TypeError("code must be a SQLitePathErrorCode")
        self.code = code
        super().__init__(f"SQLite path configuration failed: {code.value}")


def _resolve_absolute(path: Path) -> Path:
    if not isinstance(path, Path):
        raise TypeError("SQLite paths must be pathlib.Path values")
    if not path.is_absolute():
        raise SQLitePathConfigurationError(SQLitePathErrorCode.RELATIVE_PATH)
    return path


def _secure_data_root(path: Path) -> Path:
    try:
        return assert_local_data_root(path)
    except LocalFileSecurityError as error:
        code = (
            SQLitePathErrorCode.NON_LOCAL_DATA_DIRECTORY
            if error.code
            in {LocalFileSecurityCode.NETWORK_PATH, LocalFileSecurityCode.NON_LOCAL_ROOT}
            else SQLitePathErrorCode.PATH_REDIRECTION_FORBIDDEN
            if error.code is LocalFileSecurityCode.PATH_REDIRECTION_FORBIDDEN
            else SQLitePathErrorCode.PATH_RESOLUTION_FAILED
        )
        raise SQLitePathConfigurationError(code) from error


def _secure_runtime(path: Path, *, data_root: Path) -> Path:
    try:
        return resolve_secure_path(path, allowed_root=data_root)
    except LocalFileSecurityError as error:
        code = (
            SQLitePathErrorCode.RUNTIME_OUTSIDE_DATA_DIRECTORY
            if error.code is LocalFileSecurityCode.OUTSIDE_ALLOWED_ROOT
            else SQLitePathErrorCode.PATH_REDIRECTION_FORBIDDEN
            if error.code is LocalFileSecurityCode.PATH_REDIRECTION_FORBIDDEN
            else SQLitePathErrorCode.PATH_RESOLUTION_FAILED
        )
        raise SQLitePathConfigurationError(code) from error


def _secure_seed(path: Path) -> Path:
    try:
        return resolve_secure_path(path, allowed_root=path.parent)
    except LocalFileSecurityError as error:
        code = (
            SQLitePathErrorCode.PATH_REDIRECTION_FORBIDDEN
            if error.code is LocalFileSecurityCode.PATH_REDIRECTION_FORBIDDEN
            else SQLitePathErrorCode.PATH_RESOLUTION_FAILED
        )
        raise SQLitePathConfigurationError(code) from error


def _assert_distinct(seed: Path, runtime: Path) -> None:
    try:
        assert_distinct_paths(seed, runtime)
    except LocalFileSecurityError as error:
        if error.code is LocalFileSecurityCode.PATH_COLLISION:
            raise SQLitePathConfigurationError(
                SQLitePathErrorCode.SEED_RUNTIME_COLLISION
            ) from error
        raise SQLitePathConfigurationError(
            SQLitePathErrorCode.PATH_RESOLUTION_FAILED
        ) from error


@dataclass(frozen=True, slots=True, init=False)
class SQLiteDatabasePaths:
    data_directory: Path
    canonical_seed_path: Path
    runtime_database_path: Path

    def __init__(
        self,
        canonical_seed_path: Path,
        runtime_database_path: Path,
        *,
        data_directory: Path | None = None,
    ) -> None:
        """Build resolved paths while retaining the two-argument legacy API."""

        unresolved_seed = _resolve_absolute(canonical_seed_path)
        unresolved_runtime = _resolve_absolute(runtime_database_path)
        unresolved_root = _resolve_absolute(
            runtime_database_path.parent if data_directory is None else data_directory
        )
        root = _secure_data_root(unresolved_root)
        seed = _secure_seed(unresolved_seed)
        runtime = _secure_runtime(unresolved_runtime, data_root=root)
        _assert_distinct(seed, runtime)
        object.__setattr__(self, "data_directory", root)
        object.__setattr__(self, "canonical_seed_path", seed)
        object.__setattr__(self, "runtime_database_path", runtime)

    @property
    def imports_directory(self) -> Path:
        return self.data_directory / "imports"

    @property
    def exports_directory(self) -> Path:
        return self.data_directory / "exports"

    @property
    def logs_directory(self) -> Path:
        return self.data_directory / "logs"

    @property
    def backups_directory(self) -> Path:
        return self.data_directory / "backups"

    @property
    def runtime_directory(self) -> Path:
        return self.data_directory / "runtime"
