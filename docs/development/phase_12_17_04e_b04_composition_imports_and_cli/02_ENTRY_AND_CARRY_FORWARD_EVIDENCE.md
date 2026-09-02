# Phase 12.17.4E-B04 — Entrée et carry-forward

## Binding d'entrée

```text
PHASE_12_17_04E_B03 = PASS
B04_ENTRY_GATE = READY
HEAD_PRE_B04 = 711ebec196d7a2ea2bb0acf1cfd23812fd56e0e7
B02_COMMIT = 16d1e90ea8629fa419a93759e4c30ff1c0cb96f0
B03_MANIFEST_SHA256 = 28a111597572ccc6658f56d2de0817b8b9fa1a93b9eb8a51f6e5948968790437
B01_MANIFEST_SHA256 = de4903fa9a78d4cbbcc0c792a0d4e46d3805874c686b9e03d75350e694466e8e
```

Le manifeste B01 a été vérifié à 8/8, puis l'ADR, le guard et le manifeste
lui-même portent le carry-forward à 11/11. Ils restent non suivis et ne font
pas partie du stage B04. Les artefacts 12.17.3 et du design 12.17.4 déjà
présents restent eux aussi hors du lot.

## Baselines PRE

```text
HISTORICAL_FREEZE_PRE = 40/40 PASS
PREEXISTING_DRIFT = 7/7 UNCHANGED
NEW_HISTORICAL_DRIFT = 0
ACTIVE_IMPORTS_TO_HISTORICAL = 0
ACTIVE_IMPORTS_TO_TESTS_PROVIDERS = 0
ACTIVE_MYPY_PRE = 0 / 30 files
BACKEND_MYPY_PRE = 0 / 659 files
HISTORICAL_MYPY_PRE = 15 errors / 10 files
PROVIDER_CALLS_PRE = 0
```
