# Phase 12.17.2A — Mypy avant/après

## Backend

| Mesure | Avant | Après |
| --- | ---: | ---: |
| Erreurs | 0 | 0 |
| Fichiers analysés | 659 | 659 |

Résultat après : `Success: no issues found in 659 source files`.

## Traversée import-driven stricte

Commande identique à 12.17.2 :

```text
.venv/Scripts/python.exe -m mypy --strict --explicit-package-bases --no-pretty --no-color-output --show-error-codes tests/calibration/pedagogical/pairwise_output_contract_v5_2_4.py tests/unit/test_pairwise_output_contract_v5_2_4.py
```

| Mesure | Avant | Cible initiale | Après |
| --- | ---: | ---: | ---: |
| Erreurs | 33 | 14 | 15 |
| Fichiers en erreur | 15 | 9 | 10 |
| Diagnostics supprimés | — | 19 | 18 |
| Nouveaux diagnostics | — | 0 | 0 |

Écart à la cible : `+1`, exclusivement `MYPY-001`. Son fix a été annulé parce qu'il changeait un bundle source utilisé par les identités historiques. Tous les autres IDs allowlistés ont disparu.

## Dette résiduelle par cluster

| Cluster | Diagnostics restants |
| --- | ---: |
| `C01_STALE_TYPING_SCAFFOLD` | 1 |
| `C02_PROVIDER_OPTIONAL_NARROWING` | 4 |
| `C03_FIXED_TUPLE_CARDINALITY` | 4 |
| `C05_OPTIONAL_BUDGET_NARROWING` | 4 |
| `C07_IMPLICIT_REEXPORT` | 1 |
| `C08_BRANCH_SPEC_UNION` | 1 |

Total : `15 diagnostics / 10 fichiers`. Les IDs correspondent exactement au registre résiduel; aucun diagnostic nouveau n'est apparu.
