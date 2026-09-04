# Phase 12.17.3A — 12.17.4 readiness

## Current verdict

`PHASE_12_17_4_RATIONALIZATION_DESIGN_GATE = BLOCKED_OWNER_DECISIONS`

| Check | Current result |
|---|---|
| Decision register parses and contains 8 unique decisions | PASS |
| Independent/dependent partition equals 4/4 | PASS |
| Every decision has A/B/C/DEFER options | PASS |
| Every option covers Product, Domain, Application, API, SQLite, migration, tests and security | PASS |
| Recommendations have explicit confidence | PASS |
| SQLite-dependent decisions are marked | PASS — `OD-05`, `OD-06`, `OD-07` |
| Owner choices completed | FAIL — `0/8` |
| Dependency-compatible owner choices | BLOCKED — no choices |
| Owner attestation integrity verified | BLOCKED — no completed attestation |

`BLOCKING_OWNER_DECISION_COUNT = 8`

## Deterministic transition to READY

The state may change to `READY` only when all conditions are true:

1. The attestation baseline equals `6d0d66380757d7502fd967cd0246c5b6ff91d5f8`.
2. The attestation binds decision register SHA-256 `43985ca2cffc4979d59b32466654d541f9084465b7f06b5e00bf81be33cad8f4`.
3. Exactly one allowed choice is recorded for every `OD-01` through `OD-08`.
4. No required decision is `DEFER`, unless the same attestation explicitly removes it from 12.17.4 scope.
5. Dependencies are consistent:
   - active `OD-03` requires a non-deferred `OD-01`;
   - non-resource `OD-04` requires `OD-03 OPTION_A` or `OPTION_B`;
   - `OD-06 OPTION_A` or `OPTION_B` requires `OD-05 OPTION_A` or `OPTION_C`;
   - `OD-07 OPTION_C` requires `OD-05 OPTION_A` or `OPTION_C`;
   - any schema-dependent action keeps `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE` until evidence verification passes.
6. `OWNER_ATTESTATION = APPROVED`, owner role and UTC timestamp are present, and the completed attestation hash verifies.

Only after these checks may a new package state:

`PHASE_12_17_4_RATIONALIZATION_DESIGN_GATE = READY`

## What READY would authorize

READY authorizes preparation of a separate 12.17.4 rationalization **design** lot under the selected dispositions. It does not itself authorize:

- business-code modification;
- source-rule rewrite;
- API implementation;
- SQLite mutation or migration execution;
- provider call or credential resolution;
- commit, push or merge.

## Fail-closed conditions

Any missing choice, unknown value, hash mismatch, contradictory dependency, broadened external evidence or implicit recommendation selection keeps the state `BLOCKED_OWNER_DECISIONS`.
