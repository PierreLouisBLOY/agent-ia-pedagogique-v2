# Phase 12.17.5B-B07 — Ré-audit migration P0

La migration `001` conserve son SHA-256
`5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102`.
La corrective `002` existe sous une identité distincte
`e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893`.

Les preuves B02→B04 et le replay ciblé B07 confirment :

- restauration du CHECK `size_bytes >= 0` et des quatre defaults, soit 5/5 ;
- parcours fresh `001 -> 002` et existing `001 -> 002` ;
- replay no-op, checksum fail-closed et rollback ;
- données, PK, indexes et foreign keys préservés ;
- recovery vérifiée sur copie distincte ;
- runtime utilisateur non migrée et migration `002` non appliquée dessus.

Aucune migration ACTIVE/CANONICAL ou `ContextOrigin` n'existe. B07 n'a créé ou
exécuté aucune migration supplémentaire.

```text
MIGRATION_SCHEMA_REGRESSION_P0 = CLOSED
MIGRATION_001_IMMUTABLE = TRUE
FIVE_INVARIANTS = 5/5 PASS
FRESH_001_TO_002 = PASS
EXISTING_001_TO_002 = PASS
REPLAY_CHECKSUM_ROLLBACK_RECOVERY = PASS
USER_RUNTIME_002_APPLIED = FALSE
B07_MIGRATION_WRITE_OPERATIONS = 0
```
