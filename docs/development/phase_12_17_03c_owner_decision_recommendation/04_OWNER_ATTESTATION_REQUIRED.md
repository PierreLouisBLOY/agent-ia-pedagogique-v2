# Phase 12.17.3C — Explicit owner attestation required

## Why execution stops here

The bundle recommends all eight Option A choices, but labels its decision record “attestation proposée”. It has no affirmative owner approval, identity/role, timestamp or completed hash. The instruction “do not take decisions in place of the owner” therefore remains controlling.

## Minimal explicit owner response

The owner may approve all recommendations by returning the following block, completed without changing the bound identities:

```text
OWNER_DECISION_RESOLUTION = APPROVED
AUTHORIZED_BASELINE_COMMIT = 6d0d66380757d7502fd967cd0246c5b6ff91d5f8
AUTHORIZED_DECISION_REGISTER_SHA256 = 43985ca2cffc4979d59b32466654d541f9084465b7f06b5e00bf81be33cad8f4

OD-01 = OPTION_A
OD-02 = OPTION_A
OD-03 = OPTION_A
OD-04 = OPTION_A
OD-05 = OPTION_A
OD-06 = OPTION_A
OD-07 = OPTION_A
OD-08 = OPTION_A

OWNER_NAME_OR_ROLE = <required>
OWNER_ATTESTATION = APPROVED
```

For `OD-05`, this selection approves the evidence mode but does not identify a local file. A later read-only schema inspection still requires the exact local path and must verify size and SHA-256 before opening SQLite.

For `OD-06`, Option A selects bounded-context ownership; no stored-value alignment or migration conclusion is authorized before schema evidence.

For `OD-07`, Option A is independent of SQLite and deprecates `version_ref` and `include` from the active READ-15 scope.

## Current attestation state

```text
EXPLICIT_OWNER_APPROVAL = MISSING
OWNER_IDENTITY_OR_ROLE = MISSING
OWNER_DECISIONS_RESOLVED = 0/8
OWNER_DECISION_EXECUTION = BLOCKED_EXPLICIT_ATTESTATION_REQUIRED
```

No code, source rule, database, migration, provider, commit or push action is authorized by the proposed template alone.
