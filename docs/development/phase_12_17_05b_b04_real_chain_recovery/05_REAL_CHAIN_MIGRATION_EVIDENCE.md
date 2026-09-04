# Phase 12.17.5B-B04 — Chaîne réelle et replay

La cible est une copie contrôlée du backup utilisateur, hors dépôt. Son état
initial contient `001` seulement; le runner découvre le catalogue autorisé
`001,002`, ignore `001`, applique `002` puis écrit son identité exacte.

```text
VALIDATION_TARGET = CONTROLLED_RUNTIME_COPY
MIGRATIONS_BEFORE = 001
MIGRATION_MISSING = 002
MIGRATIONS_APPLIED = 002
MIGRATIONS_SKIPPED_FIRST_RUN = 001
MIGRATIONS_AFTER = 001,002
MIGRATION_002_LEDGER_SHA256 = e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893
USER_RUNTIME_002_APPLIED = FALSE
```

Le replay retourne `migrations_applied=[]` et
`migrations_skipped=[001,002]`. Le fichier principal conserve entre les deux
snapshots de replay sa taille, son mtime et son SHA-256
`7876142f8d84e351d99035d91f7c9e870b6aa49f6982c819e3f89a9147826728`.
Le ledger, les 15 identités et le schéma restent identiques.

Le snapshot physique complet diffère uniquement parce que l'ouverture du
runner matérialise sur la copie un WAL vide et un SHM standard. Cette création
de sidecars n'est ni une migration ni une mutation du fichier principal; elle
est détaillée dans `08_SIDECAR_PRE_POST_EVIDENCE.md`.

```text
REPLAY_MIGRATION_NO_OP = PASS
REPLAY_MAIN_FILE_BYTE_IDEMPOTENCE = PASS
REPLAY_FULL_FILESET_IDENTICAL = FALSE_SIDECARS_MATERIALIZED
```
