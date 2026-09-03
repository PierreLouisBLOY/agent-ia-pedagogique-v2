# Phase 12.17.4E-B08 — Identité seed PRE/POST

Le snapshot PRE a été capturé avant toute ouverture SQLite. Toutes les lectures
ont utilisé `mode=ro&immutable=1` et `PRAGMA query_only=ON`.

| Preuve | PRE | POST | Verdict |
|---|---:|---:|---|
| taille | 105553920 | 105553920 | identique |
| SHA-256 | `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` | identique | PASS |
| mtime UTC | `2026-08-22T00:13:57.5500000Z` | identique | PASS |
| inventaire | 98/20/7/2 | 98/20/7/2 | PASS |
| integrity/quick/FK | ok/ok/0 | ok/ok/0 | PASS |

```text
SEED_MAIN_FILE_MUTATED = FALSE
SEED_MIGRATIONS = 0
SEED_DDL_DML = 0
SEED_PRE_POST_BYTE_IDENTITY = TRUE
```
