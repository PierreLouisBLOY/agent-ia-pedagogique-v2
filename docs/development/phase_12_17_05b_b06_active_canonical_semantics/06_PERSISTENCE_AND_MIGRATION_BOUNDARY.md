# Phase 12.17.5B-B06 — Persistence et frontière de migration

Le schéma courant conserve une colonne physique unique
`resource.identity_status TEXT NOT NULL DEFAULT 'ACTIVE'`. Elle ne peut pas
représenter simultanément les deux dimensions.

Le mapper outbound isole cette dette sous `_LegacyResourceIdentityStatus` :

| Valeur physique | État Domain décodé |
|---|---|
| `ACTIVE` | `availability=ACTIVE`, `canonicality=UNKNOWN` |
| `CANONICAL` | `availability=UNKNOWN`, `canonicality=CANONICAL` |

L'encodage est permis uniquement pour ces deux projections sans perte. Un état
`UNKNOWN/UNKNOWN` ou une future combinaison multi-dimensionnelle est refusé
fail-closed par `SQLiteVocabularyMappingError`.

Le modèle et READ-15 ne requièrent aucune migration dans B06. Une persistence
complète des deux dimensions exigera en revanche un design structurel séparé,
probablement une colonne de canonicalité distincte. Sa nullabilité, son
vocabulaire, son default et sa stratégie de reprise restent à approuver; aucun
default ni backfill n'est proposé comme acquis.

```text
CURRENT_PERSISTENCE_MAPPING = LOSSLESS_FOR_TWO_LEGACY_OBSERVATIONS
MIGRATION_REQUIRED_FOR_B06 = FALSE
MIGRATION_REQUIRED_FOR_FULL_TWO_DIMENSION_STORAGE = TRUE
ACTIVE_CANONICAL_MIGRATION_AUTHORIZED = FALSE
MIGRATION_EXECUTED_BY_B06 = FALSE
DATA_BACKFILL_AUTHORIZED = FALSE
DATA_BACKFILL_EXECUTED = FALSE
MIGRATION_002_MIXED_WITH_B06 = FALSE
```
