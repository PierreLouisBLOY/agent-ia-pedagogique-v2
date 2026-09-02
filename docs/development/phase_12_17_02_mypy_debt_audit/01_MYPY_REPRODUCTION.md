# Phase 12.17.2 — Reproduction mypy

## Baseline

- HEAD : `3156092091bf755f1d542ef2d36ada2a34f3c210`
- Python : `3.12.13`
- mypy : `2.3.1 (compiled)`
- Configuration : `strict = true`, `files = ["backend"]` dans `pyproject.toml`
- Manifest 12.17.1 : `078424d0138c090d5a7ba48364ae42fad82dca1d942dbc1c0c48471cecf52d92`

## Réalité 1 — backend canonique

Commande exécutée :

```text
.venv/Scripts/python.exe -m mypy backend --no-pretty --no-color-output --show-error-codes
```

Résultat :

```text
Success: no issues found in 659 source files
```

La même traversée avec `--no-incremental` avait déjà produit le même résultat pendant 12.17.1. Le backend de production est donc `0 erreur / 659 fichiers`.

## Réalité 2 — traversée import-driven calibration

Commande exécutée :

```text
.venv/Scripts/python.exe -m mypy --strict --explicit-package-bases --no-pretty --no-color-output --show-error-codes tests/calibration/pedagogical/pairwise_output_contract_v5_2_4.py tests/unit/test_pairwise_output_contract_v5_2_4.py
```

Résultat :

```text
Found 33 errors in 15 files (checked 2 source files)
```

La reproduction cache-disabled de 12.17.1 avec `--no-incremental` a produit exactement les mêmes `33 / 15`.

## Racines et propagation

La première racine importe directement `semantic_integration_v5`, le contrat V5.2.3, le pricing, le scorer contract et les contrats Anthropic. Par transitivité, elle atteint douze des quinze fichiers en erreur, avec une profondeur maximale observée de cinq imports jusqu'au transport Anthropic.

La deuxième racine importe en plus `semantic_gate_v5_2`, `semantic_mini_pilot_v5_1` et `semantic_pilot_freeze_v5`; ces trois fichiers en erreur n'entrent dans la traversée que par le test unitaire.

Aucun import inverse de `tests.providers.anthropic`, `tests.calibration.pedagogical`, `semantic_gate_v5_2`, `semantic_integration_v5` ou du contrat V5.2.4 n'a été trouvé sous `backend/` ou `evaluation_harness/`.

## Conclusion de reproduction

Les deux résultats ne se contredisent pas : ils mesurent deux graphes différents. La dette de 33 erreurs est une dette de tooling/calibration sous `tests`, pas une dette du runtime backend. Elle demeure réelle parce que ces helpers ont servi à construire et exécuter des calibrations, mais elle n'est pas un bloqueur mypy de production.
