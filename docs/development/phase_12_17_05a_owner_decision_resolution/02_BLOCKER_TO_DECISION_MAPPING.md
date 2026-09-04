# Phase 12.17.5A-OD — Réconciliation blockers/décisions

## Table exhaustive

| Blocker | Finding | Owner decision required | Decision ID | Rationale |
|---|---|---|---|---|
| 1 | `DMAPI-001` — perte du CHECK `size_bytes` | TRUE | `DM-01` | le choix de stratégie détermine comment restaurer l'invariant sans réécrire `001` |
| 2 | `DMAPI-002` — perte de quatre defaults | TRUE | `DM-01` | même cause SQL et même migration corrective que `DMAPI-001`; une seule décision gouverne les cinq invariants |
| 3 | `DMAPI-003` — `resource_ref` sans borne sûre | TRUE | `DM-02` | la borne et l'alphabet deviennent un contrat métier/API et exigent un arbitrage propriétaire |
| 4 | `DMAPI-004` — relation `ACTIVE/CANONICAL` inconnue | TRUE | `DM-03` | aucune preuve existante ne permet de choisir automatiquement la sémantique |
| 5 | `DMAPI-009` — tests incomplets de préservation du schéma | FALSE | `NO_OWNER_DECISION_REQUIRED` | la dette de test se ferme techniquement après `DM-01`; elle ne crée pas une quatrième règle métier |

## Réconciliation arithmétique

- 5/5 blockers sont couverts.
- 4/4 blockers nécessitant une décision owner sont expliqués.
- 3 décisions suffisent parce que `DM-01` couvre deux blockers de schéma liés à la même cause.
- `DMAPI-009` dépend du résultat de `DM-01`, mais ne nécessite aucune sélection propriétaire supplémentaire.

```text
BLOCKERS_MAPPED = 5/5
OWNER_DECISION_BLOCKERS_EXPLAINED = 4/4
OWNER_DECISIONS = 3
MAPPING_COHERENCE = PASS
```
