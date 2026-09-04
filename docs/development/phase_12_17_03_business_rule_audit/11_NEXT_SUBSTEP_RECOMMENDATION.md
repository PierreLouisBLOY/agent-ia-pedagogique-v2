# Phase 12.17.3 — Next substep recommendation

## Recommendation

`NEXT_RECOMMENDED_SUBSTEP = 12.17.4_RATIONALIZATION_DESIGN_GATE`

Phase 12.17.4 should begin only after the eight decisions in `10_PRIORITIZATION_AND_OWNER_DECISIONS.md` have explicit dispositions and the required evidence is available. This document does **not** start 12.17.4.

## Entry criteria

- Phase 1/2 source authority is identified or its absence is formally accepted.
- The legacy-reuse trace disposition is explicit.
- The exact external SQLite seed is authorized for read-only, hash-bound schema inspection if data-model closure is desired.
- Application ownership and sequencing are chosen for CAP-R02, CAP-A01, CAP-A02 and `/api/v2`.
- SQLite status/default vocabulary ownership is assigned.
- READ-15 deferred options receive an explicit scope decision.
- Calibration history, reusable policy and future threshold governance are separated by owner decision.
- The `41` candidate rules and `10` candidate exceptions are approved, amended or rejected individually.

## Proposed 12.17.4 outputs, not actions in this phase

- an owner-approved canonical rule authority index;
- a rule-by-rule disposition map from `BR-*` to approved canonical IDs;
- a no-code dependency/order plan for later remediation lots;
- explicit acceptance criteria for Domain, Application, persistence, API and test changes;
- a preservation plan for historical manifests and superseded rules.

## Guardrails

- No automatic rewrite or deletion of source rules.
- No consolidation based only on validator or enum name equality.
- No database claim without the external schema evidence.
- No API before an authoritative Application use case.
- No provider call, calibration rerun, runtime route change or release-threshold adoption.
- No remediation lot may combine unrelated bounded contexts merely to reduce rule count.

If any entry criterion remains unresolved, the next action is an owner/evidence gate, not implementation.
