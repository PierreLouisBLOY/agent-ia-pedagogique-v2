# Phase 12.17.4E-B09 — Entrée et carry-forward

```text
PHASE_12_17_04E_B08 = PASS
B09_ENTRY_GATE = READY
HEAD_PRE_B09 = 054ba2c7eb19f1be4eb048f94e554022db631dc1
B01_MANIFEST = 8/8 PASS
B01_MANIFEST_SHA256 = de4903fa9a78d4cbbcc0c792a0d4e46d3805874c686b9e03d75350e694466e8e
B08_MANIFEST = 14/14 PASS
B08_MANIFEST_SHA256 = 180db0afff148567bd08052d45eb2a5d8e14a29d57b3aba805ffd5b62abbea54
HISTORICAL_FREEZE_PRE = 40/40 PASS
KNOWN_DRIFTS_PRE = 7/7 UNCHANGED
NEW_HISTORICAL_DRIFT_PRE = 0
ACTIVE_MYPY_PRE = 0/41
BACKEND_MYPY_PRE = 0/671
HISTORICAL_MYPY_PRE = 15 errors/10 files
PROVIDER_CALLS_PRE = 0
```

Le carry-forward B08 conserve le seed au SHA-256
`38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`,
une runtime distincte validée et la migration 001 appliquée une fois avec
replay idempotent. B09 propage cette preuve sans ouvrir la base ni rejouer la
migration.

Les éléments non suivis antérieurs au lot sont préservés et exclus de son
stage.
