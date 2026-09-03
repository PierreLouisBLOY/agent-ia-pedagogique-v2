from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from backend.infrastructure.composition.factories import sqlite as sqlite_factory
from backend.infrastructure.config.loaders.sqlite import (
    CANONICAL_DB_ENV,
    DATA_DIR_ENV,
    LEGACY_RUNTIME_PATH_ENV,
    LEGACY_SEED_PATH_ENV,
    RUNTIME_DB_ENV,
    USER_HOME_ENV,
    WINDOWS_DATA_HOME_ENV,
    XDG_DATA_HOME_ENV,
    load_sqlite_paths,
)
from backend.infrastructure.config.schemas.sqlite import (
    SQLiteDatabasePaths,
    SQLitePathConfigurationError,
    SQLitePathErrorCode,
)


def test_windows_default_uses_os_local_app_data(tmp_path: Path) -> None:
    paths = load_sqlite_paths(
        {WINDOWS_DATA_HOME_ENV: str(tmp_path)}, platform_name="win32"
    )

    root = tmp_path / "ProjetV2"
    assert paths.data_directory == root
    assert paths.canonical_seed_path == root / "seed" / "base_pedagogique_v2.sqlite"
    assert paths.runtime_database_path == (
        root / "runtime" / "base_pedagogique_v2.runtime.sqlite"
    )


def test_non_windows_default_prefers_xdg_data_home(tmp_path: Path) -> None:
    paths = load_sqlite_paths(
        {XDG_DATA_HOME_ENV: str(tmp_path)}, platform_name="linux"
    )

    assert paths.data_directory == tmp_path / "ProjetV2"


def test_non_windows_default_falls_back_to_injected_home(tmp_path: Path) -> None:
    paths = load_sqlite_paths({USER_HOME_ENV: str(tmp_path)}, platform_name="linux")

    assert paths.data_directory == tmp_path / ".local" / "share" / "ProjetV2"


def test_macos_default_uses_application_support(tmp_path: Path) -> None:
    paths = load_sqlite_paths({USER_HOME_ENV: str(tmp_path)}, platform_name="darwin")

    assert paths.data_directory == (
        tmp_path / "Library" / "Application Support" / "ProjetV2"
    )


def test_explicit_data_root_derives_non_repository_subdirectories(tmp_path: Path) -> None:
    paths = load_sqlite_paths({DATA_DIR_ENV: str(tmp_path)}, platform_name="simulated")

    assert paths.imports_directory == tmp_path / "imports"
    assert paths.exports_directory == tmp_path / "exports"
    assert paths.logs_directory == tmp_path / "logs"
    assert paths.backups_directory == tmp_path / "backups"
    assert paths.runtime_directory == tmp_path / "runtime"


def test_legacy_names_remain_accepted_during_compatibility_window(tmp_path: Path) -> None:
    seed = tmp_path / "external-seed.sqlite"
    runtime = tmp_path / "external-runtime.sqlite"
    paths = load_sqlite_paths(
        {
            DATA_DIR_ENV: str(tmp_path),
            LEGACY_SEED_PATH_ENV: str(seed),
            LEGACY_RUNTIME_PATH_ENV: str(runtime),
        }
    )

    assert paths.canonical_seed_path == seed
    assert paths.runtime_database_path == runtime


def test_equal_new_and_legacy_values_are_accepted(tmp_path: Path) -> None:
    seed = tmp_path / "seed.sqlite"
    runtime = tmp_path / "runtime.sqlite"
    paths = load_sqlite_paths(
        {
            DATA_DIR_ENV: str(tmp_path),
            CANONICAL_DB_ENV: str(seed),
            LEGACY_SEED_PATH_ENV: str(seed),
            RUNTIME_DB_ENV: str(runtime),
            LEGACY_RUNTIME_PATH_ENV: str(runtime),
        }
    )

    assert paths.canonical_seed_path == seed
    assert paths.runtime_database_path == runtime


@pytest.mark.parametrize(
    ("new_name", "legacy_name"),
    (
        (CANONICAL_DB_ENV, LEGACY_SEED_PATH_ENV),
        (RUNTIME_DB_ENV, LEGACY_RUNTIME_PATH_ENV),
    ),
)
def test_different_new_and_legacy_values_fail_closed(
    tmp_path: Path, new_name: str, legacy_name: str
) -> None:
    environment = {
        DATA_DIR_ENV: str(tmp_path),
        new_name: str(tmp_path / "new.sqlite"),
        legacy_name: str(tmp_path / "legacy.sqlite"),
    }

    with pytest.raises(SQLitePathConfigurationError) as raised:
        load_sqlite_paths(environment)

    assert raised.value.code is SQLitePathErrorCode.LEGACY_SETTING_CONFLICT


def test_empty_or_relative_settings_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(SQLitePathConfigurationError) as empty:
        load_sqlite_paths({DATA_DIR_ENV: ""})
    with pytest.raises(SQLitePathConfigurationError) as relative:
        load_sqlite_paths({DATA_DIR_ENV: str(tmp_path), CANONICAL_DB_ENV: "seed.sqlite"})

    assert empty.value.code is SQLitePathErrorCode.EMPTY_SETTING
    assert relative.value.code is SQLitePathErrorCode.RELATIVE_PATH


def test_seed_and_runtime_cannot_resolve_to_the_same_path(tmp_path: Path) -> None:
    database = tmp_path / "database.sqlite"

    with pytest.raises(SQLitePathConfigurationError) as raised:
        load_sqlite_paths(
            {
                DATA_DIR_ENV: str(tmp_path),
                CANONICAL_DB_ENV: str(database),
                RUNTIME_DB_ENV: str(database),
            }
        )

    assert raised.value.code is SQLitePathErrorCode.SEED_RUNTIME_COLLISION


def test_file_identity_aliases_cover_symlink_or_junction_convergence(
    tmp_path: Path,
) -> None:
    seed = tmp_path / "seed.identity"
    alias = tmp_path / "runtime-alias.identity"
    seed.write_bytes(b"identity-only-test")
    os.link(seed, alias)

    with pytest.raises(SQLitePathConfigurationError) as raised:
        SQLiteDatabasePaths(seed, alias, data_directory=tmp_path)

    assert raised.value.code is SQLitePathErrorCode.SEED_RUNTIME_COLLISION


def test_configuration_errors_never_disclose_local_path_values(tmp_path: Path) -> None:
    private_seed = tmp_path / "private-user-seed.sqlite"
    private_legacy = tmp_path / "different-private-seed.sqlite"

    with pytest.raises(SQLitePathConfigurationError) as raised:
        load_sqlite_paths(
            {
                DATA_DIR_ENV: str(tmp_path),
                CANONICAL_DB_ENV: str(private_seed),
                LEGACY_SEED_PATH_ENV: str(private_legacy),
            }
        )

    rendered = str(raised.value)
    assert str(tmp_path) not in rendered
    assert private_seed.name not in rendered
    assert private_legacy.name not in rendered


def test_composition_consumes_the_injected_portable_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = object()
    captured: list[tuple[SQLiteDatabasePaths, Path]] = []

    def fake_build(
        paths: SQLiteDatabasePaths, migration_path: Path
    ) -> sqlite_factory.SQLiteRuntimeComposition:
        captured.append((paths, migration_path))
        return cast(sqlite_factory.SQLiteRuntimeComposition, sentinel)

    monkeypatch.setattr(sqlite_factory, "build_sqlite_runtime", fake_build)
    migration = tmp_path / "migration.sql"
    result = sqlite_factory.build_configured_sqlite_runtime(
        {DATA_DIR_ENV: str(tmp_path)}, migration, platform_name="simulated"
    )

    assert result is sentinel
    assert captured[0][0].data_directory == tmp_path
    assert captured[0][1] == migration
