# V5.1 — Parser failure surface audit

## Canonical state

The canonical scorer contract remains
`a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`.
The failed V5 pilot artifacts were not modified.

## Deterministic map

| JSON path | Expected value | Existing normalization | Existing failure | V5.1 diagnostic |
|---|---|---|---|---|
| `$` | one JSON object | none | `INVALID_JSON` or `INVALID_SHAPE` | exact code, response hash and length |
| `$.*` | exact required top-level fields | none | `INVALID_SHAPE` | `MISSING_FIELD` or `EXTRA_FIELD` with path |
| `$.status` | string enum `SCORED|INCONCLUSIVE` | none | `INVALID_VALUE` | case/outer-space normalization, otherwise `UNKNOWN_VALUE` |
| `$.confidence` | string enum `LOW|MEDIUM|HIGH` | none | `INVALID_VALUE` | case/outer-space normalization, otherwise `UNKNOWN_VALUE` |
| `$.evidence` | array, 0..8 items | runtime cast only | shape/value may be global | typed cardinality diagnostic |
| `$.evidence[i]` | exact object fields | none | `INVALID_SHAPE` | missing/extra field path |
| `$.evidence[i].check_id` | canonical rubric check id, string, unique | none | `INVALID_VALUE`, `EVIDENCE_CHECK_UNKNOWN` or duplicate | casefold only when it resolves to one exact canonical id; unknown values are hashed |
| `$.evidence[i].locator` | trimmed string, length 1..64 | none | `INVALID_VALUE` | trim outer whitespace; typed bound diagnostic |
| `$.evidence[i].observation` | trimmed string, length 1..180 | none | `INVALID_VALUE` | trim outer whitespace; value is never persisted |
| `$.defects` | array, 0..8 items, exact missing-check coverage | runtime cast only | shape/value or `DEFECT_COVERAGE_INVALID` | typed cardinality plus canonical-invariant path |
| `$.defects[i].severity` | `MINOR|MAJOR|CONTRADICTION` | none | `INVALID_VALUE` | unambiguous enum normalization; unknown fails |
| `$.score_level` | exact integer 0..4 or null | none | `INVALID_VALUE` | `INVALID_TYPE` or `OUT_OF_BOUNDS` |
| `$.score_level` with `INCONCLUSIVE` | null and confidence `LOW` | none | `INVALID_VALUE` | explicit invariant diagnostic |
| `$.score_level` versus evidence | exact evidence-derived level | none | score/contradiction mismatch | canonical invariant and exact path |
| `$.rationale` | trimmed string, length 1..240 | none | may surface as an unclassified constructor error | typed bound diagnostic; value never persisted |
| `$.differences` | array, 1..8 items | runtime cast only | shape/value may be global | typed cardinality diagnostic |
| `$.differences[i].*` | exact bounded fields and enums | none | `INVALID_VALUE` or `INVALID_SHAPE` | exact path, type, enum and bound |
| `$.decision` | `A_BETTER|B_BETTER|TIE` | none | `INVALID_VALUE` | case/space normalization; aliases `A`, `B`, `EQUAL` only |
| pairwise semantic invariants | decision supported by material differences | none | specific canonical error | canonical error retained with decision/differences path |

`build_v5_anchor_observation()` can also emit the legacy global
`INVALID_VALUE`, but that is an offline input-construction failure and not a
provider-response parser surface.

## Root finding

The old schema constrains general string shapes but does not enumerate the
criterion-specific `check_id` values or enforce all semantic invariants. A
provider response can therefore cross the SDK structured-output boundary and
still fail the canonical parser. V5.1 preserves that strictness while making the
failure location deterministic.
