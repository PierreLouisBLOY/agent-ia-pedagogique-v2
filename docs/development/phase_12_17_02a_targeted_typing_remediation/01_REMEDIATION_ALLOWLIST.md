# Phase 12.17.2A — Allowlist de remédiation

## Source et bornes

Source autoritative : `docs/development/phase_12_17_02_mypy_debt_audit/02_ERROR_REGISTER.json`.

- `ALLOWLIST_DIAGNOSTIC_COUNT = 19`
- `ALLOWLIST_FILE_COUNT = 10`
- `EXPECTED_ROOT_CORRECTION_COUNT = 13`
- `ALLOWLIST_CLUSTERS = C01, C04, C06`

## Diagnostics autorisés

| Cluster | Error IDs | Diagnostics | Fichiers | Correction racine attendue |
| --- | --- | ---: | ---: | ---: |
| `C01_STALE_TYPING_SCAFFOLD` | `MYPY-001`, `MYPY-006`, `MYPY-024` à `MYPY-032` | 11 | 8 | 11 |
| `C04_LOOP_VARIABLE_COLLISION` | `MYPY-010` à `MYPY-016` | 7 | 1 | 1 |
| `C06_DYNAMIC_OBSERVATION_UNION` | `MYPY-020` | 1 | 1 | 1 |

Liste complète :

```text
MYPY-001
MYPY-006
MYPY-010
MYPY-011
MYPY-012
MYPY-013
MYPY-014
MYPY-015
MYPY-016
MYPY-020
MYPY-024
MYPY-025
MYPY-026
MYPY-027
MYPY-028
MYPY-029
MYPY-030
MYPY-031
MYPY-032
```

## Résultat d'exécution

- `APPLIED_ROOT_CORRECTION_COUNT = 12`
- `REMOVED_ALLOWLIST_DIAGNOSTIC_COUNT = 18`
- `DEFERRED_ALLOWLIST_DIAGNOSTIC_COUNT = 1`
- `DEFERRED_ALLOWLIST_ERROR_ID = MYPY-001`

`MYPY-001` a été reproduit et son fix minimal essayé, puis annulé : toute modification de `tests/providers/anthropic/transport.py` change le bundle source Anthropic incorporé aux identités historiques et fait échouer la gate `MATRIX_MISMATCH`. Le prompt autorise explicitement l'annulation et le defer lorsqu'un fix exige un changement architectural ou comportemental.
