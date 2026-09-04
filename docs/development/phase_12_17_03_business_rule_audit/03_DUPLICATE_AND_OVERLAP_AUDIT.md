# Phase 12.17.3 — Duplicate and overlap audit

## Result

- Exact duplicate groups: **2** (`4` raw occurrences).
- Quasi-duplicate groups: **8** (`22` raw occurrences; an occurrence can also belong to an overlap cluster).
- Overlap clusters: **9** (`55` raw occurrences).
- Repeated validations are present at DTO, port, adapter and orchestration boundaries. They are not automatically redundant: boundary-local rejection is part of defence in depth.
- No source was rewritten or consolidated by this audit.

The counts below use groups, not occurrences. The source of truth is `02_BUSINESS_RULE_REGISTER.json`.

## Exact duplicate groups

| Group | Authoritative rule | Other occurrence | Divergence risk | Recommended disposition |
|---|---|---|---|---|
| `DG-EXACT-01` | `BR-001` / canonical `README.md` | `BR-002` / `AGENTS.md` | Medium: the two policies can drift independently | Consolidate into candidate `CR-001`, retain both enforcement surfaces and name one canonical source |
| `DG-EXACT-02` | `BR-005` / canonical `README.md` plus `.gitignore` | `BR-006` / `AGENTS.md` | Low: wording is currently identical | Consolidate into candidate `CR-003`; keep repository policy and agent guard aligned |

## Quasi-duplicate groups

| Group | Common obligation | Rules | Most authoritative source | Risk | Recommended disposition |
|---|---|---|---|---|---|
| `DG-Q-01` | Business access crosses an Application boundary | `BR-007`, `BR-011`, `BR-014`, `BR-030` | Phase 6/11 architecture and Domain/Application contracts | High if an adapter or agent becomes authoritative | Keep the general boundary in `CR-004`; retain local contract checks |
| `DG-Q-02` | Resource identities and fields are non-empty | `BR-009`, `BR-010` | Application DTO and Domain port | Low | Keep both checks but define the shared invariant in `CR-006`/`CR-007` |
| `DG-Q-03` | Authorization decisions fail closed | `BR-027`, `BR-029`, `BR-031` | Capability authorization policy | High | Consolidate semantics in `CR-017`, `CR-019`, `CR-021`; preserve layer-specific evidence |
| `DG-Q-04` | Outputs, data and telemetry do not grant authority | `BR-034`, `BR-037`, `BR-048` | Runtime authority and observability ADRs | High | Consolidate as one authority invariant referenced by `CR-022`, `CR-024`, `CR-030` |
| `DG-Q-05` | Secrets and sensitive payloads are minimized | `BR-039`, `BR-049` | Security and observability policies | High | Share a canonical redaction/minimization vocabulary, retain separate runtime checks |
| `DG-Q-06` | Generation, review and promotion are distinct | `BR-008`, `BR-053`, `BR-055` | Persistent architecture rule and agent ADRs | High | Consolidate lifecycle semantics in `CR-005`; keep agent-specific contracts |
| `DG-Q-07` | Identity/evidence lineage is immutable | `BR-016`, `BR-061` | Canonical persistence and calibration closure | Medium | Generalize lineage in `CR-010` and `CR-038` without erasing scope-specific proofs |
| `DG-Q-08` | Strong-only calibration is primary; secondary ordering and threshold are non-authoritative | `BR-058`, `BR-059`, `BR-062` | Owner decision and canonical closure | Medium | Consolidate into `CR-037`/`CR-039`; keep release adoption a future owner decision |

## Overlap clusters

| Cluster | Rules | Shared core | Material extensions/exceptions | Candidate rule(s) |
|---|---|---|---|---|
| `OC-GOVERNANCE` | `BR-003`, `BR-004` | Canonical evidence governs reuse and implementation | `EX-01` permits explicit audited legacy reuse | `CR-001`, `CR-002` |
| `OC-APPLICATION_BOUNDARY` | `BR-007`, `BR-065`, `BR-066` | Business operations need a concrete Application owner | `/api/v2` is projected; non-resource capabilities remain absent | `CR-004`, `CR-041` |
| `OC-LIFECYCLE` | `BR-008`, `BR-022`, `BR-024`, `BR-052`–`BR-055`, `BR-063` | State transitions and agent outputs are bounded and separated | `EX-06` permits explicit `DEGRADED` evidence for a declared unavailable channel; review/generation have no promotion authority | `CR-005`, `CR-014`, `CR-031`–`CR-034`, `CR-040` |
| `OC-PERSISTENCE` | `BR-016`–`BR-023` | Seed immutability, runtime copy, migrations and unit of work | `EX-03` adds mutable-runtime concurrency settings; `EX-04` makes identical migration reapplication a verified no-op; external DDL remains required | `CR-010`–`CR-013` |
| `OC-AUTHORITY` | `BR-026`–`BR-033` | Authorization precedes routing and routing grants no business authority | `EX-05` permits continued evaluation after approval but grants no business action | `CR-016`–`CR-022` |
| `OC-SECURITY` | `BR-005`, `BR-006`, `BR-035`–`BR-040`, `BR-049` | Minimize access, transfers, secrets and content exposure | Approved tools and delegation remain governed by their general allowlist rules, not by a broad security exception | `CR-003`, `CR-023`–`CR-026` |
| `OC-RECOVERY` | `BR-041`–`BR-047` | Recovery is deterministic, budgeted and replay-safe | `EX-07` permits retry only for known `EffectState.NONE` under every other guard | `CR-027`–`CR-029` |
| `OC-OBSERVABILITY` | `BR-048`–`BR-050` | Telemetry is minimized, correlated and non-authoritative | `EX-08` isolates a sink failure so it cannot alter the functional outcome | `CR-030` |
| `OC-CALIBRATION` | `BR-056`–`BR-062` | Synthetic evidence, blind scoring and strong-only deliverability | `EX-09` carry-forward; `EX-10` one-shot live authorization; no release threshold | `CR-035`–`CR-039` |

## Repeated validation assessment

The repository inventory reports `156` private validator methods and `16` duplicate-name groups containing `50` definitions. Name equality is only a discovery signal. The reviewed repeated checks fall into three categories:

1. **Intentional boundary validation** — DTO, port, adapter and runner checks reject malformed or unauthorized input close to the boundary. Keep unless a single shared contract can preserve fail-closed behaviour.
2. **Shared semantics expressed locally** — non-empty identity, authorization denial, lineage and redaction. Extracting a common vocabulary is a rationalization candidate, not an audit-time change.
3. **Potential drift** — repeated literal statuses/defaults in SQLite adapters and version-specific calibration guards. These require an owner and contract before consolidation.

`REDUNDANT_IMPLEMENTATION_CONFIRMED = 0`: this audit found overlap and duplication, but it did not prove that removing any individual check would preserve all boundary guarantees.
