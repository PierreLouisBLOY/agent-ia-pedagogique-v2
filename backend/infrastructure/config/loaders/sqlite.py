"""Environment loader for local SQLite paths; values are never committed."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from backend.infrastructure.config.schemas.sqlite import (
    SQLiteDatabasePaths,
    SQLitePathConfigurationError,
    SQLitePathErrorCode,
)

DATA_DIR_ENV = "PROJET_V2_DATA_DIR"
CANONICAL_DB_ENV = "PROJET_V2_CANONICAL_DB"
RUNTIME_DB_ENV = "PROJET_V2_RUNTIME_DB"
LEGACY_SEED_PATH_ENV = "PEDAGOGICAL_CANONICAL_SEED_PATH"
LEGACY_RUNTIME_PATH_ENV = "PEDAGOGICAL_RUNTIME_DATABASE_PATH"

# Compatibility aliases retained for existing conditional gates until B08.
SEED_PATH_ENV = LEGACY_SEED_PATH_ENV
RUNTIME_PATH_ENV = LEGACY_RUNTIME_PATH_ENV

WINDOWS_DATA_HOME_ENV = "LOCALAPPDATA"
XDG_DATA_HOME_ENV = "XDG_DATA_HOME"
USER_HOME_ENV = "HOME"


def _configured_path(environment: Mapping[str, str], setting: str) -> Path | None:
    if setting not in environment:
        return None
    value = environment[setting]
    if not isinstance(value, str):
        raise TypeError("environment values must be strings")
    if not value.strip():
        raise SQLitePathConfigurationError(SQLitePathErrorCode.EMPTY_SETTING)
    path = Path(value)
    if not path.is_absolute():
        raise SQLitePathConfigurationError(SQLitePathErrorCode.RELATIVE_PATH)
    return path


def _paths_are_equivalent(left: Path, right: Path) -> bool:
    try:
        resolved_left = left.resolve(strict=False)
        resolved_right = right.resolve(strict=False)
        if resolved_left == resolved_right:
            return True
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError as error:
        raise SQLitePathConfigurationError(
            SQLitePathErrorCode.PATH_RESOLUTION_FAILED
        ) from error


def _compatible_setting(
    environment: Mapping[str, str], new_name: str, legacy_name: str
) -> Path | None:
    current = _configured_path(environment, new_name)
    legacy = _configured_path(environment, legacy_name)
    if current is not None and legacy is not None and not _paths_are_equivalent(
        current, legacy
    ):
        raise SQLitePathConfigurationError(
            SQLitePathErrorCode.LEGACY_SETTING_CONFLICT
        )
    return current if current is not None else legacy


def _default_data_directory(
    environment: Mapping[str, str], platform_name: str
) -> Path:
    if platform_name.startswith("win"):
        base = _configured_path(environment, WINDOWS_DATA_HOME_ENV)
    elif platform_name == "darwin":
        home = _configured_path(environment, USER_HOME_ENV)
        base = None if home is None else home / "Library" / "Application Support"
    else:
        base = _configured_path(environment, XDG_DATA_HOME_ENV)
        if base is None:
            home = _configured_path(environment, USER_HOME_ENV)
            base = None if home is None else home / ".local" / "share"
    if base is None:
        raise SQLitePathConfigurationError(
            SQLitePathErrorCode.MISSING_OS_DATA_DIRECTORY
        )
    return base / "ProjetV2"


def load_sqlite_paths(
    environment: Mapping[str, str], *, platform_name: str | None = None
) -> SQLiteDatabasePaths:
    """Resolve portable defaults and strict legacy aliases from injected values."""

    selected_platform = sys.platform if platform_name is None else platform_name
    data_directory = _configured_path(environment, DATA_DIR_ENV)
    if data_directory is None:
        data_directory = _default_data_directory(environment, selected_platform)

    seed = _compatible_setting(environment, CANONICAL_DB_ENV, LEGACY_SEED_PATH_ENV)
    runtime = _compatible_setting(environment, RUNTIME_DB_ENV, LEGACY_RUNTIME_PATH_ENV)
    if seed is None:
        seed = data_directory / "seed" / "base_pedagogique_v2.sqlite"
    if runtime is None:
        runtime = data_directory / "runtime" / "base_pedagogique_v2.runtime.sqlite"
    return SQLiteDatabasePaths(seed, runtime, data_directory=data_directory)
