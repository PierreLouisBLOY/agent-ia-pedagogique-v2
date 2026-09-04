# Phase 12.17.3A — Options and impact analysis

## Interpretation

Every decision provides `OPTION_A`, `OPTION_B`, `OPTION_C` and `DEFER`. `APPROVE_RECOMMENDATION` is an attestation shortcut that resolves to the option explicitly identified in the register; it is not a fifth technical option. The complete per-option impact object for Product, Domain, Application, API, SQLite, migration, tests and security is authoritative in `02_OWNER_DECISION_REGISTER.json`.

## OD-01 — Phase 1/2 source authority

| Choice | Distinct outcome | Candidate effect | Cross-layer impact |
|---|---|---|---|
| A | Bind the original artifact by locator, SHA-256, provenance and supersession | `CR-002 REWRITE`; `CR-001 CONSOLIDATE` | Strongest product/Domain completeness; documentary tests; no SQLite/API change |
| B | Owner formally closes the source as unavailable and bounds 12.17 to later repository evidence | `CR-002 KEEP + ADD_TESTS` | Enables bounded planning but preserves a stated historical limitation |
| C | Build a clearly non-authoritative reconstruction from later evidence | `CR-002 REWRITE + ADD_TESTS` | Improves navigation; cannot authorize new Domain/API/schema rules |
| DEFER | Preserve the gap | `CR-002 KEEP` | Blocks `OD-03` and `OD-07`; safest authority default |

Recommendation: **A**, confidence **MEDIUM**. Product benefit is highest, but the source is not currently located.

## OD-02 — Legacy-reuse trace

| Choice | Distinct outcome | Candidate effect | Cross-layer impact |
|---|---|---|---|
| A | Create a retrospective `docs/legacy-review` trace bound to Phase 12.15 without retroactive reapproval | `CR-001 CONSOLIDATE + ADD_TESTS` | Closes governance provenance; no Domain/Application/API/SQLite/migration change |
| B | Supersede the README location and make the existing phase handoff canonical | `CR-001 REWRITE + ADD_TESTS` | Less duplication, but changes the governance convention |
| C | Preserve the prior reuse as a closed non-conformance that cannot authorize new reuse | `CR-001 KEEP + DEPRECATE` | Explicit exception; future reuse remains fail-closed |
| DEFER | Keep `EX-01` in `EVIDENCE_GAP` | `CR-001 KEEP` | No technical change; traceability remains incomplete |

Recommendation: **A**, confidence **HIGH**.

## OD-03 — Application owners for CAP-R02/A01/A02

| Choice | Distinct outcome | Candidate effect | Cross-layer impact |
|---|---|---|---|
| A | Three bounded owners, delivered read-production → validation → promotion | `CR-041 IMPLEMENT + ADD_TESTS`; `CR-005/031 KEEP` | Best authority separation; ports and later API follow each use case; migrations only if later justified |
| B | One lifecycle module with three distinct handlers | `CR-041 IMPLEMENT`; `CR-005 CONSOLIDATE`; `CR-031 ADD_TESTS` | Faster shared delivery, larger Domain/Application coupling and test burden |
| C | Formally remove these projected capabilities from active delivery | `CR-041 DEPRECATE + REWRITE + ADD_TESTS` | Narrower product; no API or schema expansion |
| DEFER | Keep routes as non-authoritative metadata | `CR-041 KEEP` | Product lifecycle remains incomplete; non-resource API blocked |

Recommendation: **A**, confidence **HIGH**, after `OD-01`.

## OD-04 — First `/api/v2` scope

| Choice | Distinct outcome | Candidate effect | Cross-layer impact |
|---|---|---|---|
| A | Expose only read-only Resource Library READ-15 | `CR-006/007/008 ALIGN_API`; `CR-041 IMPLEMENT + ADD_TESTS` | Reuses the sole concrete Application slice; no migration expected; smallest external surface |
| B | Expose lifecycle operations after `OD-03` implementation | `CR-041 IMPLEMENT + ALIGN_API`; `CR-005 ADD_TESTS` | Broader product/API; high authority, replay, data-model and test impact |
| C | Remove HTTP delivery from current product scope | `CR-041 DEPRECATE + REWRITE` | Application-only product; smallest transport attack surface |
| DEFER | Keep `/api/v2` at zero endpoints | `CR-041 KEEP` | No code or security expansion; implementation gap persists |

Recommendation: **A**, confidence **HIGH**. It can rely on existing Resource Application ownership; any non-resource choice depends strictly on `OD-03`.

## OD-05 — External SQLite schema evidence

| Choice | Distinct outcome | Candidate effect | Cross-layer impact |
|---|---|---|---|
| A | Hash-bound, read-only metadata introspection of the exact external seed | Eight candidates `ALIGN_DATA_MODEL`/`KEEP` | Can close nine raw mapping checks; no row export, mutation, migration execution or Git database |
| B | Accept the evidence gap permanently for this design cycle | `CR-010/015 KEEP` | Allows non-data planning only; schema/migration equivalence remains unproven |
| C | Owner supplies a signed, minimized schema-only export | `CR-010/015 ALIGN_DATA_MODEL` | Useful if complete; export provenance and exclusion controls are mandatory |
| DEFER | Keep all schema-dependent claims blocked | `CR-010/015 KEEP` | `OD-06` and implementation path of `OD-07` cannot close |

Recommendation: **A**, confidence **HIGH**. `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE`.

## OD-06 — Persistence literal/default ownership

| Choice | Distinct outcome | Candidate effect | Cross-layer impact |
|---|---|---|---|
| A | Own vocabulary per bounded Domain/Application context with explicit adapter translation | `CR-015 REWRITE + ALIGN_DATA_MODEL + ADD_TESTS` | Preserves bounded contexts and keeps infrastructure non-authoritative; schema checked first |
| B | Own a shared transport-neutral vocabulary at Application level | `CR-015 CONSOLIDATE + ALIGN_DATA_MODEL + ADD_TESTS` | Easier serialization but risks flattening distinct lifecycle meanings |
| C | Declare existing literals technical-only and prohibit business interpretation | `CR-015 DEPRECATE + KEEP + ADD_TESTS` | Avoids premature modelling; lifecycle remains incomplete |
| DEFER | Leave literals unchanged and unowned | `CR-015 KEEP` | No exposure allowed; debt remains |

Recommendation: **A**, confidence **HIGH**, after `OD-05`. `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE`.

## OD-07 — READ-15 version/include scope

| Choice | Distinct outcome | Candidate effect | Cross-layer impact |
|---|---|---|---|
| A | Deprecate the options from active READ-15 and require a future versioned contract | `CR-009 DEPRECATE + REWRITE + ADD_TESTS` | Honest product boundary; no Domain/schema/API expansion; smaller input surface |
| B | Keep reserved names but reject them fail-closed today | `CR-009 KEEP + ADD_TESTS` | Preserves roadmap signal; adds negative contract/API tests |
| C | Approve a later version/include implementation after requirements and schema evidence | `CR-009 IMPLEMENT + ALIGN_DATA_MODEL + ALIGN_API + ADD_TESTS` | New Domain/Application/API semantics; possible migration; strict include allowlist |
| DEFER | Keep the current one-field request and documentary gap | `CR-009 KEEP` | No technical change; no support claim |

Recommendation: **A**, confidence **MEDIUM**. `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE` for implementation option C.

## OD-08 — Durable calibration governance

| Choice | Distinct outcome | Candidate effect | Cross-layer impact |
|---|---|---|---|
| A | Keep general blind/strong-only/authorization/lineage rules; archive V4/V5.x mechanics; threshold remains `NONE` | `CR-036/037/039 KEEP`; `CR-038 REWRITE + CONSOLIDATE + ADD_TESTS` | Clear product boundary, no runtime route/provider/API/SQLite/migration change |
| B | Retain all version-specific controls as active canonical policy | `CR-038/039 KEEP + ADD_TESTS` | Maximum forensic continuity, maximum maintenance surface |
| C | Deprecate future live calibration and retain evidence read-only | `CR-038 DEPRECATE`; `CR-039 KEEP`; `CR-036 REWRITE` | Eliminates future provider transfer risk; offline-only calibration |
| DEFER | Preserve Phase 12.16 closure exactly | `CR-036`–`CR-039 KEEP` | Authorization remains consumed/false; threshold `NONE`; no runtime change |

Recommendation: **A**, confidence **HIGH**.

## Global safety conclusion

Until attestation is complete, all recommendations are non-operative. No option authorizes code changes, schema mutation, migration, endpoint creation, provider execution or Phase 12.17.4 work in this lot.
