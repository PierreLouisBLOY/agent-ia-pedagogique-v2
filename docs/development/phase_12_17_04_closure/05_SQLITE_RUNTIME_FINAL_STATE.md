# Phase 12.17.4 — État final SQLite/runtime

```text
SEED_SHA256 = 38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134
SEED_SIZE_BYTES = 105553920
SEED_PRE_POST_BYTE_IDENTITY = TRUE
SEED_OPEN_MODE = ro+immutable+query_only
SEED_MIGRATIONS = 0
SEED_INTEGRITY_QUICK_FK = ok / ok / 0
RUNTIME_STATUS = VALIDATED_DISTINCT_AT_B08
RUNTIME_INTEGRITY_QUICK_FK = ok / ok / 0
RUNTIME_IDEMPOTENT_REPLAY = PASS
MIGRATION_001 = ALLOWLISTED_APPLIED_IDEMPOTENT
UNKNOWN_MIGRATIONS_APPLIED = 0
```

La runtime B08 était fraîche, distincte du seed et publiée atomiquement. Son
second bootstrap a conservé hash et mtime. Cette clôture confirme la preuve B08
sans affirmer qu'un processus ou fichier runtime est actuellement actif.

Les sidecars seed WAL (0 octet, hash vide) et SHM (32 768 octets,
`fd4c9fda...9389eb`) préexistaient et sont identiques PRE/POST. Leur créateur
historique reste `UNKNOWN`. Les sidecars runtime sont un comportement WAL
attendu et n'autorisent aucune modification du seed.
