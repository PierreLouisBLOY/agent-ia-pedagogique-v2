# Phase 12.16-G2-V4.2 — Provenance du rapport agrégé

## Partition finale

`LOGICAL_MATRIX_CALL_COUNT = 102`

`CARRY_FORWARD_COUNT = 63`

`NEWLY_EXECUTED_COUNT = 39`

Les 63 records carry-forward conservent individuellement :

- `source_run_id = 12.16-g2-v4-1-live` ;
- `source_baseline_commit = 71e4258baacc1f0914cf9a9087638736c2a4ebdd` ;
- leur call-spec SHA-256 V4.1 ;
- `disposition = CARRY_FORWARD` ;
- `ledger_source = artifacts/calibration/12.16-g2-v4-1/ledger.json`.

Les 39 nouveaux records conservent individuellement :

- `source_run_id = 12.16-g2-v4-2-live` ;
- `source_baseline_commit = a560d6ca1989ba3dd13c9d02eeb97ef3fff6238b` ;
- leur call-spec SHA-256 V4.2 ;
- `disposition = NEWLY_EXECUTED` ;
- `ledger_source = artifacts/calibration/12.16-g2-v4-2/ledger.json`.

Les 31 anciens succès liés aux projections legacy ne figurent jamais dans le groupe
carry-forward : ils sont remplacés par leurs nouvelles exécutions V4.2. Les 63 résultats
certifiés n'ont été ni réémis ni transférés aux fournisseurs pendant ce run.

Intégrité historique vérifiée :

- safe report V4.1 : `fe25523b4c72d927c4ba71df4d789c3fafeaed8414cd82a342761cc3581eea85` ;
- ledger V4.1 : `697eb124e5a4883896e2eb17ef7fa4764b7396fdc434dbaf0022a3425a79788f`.

`CROSS_RUN_PROVENANCE_PRESERVED = TRUE`
