# Phase 12.17.4E-B02 — Isolation du diff et stratégie de commit

## B01 carry-forward

- 11 fichiers identifiés et hashés avant B02 ;
- 11/11 inchangés après B02 ;
- conservés hors index afin de préserver le manifeste approuvé ;
- non mélangés au diff B02.

## B02 new diff

Le diff B02 comprend exclusivement :

- 14 modules sous `calibration_tooling/` ;
- 4 fichiers de tests unitaires sous `tests/unit/calibration_tooling/` ;
- 1 test d'intégration sous `tests/integration/calibration_tooling/` ;
- 1 nouveau guard `tests/architecture/test_calibration_tooling_active_runner.py` ;
- 11 documents de preuve et leur manifeste sous le dossier B02.

Il ne contient aucun fichier historique, backend, harness, SQLite, migration,
adapter provider, artefact runtime ou secret.

## Commit

Le plan demande un commit B02 séparé. Le stage doit inclure uniquement les
fichiers ci-dessus, avec `git diff --cached --check = PASS` et le message :

`refactor: establish canonical calibration runner contracts`

Le SHA du commit est créé après le gel documentaire afin d'éviter une
auto-référence. Il est rapporté dans la sortie finale Git.

```text
B01_COMMIT = NONE
B01_MIXED_WITH_B02 = FALSE
B02_COMMIT = CREATED_AFTER_ARTIFACT_FREEZE
PUSH = NONE
```
