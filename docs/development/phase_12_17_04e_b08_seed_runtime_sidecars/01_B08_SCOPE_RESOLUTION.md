# Phase 12.17.4E-B08 — Résolution du scope

```text
PHASE = 12.17.4E-B08
CANONICAL_TITLE = Cycle seed/runtime et sidecars
ROOT_CHANGE = RC-08
ENTRY_HEAD = 3592ce67855ec65e7adc93d256c9a8043bd978aa
SOURCE_BUNDLE_SHA256 = 3a3407fe5f166f59bd18f70b32431ee1f16e8e0eebedecc8fc739b67f654e0b3
SOURCE_BUNDLE_MANIFEST = 6/6 PASS
```

Le lot couvre les snapshots PRE/POST, l'authentification et l'ouverture
immuable du seed, la copie runtime temporaire, sa publication atomique sans
écrasement, la migration allowlistée, WAL/SHM runtime et le backup/restore
runtime frais.

Les migrations de Resource `ACTIVE/CANONICAL` et de `ContextOrigin` restent
explicitement exclues. B09, l'API, les règles métier, la calibration et les
providers sont hors scope.

```text
SEED_POLICY = IMMUTABLE_READ_ONLY
RUNTIME_POLICY = FRESH_DERIVED_COPY
SEPARATE_COMMIT = TRUE
```
