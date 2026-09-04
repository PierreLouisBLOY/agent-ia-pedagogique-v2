# Phase 12.17.3A — Technical recommendations

## Non-operative recommendation set

These recommendations are engineering advice, not approvals. They cannot change an `UNRESOLVED` decision or authorize implementation.

| Decision | Recommendation | Confidence | Why | First candidate actions after owner approval |
|---|---|---|---|---|
| `OD-01` | `OPTION_A` — bind the original Phase 1/2 corpus | MEDIUM | Highest provenance quality, but the artifact is not currently located | `CR-002 REWRITE`; `CR-001 CONSOLIDATE`; lineage tests |
| `OD-02` | `OPTION_A` — retrospective canonical legacy trace | HIGH | Closes the declared process gap without rewriting prior approval history | `CR-001 CONSOLIDATE + ADD_TESTS` |
| `OD-03` | `OPTION_A` — three bounded Application owners | HIGH | Preserves read/validate/promote authority separation and keeps routes non-authoritative | `CR-041 IMPLEMENT + ADD_TESTS`; keep `CR-005/031` |
| `OD-04` | `OPTION_A` — Resource READ-15 only | HIGH | Only API candidate backed by a concrete Application use case | `CR-006/007/008 ALIGN_API`; `CR-041 IMPLEMENT + ADD_TESTS` |
| `OD-05` | `OPTION_A` — hash-bound read-only schema introspection | HIGH | Closes evidence without database transfer, mutation or Git inclusion | `CR-007/011/012/013/014/015/031 ALIGN_DATA_MODEL`; keep `CR-010` |
| `OD-06` | `OPTION_A` — bounded-context vocabulary owners | HIGH | Respects module ownership and prevents infrastructure/defaults becoming business authority | `CR-015 REWRITE + ALIGN_DATA_MODEL + ADD_TESTS` |
| `OD-07` | `OPTION_A` — deprecate options from active READ-15 | MEDIUM | The current one-field contract is implemented and no consumer requirement supports expansion | `CR-009 DEPRECATE + REWRITE + ADD_TESTS` |
| `OD-08` | `OPTION_A` — generalize durable policy and archive version-specific controls | HIGH | Preserves security and lineage while keeping consumed incident mechanics out of runtime business policy | Keep `CR-036/037/039`; `CR-038 REWRITE + CONSOLIDATE + ADD_TESTS` |

## Recommended technical sequence if, and only if, approved

1. Bind authority and evidence: `OD-01`, `OD-02`, `OD-05`.
2. Freeze explicit rule dispositions before code design.
3. Define Application and vocabulary ownership: `OD-03`, `OD-06`, `OD-07`.
4. Bound transport: `OD-04`.
5. Separate calibration policy from history: `OD-08`.
6. Open a new 12.17.4 design gate; do not combine unrelated implementation lots.

## Architecture guardrails

- No business status or transition is owned by a SQLite adapter.
- No API endpoint talks directly to repositories or SQL.
- No agent output, route success, gate approval or telemetry event grants validation/promotion authority.
- No `shared_kernel` specialization is introduced to centralize business vocabulary.
- Schema evidence is read-only, exact-hash-bound and row-content-free.
- Phase 12.16 history remains immutable; no provider or release-threshold authorization is inferred.
- Tests are added only after rule and owner disposition, never to create the appearance of implementation.

## Confidence interpretation

- `HIGH`: recommendation follows an existing canonical boundary and has direct repository evidence.
- `MEDIUM`: recommendation is safe but depends on missing evidence or product scope.
- `LOW`: evidence would not support a preferred option. No decision in this package has a LOW recommendation.
