# Phase 12.16-G2-V4.2 — Handoff final de l'exécution live

`BASELINE_COMMIT_SHA = a560d6ca1989ba3dd13c9d02eeb97ef3fff6238b`

`MATRIX_SHA256 = 605358444f1bc9052ca7b4e55057c9d5424b3ad3b4deecc17bdde83e23c18aa5`

`REVIEW_CONTRACT_SHA256 = 1201a11ddb6b2d57b28a0f8ab20ce58f87a78e02be555c0c5248edbf525f8b1d`

`PRICING_SHA256 = 31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`

`LOGICAL_MATRIX_CALL_COUNT = 102`

`CARRY_FORWARD_COUNT = 63`

`REPAIR_TRANCHE_MAX_CALL_COUNT = 39`

`NEW_PROVIDER_CALLS_ATTEMPTED = 39`

`OPENAI_COMPLETED/FAILED/SKIPPED = 20/0/0`

`ANTHROPIC_COMPLETED/FAILED/SKIPPED = 19/0/0`

`AUTOMATIC_RETRIES/AUTOMATIC_RERUNS = 0/0`

`ACTUAL_MEASURED_COST_USD = 0.160160`

`LEDGER_PRUDENT_COST_USD = 0.160160`

`APPROVED_CEILING_USD = 2.111240`

`CALIBRATION_VERDICT = CALIBRATION_COMPLETE`

`RELEASE_THRESHOLD_ADOPTED = NONE`

`SECRETS_DETECTED = NONE`

`SQLITE_RUNTIME_CREATED_OR_TRANSMITTED = NONE`

`LIVE_AUTHORIZATION = CONSUMED`

`LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`

`PUSH = NONE`

## Artefacts durables

- ledger : `artifacts/calibration/12.16-g2-v4-2/ledger.json` ;
- safe report JSON : `artifacts/calibration/12.16-g2-v4-2/safe_report.json` ;
- safe report Markdown : `artifacts/calibration/12.16-g2-v4-2/safe_report.md`.

Checksums :

- ledger : `7d173accfc7591998d7cab1625a6ad562f1e530fc24027aea5f322a9c44bd10a` ;
- safe report JSON : `3cbe5c7bbf5fc0a4b34f0b3810656666969355d7fde3fa643b9ae05371082c1a` ;
- safe report Markdown : `a029856836a788672bd3a0000329473b594314df0003726732c13c7e8f9dcff8` ;
- projection canonique ledger : `5584f391aadaf9e8bc8e8c025fde1569363cc9cfd0fdb3b2ce7466a77802e191`.

Le HEAD Git reste la baseline autorisée. Le worktree est non clean uniquement à cause
des sept documents obligatoires de ce handoff, laissés non commités conformément à
l'interdiction de commit. Aucun fichier runtime produit, artefact V4.1 ou secret n'a
été ajouté à Git.
