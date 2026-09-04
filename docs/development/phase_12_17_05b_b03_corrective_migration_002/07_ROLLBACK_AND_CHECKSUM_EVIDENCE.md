# Phase 12.17.5B-B03 — Rollback et checksum

## Checksum

Après application de `001` et `002`, une divergence synthétique du checksum de ledger de `002` produit `MIGRATION_CHECKSUM_MISMATCH: 002` avant toute réapplication.

## Rebuild fautif

Une variante temporaire de `002` échoue volontairement après création et remplissage de la table de remplacement, mais avant la suppression de `document`. Le runner :

- rollbacke la transaction `002` ;
- conserve la table originale après `001` ;
- conserve tous les identifiants ;
- supprime par rollback la table de remplacement ;
- laisse uniquement `001` dans le ledger ;
- n'exécute aucune migration suivante.

```text
CHECKSUM_MISMATCH_002 = PASS_FAIL_CLOSED
ROLLBACK_002 = PASS
ORIGINAL_TABLE_RECOVERABLE = TRUE
FALSE_SUCCESS_LEDGER_ENTRY = FALSE
```
