# Phase 12.17.3C — Owner attestation application

## Outcome

```text
BASELINE_BINDING = PASS
DECISION_REGISTER_BINDING = PASS
OWNER_ATTESTATION_HASH = PASS
OWNER_DECISION_RESOLUTION = APPROVED
OWNER_ATTESTATION_APPLICATION = APPLIED
OWNER_DECISIONS_SUBMITTED = 8/8
OWNER_DECISIONS_RESOLVED = 8/8
```

The rebound attestation is complete, hash-verifiable and explicitly bound to the exact baseline and Phase 12.17.3A decision register. Its eight choices are allowed, dependency-compatible and identical to the eight registered `OPTION_A` recommendations. All eight owner decisions are applied.

## Verified final attestation

```text
OWNER_DECISION_RESOLUTION = APPROVED

BASELINE_COMMIT = 6d0d66380757d7502fd967cd0246c5b6ff91d5f8
DECISION_REGISTER_SHA256 = 43985ca2cffc4979d59b32466654d541f9084465b7f06b5e00bf81be33cad8f4

OD-01 = OPTION_A
OD-02 = OPTION_A
OD-03 = OPTION_A
OD-04 = OPTION_A
OD-05 = OPTION_A
OD-06 = OPTION_A
OD-07 = OPTION_A
OD-08 = OPTION_A

OWNER_NAME_OR_ROLE = PROJECT_OWNER
OWNER_ATTESTATION = APPROVED
OWNER_ATTESTATION_TIMESTAMP = 2026-09-02T17:25:40+02:00
```

The timestamp is an offset-aware ISO-8601 value and normalizes to `2026-09-02T15:25:40Z`.

The same hash-bound file records these scope clarifications:

- the eight decisions are explicitly approved;
- `EXTERNAL_SCHEMA_EVIDENCE = MISSING` is preserved;
- `OD-05 OPTION_A` authorizes only a later read-only inspection of the exact, physically available and correctly identified SQLite seed;
- `OD-06 OPTION_A` assigns vocabulary ownership by bounded context while keeping stored-value/default validation conditional on SQLite evidence;
- `OD-07 OPTION_A` deprecates `version_ref` and `include` from active READ-15 scope without requiring SQLite evidence;
- no migration, SQLite modification, source-rule change, provider operation or code change is authorized.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Exactly eight choices, `OD-01` through `OD-08` | PASS | 8 unique submitted identifiers |
| Every choice is allowed | PASS | All are `OPTION_A` |
| Choices match register recommendations | PASS | 8/8 exact matches |
| Dependency compatibility | PASS | The eight Option A selections satisfy the declared dependency combinations |
| Owner role present | PASS | `PROJECT_OWNER` |
| Approval present | PASS | `APPROVED` |
| Timestamp present and parseable | PASS | `2026-09-02T17:25:40+02:00` |
| Baseline bound by the submitted attestation | PASS | Bound and observed value: `6d0d66380757d7502fd967cd0246c5b6ff91d5f8` |
| Decision register bound by the submitted attestation | PASS | Bound and observed SHA-256: `43985ca2cffc4979d59b32466654d541f9084465b7f06b5e00bf81be33cad8f4` |
| Completed attestation SHA-256 verifies | PASS | `01_OWNER_ATTESTATION_REBOUND.md` hashes to the declared value |
| Bundle manifest verifies | PASS | 5/5 manifest-bound entries match |
| Bundle state JSON parses | PASS | `STATE.json` is valid JSON |

Repository identities observed during this execution were:

```text
CURRENT_BASELINE_COMMIT = 6d0d66380757d7502fd967cd0246c5b6ff91d5f8
CURRENT_DECISION_REGISTER_SHA256 = 43985ca2cffc4979d59b32466654d541f9084465b7f06b5e00bf81be33cad8f4
```

They match both the contract and the explicit rebound-attestation bindings.

The bundle identities independently verified during this execution were:

```text
BUNDLE_SHA256 = 9763168564e83863ebc8ac1bf0511f90d122baf5eaf9f25d0f9b6065ca4a8127
OWNER_ATTESTATION_FILE = 01_OWNER_ATTESTATION_REBOUND.md
OWNER_ATTESTATION_SHA256_DECLARED = f2f0893c2e2b8b5f8033f142de769cb8193d42d3d7208cd8c6499d2819d1d6f7
OWNER_ATTESTATION_SHA256_OBSERVED = f2f0893c2e2b8b5f8033f142de769cb8193d42d3d7208cd8c6499d2819d1d6f7
BUNDLE_MANIFEST_VALID = 5/5
```

The hash binds the full rebound attestation, including the required identities and scope clarifications.

## Application consequence

The owner-decision blocker is cleared and `OWNER_DECISIONS_RESOLVED` becomes `8/8`. This does not fabricate physical SQLite evidence: the selected `OD-05 OPTION_A` and `OD-06 OPTION_A` path retains a separate external-evidence blocker.
