# Phase 12.17.4E-B03 — Isolation du diff et commit

## Diff B03

Le lot comprend exclusivement :

- 2 mises à jour B02 nécessaires : version du package et enum d'erreurs fermé ;
- 7 nouveaux fichiers sous `calibration_tooling/adapters/` ;
- 1 extension du guard B02 pour ouvrir uniquement B03 ;
- 1 nouveau guard d'architecture B03 ;
- 3 fichiers de tests unitaires Anthropic ;
- 1 test d'intégration offline sur client injecté ;
- 11 documents de preuve et leur manifeste B03.

Soit `15` fichiers code/test et `12` fichiers documentaires. Aucun fichier des
40 historiques, aucun backend métier/runtime, aucun harness, aucun SQLite,
aucune migration, aucune donnée runtime et aucun secret n'appartient au diff.

## Isolation

Le carry-forward B01 et les artefacts antérieurs non suivis restent hors index.
Le stage B03 est construit avec une allowlist explicite. Le contrôle requis est
`git diff --cached --check = PASS`.

## Commit

Le SHA est créé après le gel du manifeste pour éviter toute auto-référence et
est rapporté dans la sortie finale.

```text
B01_MIXED_WITH_B03 = FALSE
B03_COMMIT = CREATED_AFTER_ARTIFACT_FREEZE
COMMIT_MESSAGE = refactor: add active anthropic calibration adapter
PUSH = NONE
```
