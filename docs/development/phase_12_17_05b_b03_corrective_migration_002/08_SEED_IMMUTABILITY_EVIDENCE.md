# Phase 12.17.5B-B03 — Immutabilité du seed

| Élément | PRE | POST | Verdict |
|---|---|---|---|
| fichier principal | taille `105553920`, SHA `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` | identique | PASS |
| WAL | taille `0`, SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | identique | PASS |
| SHM | taille `32768`, SHA `fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb` | identique | PASS |
| journal | absent | absent | PASS |

L'accès seed a été limité au hash filesystem, à l'introspection DDL `mode=ro` et à la lecture immuable utilisée pour fabriquer une copie temporaire. La migration a été appliquée uniquement à des fichiers temporaires hors du repository.

```text
SEED_ACCESSED = TRUE_READ_ONLY
SEED_MODIFIED = FALSE
USER_RUNTIME_ACCESSED = FALSE
USER_RUNTIME_MODIFIED = FALSE
USER_RUNTIME_002_APPLIED = FALSE
```
