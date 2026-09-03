"""Typed, redaction-safe local paths for seed and runtime databases."""

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SQLitePathErrorCode(StrEnum):
    MISSING_OS_DATA_DIRECTORY = "MISSING_OS_DATA_DIRECTORY"
    EMPTY_SETTING = "EMPTY_SETTING"
    RELATIVE_PATH = "RELATIVE_PATH"
    PATH_RESOLUTION_FAILED = "PATH_RESOLUTION_FAILED"
    LEGACY_SETTING_CONFLICT = "LEGACY_SETTING_CONFLICT"
    SEED_RUNTIME_COLLISION = "SEED_RUNTIME_COLLISION"


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
    try:
        return path.resolve(strict=False)
    except OSError as error:
        raise SQLitePathConfigurationError(
            SQLitePathErrorCode.PATH_RESOLUTION_FAILED
        ) from error


def _same_file(left: Path, right: Path) -> bool:
    if left == right:
        return True
    if not left.exists() or not right.exists():
        return False
    try:
        return os.path.samefile(left, right)
    except OSError as error:
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

        seed = _resolve_absolute(canonical_seed_path)
        runtime = _resolve_absolute(runtime_database_path)
        root = _resolve_absolute(
            runtime_database_path.parent if data_directory is None else data_directory
        )
        if _same_file(seed, runtime):
            raise SQLitePathConfigurationError(SQLitePathErrorCode.SEED_RUNTIME_COLLISION)
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
