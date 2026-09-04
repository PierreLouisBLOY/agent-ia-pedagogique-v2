# Phase 12.17.5B-B03 — Implémentation de 002

## Identité

```text
MIGRATION_002_PATH = database/migrations/002_restore_document_invariants.sql
MIGRATION_002_VERSION = 002
MIGRATION_002_NAME = restore-document-invariants
MIGRATION_002_ORDER = 2
MIGRATION_002_SHA256 = e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893
MIGRATION_001_SHA256 = 5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102
```

## Mécanisme

La migration reconstruit `document` dans une table temporaire avec les quinze colonnes existantes, les cinq invariants du seed et le CHECK SHA-256 de `001`. Elle recopie explicitement les quinze colonnes, remplace la table dans la transaction et recrée les deux index canoniques.

Le registre de production contient désormais `001`, puis `002`, chacune avec ressource, checksum, ordre, applicabilité et postcondition propres. La postcondition `document-invariants` vérifie les quatre defaults, le CHECK de taille, le CHECK SHA, les deux index et leur comportement effectif avant l'inscription de `002` au ledger.

```text
PRODUCTION_MIGRATION_REGISTRY_COUNT = 2
PRODUCTION_MIGRATION_SEQUENCE = 001 -> 002
MIGRATION_001_MODIFIED = FALSE
ACTIVE_CANONICAL_LOGIC_ADDED = FALSE
CONTEXT_ORIGIN_LOGIC_ADDED = FALSE
```
