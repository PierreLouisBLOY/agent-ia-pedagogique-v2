# Calibration tooling — frontières historiques

Ce marqueur ne qualifie pas le package `calibration_tooling` lui-même comme
historique. Il déclare les anciennes racines ci-dessous comme preuves
`HISTORICAL_ONLY`, hors du graphe actif :

- `tests/calibration/pedagogical/` : corpus, plans, runners, parsers et gates
  V2 à V5.2.4 issus de la Phase 12.16 ;
- `tests/providers/anthropic/` : transport et scorer Anthropic historiques.

## Règle d'exploitation

Ces racines restent à leur emplacement et sont protégées par le registre B01
de 40 SHA-256. Elles ne sont ni une bibliothèque active, ni une source de
réexport, ni un fallback. Aucun module sous `calibration_tooling`, `backend` ou
`evaluation_harness` ne doit les importer.

Les sept écarts attribués à 12.17.2A font partie de la baseline gelée actuelle ;
ils ne constituent pas une autorisation de réécriture rétroactive. L'ancienne
traversée mypy reste attendue à 15 erreurs dans 10 fichiers et sert uniquement
de preuve informative.

## Remplacements actifs

| Responsabilité historique | Propriétaire actif |
|---|---|
| contrats de calibration et types discriminés | `calibration_tooling/contracts/` |
| orchestration et policy | `calibration_tooling/application/` |
| runner, budget, autorisation et ledger | `calibration_tooling/runtime/` |
| transport/scorer Anthropic | `calibration_tooling/adapters/anthropic/` |
| télémétrie technique bornée | `calibration_tooling/observability/` |

La parité signifie ici que les invariants durables approuvés sont conservés
par les nouveaux contrats typés. Elle ne signifie ni import, ni copie, ni
correction des implémentations historiques.

```text
HISTORICAL_SOURCE_FILES_MODIFIED = 0
ACTIVE_IMPORTS_TO_HISTORICAL = 0
ACTIVE_IMPORTS_TO_TESTS_PROVIDERS = 0
HISTORICAL_MYPY_DEBT = 15 errors / 10 files
RETROACTIVE_REPAIR = FORBIDDEN
```
