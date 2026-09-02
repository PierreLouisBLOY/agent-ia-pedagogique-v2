# Phase 12.17.4E-B05 — Entrée et carry-forward

```text
PHASE_12_17_04E_B04 = PASS
B05_ENTRY_GATE = READY
HEAD_PRE_B05 = cdbcb0457487594745becd9055ac6479127b4ed3
B04_MANIFEST_SHA256 = e9079caa4dc918d66cdba0a4efa6493617c4731c39a0af329a940ce9d11d389f
B03_COMMIT = 711ebec196d7a2ea2bb0acf1cfd23812fd56e0e7
B02_COMMIT = 16d1e90ea8629fa419a93759e4c30ff1c0cb96f0
B01_MANIFEST_SHA256 = de4903fa9a78d4cbbcc0c792a0d4e46d3805874c686b9e03d75350e694466e8e
```

Le manifeste B01 vérifie 8/8 entrées ; avec l'ADR, le guard et le manifeste,
le carry-forward vérifie 11/11. Il reste non suivi et hors du stage B05. Les
autres artefacts antérieurs non suivis restent également inchangés.

```text
HISTORICAL_FREEZE_PRE = 40/40 PASS
KNOWN_DRIFTS_PRE = 7/7 UNCHANGED
NEW_HISTORICAL_DRIFT_PRE = 0
ACTIVE_IMPORTS_TO_HISTORICAL_PRE = 0
ACTIVE_IMPORTS_TO_TESTS_PROVIDERS_PRE = 0
ACTIVE_MYPY_PRE = 0 / 39 files
BACKEND_MYPY_PRE = 0 / 659 files
HISTORICAL_MYPY_PRE = 15 errors / 10 files
PROVIDER_CALLS_PRE = 0
```
