# Phase 12.17.4E-B06 — Preuve SQLite et données

B06 concerne les vocabulaires SQLite mais pas le cycle de données. Les tests
portent sur des codecs purs ; le seed physique et toute base runtime sont restés
fermés. Le DDL authentifié antérieur est utilisé comme preuve carry-forward,
jamais comme autorité métier.

```text
CANONICAL_SEED_ACCESSED = 0
CANONICAL_SEED_MODIFIED = 0
RUNTIME_SQLITE_OPENED = 0
SQLITE_BINARY_ADDED = 0
MIGRATION_FILES_MODIFIED = 0
RESOURCE_MIGRATION_NEED = UNKNOWN
CONTEXT_ORIGIN_MIGRATION_NEED = UNKNOWN
```

Le store écrit désormais des valeurs fournies par les owners. Le default
physique `resource.identity_status=ACTIVE` n'est pas converti en décision
métier, et `ContextOrigin` n'est pas détourné vers `notes`.
