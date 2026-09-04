# Phase 12.17.3 — Prioritization and owner decisions

## Finding priority

| Priority | Count | Meaning in this audit |
|---|---:|---|
| P0 | 0 | No confirmed same-scope contradiction or product-breaking invariant |
| P1 | 8 | Missing authority/evidence/implementation ownership with high impact |
| P2 | 8 | Duplicate, overlap, legacy or over-specific debt with moderate impact |
| P3 | 4 | Traceability, test and documentation hygiene |

The priority counts are mechanically mirrored in `09_FINDINGS_REGISTER.json`. A P1 is not authorization to remediate.

## Required owner decisions

| ID | Decision required | Evidence to consider | Safe default while unresolved | Affected candidates |
|---|---|---|---|---|
| `OD-01` | Identify and authorize the consolidated Phase 1/2 business-rule source, or formally declare it unavailable/out of corpus | Repository search found no such source | Keep 12.17.3 marked incomplete with respect to Phase 1/2 historical completeness | `CR-002` |
| `OD-02` | Select the canonical legacy-reuse trace location and disposition the Phase 7 adaptation already cited by Phase 12.15 | README requires `docs/legacy-review`; directory absent | Do not infer that reuse was invalid or retroactively approve it | `CR-001`, `EX-01` |
| `OD-03` | Prioritize Application owners for CAP-R02, CAP-A01 and CAP-A02 | Only READ-15 Resource Library is concrete | Treat registry routes as metadata, not implemented business capability | `CR-041` |
| `OD-04` | Choose the first `/api/v2` delivery scope and authority boundary | Eleven API-relevant rules; zero endpoints | Do not add an HTTP adapter before its Application use case | `CR-041` |
| `OD-05` | Authorize a hash-bound read-only inspection of the external canonical SQLite schema | Nine rules are `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED` | Make no claim about unseen constraints and do not copy the database into Git | `CR-010` |
| `OD-06` | Assign Domain/Application ownership to the ten SQLite adapter literal/default families | Status/type/title/actor defaults live in infrastructure | Preserve current code; do not move or rename literals | `CR-015` |
| `OD-07` | Decide whether READ-15 `version_ref` and `include` remain deferred, are deprecated, or become a future contract | Phase 12.15 explicitly defers them | Do not claim or expose support | `CR-009` |
| `OD-08` | Define the durable calibration governance boundary: retained lineage policy, archival treatment of V4/V5.x controls and any future release-threshold process | Live authorization consumed; route unchanged; threshold `NONE` | No provider call, no route change and no threshold adoption | `CR-038`, `CR-039` |

`OWNER_DECISION_REQUIRED_COUNT = 8`

## Priority sequence after owner decisions

1. Bind missing authority and external evidence (`OD-01`, `OD-02`, `OD-05`).
2. Define business ownership before transport or persistence refactoring (`OD-03`, `OD-04`, `OD-06`, `OD-07`).
3. Separate durable calibration semantics from preserved history (`OD-08`).
4. Only then plan consolidation of exact/quasi duplicates, overlap parents, tests and API mappings.

No option above has been selected by this audit. The canonical ruleset remains `CANDIDATE`.
