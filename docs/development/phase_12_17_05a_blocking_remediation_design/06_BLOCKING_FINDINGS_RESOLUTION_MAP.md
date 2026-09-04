# Phase 12.17.5A — Carte de résolution des findings bloquants

## Reclassification

Les cinq findings bloquants de 12.17.5 sont conservés. Ce lot les rend actionnables mais n'en clôt aucun, car il est limité au design et aux décisions propriétaire.

| Finding | Sévérité | État 12.17.5A | Décision | Remédiation 12.17.5B | Preuve de clôture exigée |
|---|---|---|---|---|---|
| `DMAPI-001` — perte du CHECK `size_bytes` | P0 | cause reproduite, design prêt | `DM-01` | runner ordonné puis migration corrective `002` | rejet d'une taille négative sur runtime neuf et existant migrés |
| `DMAPI-002` — perte de quatre defaults | P1 | cause reproduite, design prêt | `DM-01` | même `002` | quatre defaults introspectés et insertions par omission vérifiées |
| `DMAPI-003` — `resource_ref` sans borne sûre | P1 | preuves et options prêtes | `DM-02` | contrat Domain/Application, mapping et tests de limites | valeur max acceptée, max+1 et caractères interdits rejetés |
| `DMAPI-004` — relation `ACTIVE`/`CANONICAL` inconnue | P1 | agrégats établis, options prêtes | `DM-03` | implémentation conditionnelle au choix owner | invariants, persistence et projection API cohérents sans backfill inventé |
| `DMAPI-009` — tests incomplets de préservation du schéma | P2 | couverture manquante localisée | dépend de `DM-01` | tests DDL complets, fresh/existing runtime et rollback | tests réellement exécutés et PASS |

## Répartition des responsabilités

- **Owner** : sélectionner et attester `DM-01`, `DM-02` et `DM-03` sur la baseline exacte.
- **12.17.5B** : implémenter uniquement les décisions approuvées, sur copies de travail et avec preuves fail-closed.
- **Gate 12.17.6** : relire les preuves de 12.17.5B et le ré-audit complet; elle ne peut pas assimiler un design à une correction appliquée.

## Conditions de non-régression

La clôture des findings ne doit pas :

- modifier le seed canonique existant ;
- réécrire la migration `001` ou son checksum ;
- mélanger la correction des cinq invariants avec une évolution métier `resource_ref` ou `ACTIVE`/`CANONICAL` ;
- introduire de type HTTP, ORM ou SDK fournisseur dans les contrats ;
- modifier les frontières validées des Phases 6 et 11 ;
- committer une base, un sidecar, une sauvegarde ou une sortie runtime.

## Verdict

```text
BLOCKING_FINDINGS_TOTAL = 5
BLOCKING_FINDINGS_CLOSED = 0
BLOCKING_FINDINGS_DESIGN_READY = 5
OWNER_DECISIONS_REQUIRED = 3
PHASE_12_17_6_GATE = BLOCKED
```
