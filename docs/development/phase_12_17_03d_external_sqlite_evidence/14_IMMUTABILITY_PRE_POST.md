# Phase 12.17.3D — PRE/POST immutability

Target:

`<CANONICAL_SEED_PATH>`

| Snapshot | Size | SHA-256 | mtime UTC |
|---|---:|---|---|
| PRE | `105553920` | `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` | `2026-08-22T00:13:57.5500000Z` |
| POST | `105553920` | `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` | `2026-08-22T00:13:57.5500000Z` |

```text
PRE_POST_SIZE = IDENTICAL
PRE_POST_SHA256 = IDENTICAL
PRE_POST_MTIME = IDENTICAL
FILE_MOVED = NO
FILE_COPIED = NO
FILE_MUTATED = NO
PRE_POST_IMMUTABILITY = PASS
```

The PASS applies to the authenticated main database required by the contract.

## Auxiliary-file limitation

No sidecar PRE snapshot was captured. At POST:

| Auxiliary file | Size | SHA-256 | mtime UTC | creation UTC |
|---|---:|---|---|---|
| `01_base_pedagogique_v2.sqlite-wal` | `0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `2026-08-28T09:32:55.5450000Z` | `2026-09-02T15:58:28.5397440Z` |
| `01_base_pedagogique_v2.sqlite-shm` | `32768` | `fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb` | `2026-09-01T09:50:02.0070000Z` | `2026-09-02T15:58:28.7273743Z` |

```text
AUXILIARY_FILES_PRE_STATE = NOT_CAPTURED
AUXILIARY_FILES_POST_STATE = WAL_EMPTY_AND_SHM_PRESENT
AUXILIARY_CREATION_ATTRIBUTION = UNDETERMINED_WITHOUT_PRE_SNAPSHOT
RUNTIME_DATABASE_CREATED = NO
```

The sidecars were not deleted or altered because their provenance was not established.
