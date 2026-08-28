"""Typed local paths for canonical seed provisioning and runtime use."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SQLiteDatabasePaths:
    canonical_seed_path: Path
    runtime_database_path: Path
