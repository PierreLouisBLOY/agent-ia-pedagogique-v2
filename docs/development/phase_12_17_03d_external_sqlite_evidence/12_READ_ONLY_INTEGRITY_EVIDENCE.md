# Phase 12.17.3D — Read-only integrity evidence

## Connection guards

The authenticated file was opened through Python SQLite with these equivalent read-only connection parameters:

```text
SQLITE_PATH = <CANONICAL_SEED_PATH>
READ_MODE = mode=ro&immutable=1
```

`PRAGMA query_only=ON` was executed immediately after connection.

```text
SQLITE_OPENED = YES_READ_ONLY
URI_MODE_RO = TRUE
URI_IMMUTABLE = TRUE
PRAGMA_QUERY_ONLY = 1
```

## Integrity and inventory

| Check | Expected | Observed | Result |
|---|---:|---:|---|
| `PRAGMA integrity_check` | `ok` | `ok` | PASS |
| `PRAGMA quick_check` | `ok` | `ok` | PASS |
| `PRAGMA foreign_key_check` violations | `0` | `0` | PASS |
| Tables | `98` | `98` | PASS |
| Explicit indexes | `20` | `20` | PASS |
| Triggers | `7` | `7` | PASS |
| Views | `2` | `2` | PASS |

SQLite also reports 111 implicit `sqlite_autoindex_*` entries, for 131 total index entries. The canonical `20` comparator is the repository-defined count of indexes whose `sqlite_schema.sql IS NOT NULL`, matching `DatabaseEvidence.explicit_indexes`.

No pedagogical table row was selected or exported. Integrity checks scanned the database as required but returned only integrity status; all other extracted information came from schema metadata and PRAGMAs.

## Auxiliary-file observation

At the POST snapshot, an empty `-wal` file and a 32768-byte `-shm` file were present. Their filesystem creation timestamps fall within the inspection window, while their preserved modification timestamps are older. Because the prompt required PRE snapshots only for the main database and no sidecar PRE snapshot was taken, their prior existence or creation by this inspection cannot be established conclusively. This limitation is recorded; neither sidecar demonstrates a change to the authenticated main database, whose size, SHA-256 and mtime stayed identical.
