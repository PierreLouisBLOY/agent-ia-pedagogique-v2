# Phase 12.16-G2-V5 — Preuve de validation réduite

Date : 2026-09-01. Environnement : Python 3.12 du `.venv`, Windows PowerShell.

## Tests ciblés

Commande :

```text
python -m pytest -q -p no:cacheprovider \
  tests/unit/test_pedagogical_calibration_v4_2.py \
  tests/unit/test_pedagogical_calibration_v5.py \
  tests/unit/test_pedagogical_calibration_v5_semantic_integration.py
```

Résultat : `38 passed in 12.00s`.

La sélection couvre : invariants V4.2, contrat/parser/schema V5, hashing des call-specs, diff des 102 records, carry-forward, choix des pilotes, budget, préflight, canaries, interdiction de rerun, reporting/provenance et live default-closed.

## Validations statiques

| Validation | Périmètre | Résultat |
|---|---|---|
| Ruff | cinq fichiers V5 code/tests | `All checks passed!` |
| mypy | `--strict --follow-imports=skip`, cinq fichiers V5 code/tests | `Success: no issues found in 5 source files` |
| compileall | cinq fichiers V5 code/tests | PASS, exit code 0 |
| `git diff --check` | diff suivi courant | PASS, exit code 0 |

La suite globale n'a pas été lancée, conformément au périmètre réduit. Les diagnostics mypy historiques hors de ces fichiers restent hors scope.

## Sûreté

- provider calls : 0 ;
- credential resolution : 0 ;
- transport réel : 0 ;
- SQLite transférée : 0 ;
- retry/rerun : 0 ;
- commit : `NONE` ;
- push : `NONE` ;
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`.
