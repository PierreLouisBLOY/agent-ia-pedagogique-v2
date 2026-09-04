# Phase 12.17.3A — Owner decision index

## Gate state

- Source audit: `PHASE_12_17_03_BUSINESS_RULE_AUDIT = PASS`.
- Baseline commit: `6d0d66380757d7502fd967cd0246c5b6ff91d5f8`.
- `OWNER_DECISION_COUNT = 8`.
- Resolved: `0`.
- Unresolved: `8`.
- `PHASE_12_17_4_RATIONALIZATION_DESIGN_GATE = BLOCKED_OWNER_DECISIONS`.

No recommendation in this package is an owner decision. A decision changes state only when `07_OWNER_DECISION_ATTESTATION.md` is completed with one allowed choice for each ID and its integrity is verified.

## Decision index

| ID | Decision | Candidate rules | Class | SQLite external evidence | Recommendation | Confidence | State |
|---|---|---|---|---:|---|---|---|
| `OD-01` | Phase 1/2 source authority | `CR-002` | Independent root | FALSE | A — bind original corpus | MEDIUM | UNRESOLVED |
| `OD-02` | Legacy-reuse trace disposition | `CR-001`, `EX-01` | Independent root | FALSE | A — retrospective canonical trace | HIGH | UNRESOLVED |
| `OD-03` | Application owners for CAP-R02/A01/A02 | `CR-005`, `CR-031`, `CR-041` | Depends on `OD-01` | FALSE | A — three bounded owners | HIGH | UNRESOLVED |
| `OD-04` | First `/api/v2` scope | `CR-006`–`CR-008`, `CR-041` | Conditional on `OD-03` | FALSE | A — Resource READ-15 only | HIGH | UNRESOLVED |
| `OD-05` | External SQLite schema evidence | `CR-007`, `CR-010`–`CR-015`, `CR-031` | Independent root | TRUE | A — hash-bound read-only introspection | HIGH | UNRESOLVED |
| `OD-06` | Ownership of ten persistence literal families | `CR-015` | Depends on `OD-05` | TRUE | A — bounded-context vocabulary | HIGH | UNRESOLVED |
| `OD-07` | READ-15 `version_ref`/`include` scope | `CR-009` | Depends on `OD-01` | TRUE for implementation option | A — deprecate from active scope | MEDIUM | UNRESOLVED |
| `OD-08` | Durable calibration governance | `CR-036`–`CR-039` | Independent root | FALSE | A — generalize and archive history | HIGH | UNRESOLVED |

## Counts

- Independent root decisions: **4** — `OD-01`, `OD-02`, `OD-05`, `OD-08`.
- Dependent decisions: **4** — `OD-03`, `OD-04`, `OD-06`, `OD-07`.
- Decisions marked `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE`: **3** — `OD-05`, `OD-06`, `OD-07`.
- Decisions blocking 12.17.4 now: **8**.

## Reading order

1. Use `02_OWNER_DECISION_REGISTER.json` as the machine-readable source.
2. Compare options and eight impact dimensions in `03_OPTIONS_AND_IMPACT_ANALYSIS.md`.
3. Respect ordering from `04_DECISION_DEPENDENCY_GRAPH.md`.
4. Review recommendations and evidence boundaries in files `05` and `06`.
5. Record choices only in `07_OWNER_DECISION_ATTESTATION.md`.
6. Re-evaluate readiness using `08_12_17_4_READINESS.md`.
