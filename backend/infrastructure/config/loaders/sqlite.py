"""Environment loader for local SQLite paths; values are never committed."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from backend.infrastructure.config.schemas.sqlite import SQLiteDatabasePaths

SEED_PATH_ENV = "PEDAGOGICAL_CANONICAL_SEED_PATH"
RUNTIME_PATH_ENV = "PEDAGOGICAL_RUNTIME_DATABASE_PATH"


def load_sqlite_paths(environment: Mapping[str, str]) -> SQLiteDatabasePaths:
    try:
        seed = environment[SEED_PATH_ENV]
        runtime = environment[RUNTIME_PATH_ENV]
    except KeyError as error:
        raise ValueError(f"missing SQLite path setting: {error.args[0]}") from error
    if not seed or not runtime:
        raise ValueError("SQLite paths must be non-empty")
    return SQLiteDatabasePaths(Path(seed), Path(runtime))
