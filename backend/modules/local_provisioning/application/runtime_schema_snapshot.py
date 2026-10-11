"""Read-only schema metadata; no database rows or maintenance commands."""
from dataclasses import dataclass

SchemaScalar = str | int | None


@dataclass(frozen=True, slots=True)
class RuntimeSchemaObject:
    kind: str
    name: str
    table: str
    definition: str | None


@dataclass(frozen=True, slots=True)
class RuntimeTableMetadata:
    name: str
    columns: tuple[tuple[SchemaScalar, ...], ...]
    foreign_keys: tuple[tuple[SchemaScalar, ...], ...]
    indexes: tuple[tuple[SchemaScalar, ...], ...]


@dataclass(frozen=True, slots=True)
class RuntimeIndexMetadata:
    name: str
    columns: tuple[tuple[SchemaScalar, ...], ...]


@dataclass(frozen=True, slots=True)
class RuntimeSchemaSnapshot:
    source_sha256: str
    source_size: int
    source_device: int
    source_inode: int
    source_modified_ns: int
    schema_sha256: str
    objects: tuple[RuntimeSchemaObject, ...]
    tables: tuple[RuntimeTableMetadata, ...]
    indexes: tuple[RuntimeIndexMetadata, ...]
    connection_flags: tuple[tuple[str, str | int], ...]
    integrity: tuple[str, ...]
    quick_check: tuple[str, ...]
    foreign_key_violations: int
    absent_sidecars: tuple[str, ...]
    file_set: tuple["RuntimeFileMetadata", ...] = ()

@dataclass(frozen=True, slots=True)
class RuntimeFileMetadata:
    suffix: str
    exists: bool
    size: int
    device: int | None
    inode: int | None
    modified_ns: int | None
    sha256: str | None

def require_immutable_schema_file_set(files: tuple[RuntimeFileMetadata, ...]) -> None:
    """Read pinned main bytes without interpreting or modifying a WAL or SHM.

    Empty WAL plus standard-size SHM is admissible for an immutable schema read,
    never a declaration of writer quiescence or authorization to copy/migrate.
    """
    if tuple(row.suffix for row in files) != ("", "-wal", "-shm", "-journal"):
        raise ValueError("RUNTIME_SCHEMA_FILE_SET_REQUIRED")
    main, wal, shm, journal = files
    if not main.exists or main.sha256 is None:
        raise ValueError("RUNTIME_SCHEMA_EXISTING_FILE_REQUIRED")
    if journal.exists or (wal.exists and (
        wal.size != 0 or wal.sha256 !=
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )) or (shm.exists and (not wal.exists or shm.size != 32768)):
        raise ValueError("RUNTIME_SCHEMA_SIDECAR_PRESENT")
