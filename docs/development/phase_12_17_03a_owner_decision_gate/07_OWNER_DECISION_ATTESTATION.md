# Phase 12.17.3A — Owner decision attestation

## Binding context

```text
ATTESTATION_SCHEMA = 12.17.3a-owner-decision-attestation-v1
BASELINE_COMMIT = 6d0d66380757d7502fd967cd0246c5b6ff91d5f8
DECISION_REGISTER_SHA256 = 43985ca2cffc4979d59b32466654d541f9084465b7f06b5e00bf81be33cad8f4
OWNER_DECISION_COUNT = 8
ALLOWED_CHOICES = APPROVE_RECOMMENDATION | OPTION_A | OPTION_B | OPTION_C | DEFER
```

`APPROVE_RECOMMENDATION` means the recommendation recorded for that exact decision in the hash-bound register. In the current register, every recommendation maps to `OPTION_A`; this mapping must not be assumed after any register change.

`DEFER` is a valid owner response but does not resolve the decision for 12.17.4 readiness unless a separate owner statement explicitly removes that subject from the 12.17.4 scope.

## Choices to complete

No choice is preselected.

```text
OD_01_CHOICE = <APPROVE_RECOMMENDATION | OPTION_A | OPTION_B | OPTION_C | DEFER>
OD_01_OWNER_NOTE = <optional>

OD_02_CHOICE = <APPROVE_RECOMMENDATION | OPTION_A | OPTION_B | OPTION_C | DEFER>
OD_02_OWNER_NOTE = <optional>

OD_03_CHOICE = <APPROVE_RECOMMENDATION | OPTION_A | OPTION_B | OPTION_C | DEFER>
OD_03_OWNER_NOTE = <optional>

OD_04_CHOICE = <APPROVE_RECOMMENDATION | OPTION_A | OPTION_B | OPTION_C | DEFER>
OD_04_OWNER_NOTE = <optional>

OD_05_CHOICE = <APPROVE_RECOMMENDATION | OPTION_A | OPTION_B | OPTION_C | DEFER>
OD_05_OWNER_NOTE = <optional>

OD_06_CHOICE = <APPROVE_RECOMMENDATION | OPTION_A | OPTION_B | OPTION_C | DEFER>
OD_06_OWNER_NOTE = <optional>

OD_07_CHOICE = <APPROVE_RECOMMENDATION | OPTION_A | OPTION_B | OPTION_C | DEFER>
OD_07_OWNER_NOTE = <optional>

OD_08_CHOICE = <APPROVE_RECOMMENDATION | OPTION_A | OPTION_B | OPTION_C | DEFER>
OD_08_OWNER_NOTE = <optional>
```

## Owner declaration

```text
OWNER_ATTESTATION = <APPROVED | NOT_APPROVED>
OWNER_NAME_OR_ROLE = <required>
OWNER_ATTESTED_AT_UTC = <required ISO-8601>
COMPLETED_ATTESTATION_SHA256 = <computed only after completion>
```

By setting `OWNER_ATTESTATION = APPROVED`, the owner confirms that:

- exactly one allowed choice is supplied for each of `OD-01` through `OD-08`;
- the decision register hash and baseline commit above are the reviewed identities;
- dependency constraints and external-evidence requirements are accepted;
- a recommendation was not silently substituted for an owner choice;
- the attestation authorizes design-gate readiness only, not code changes, migrations, provider calls, database transfer, commit or push.

## Current state

```text
ATTESTED_DECISION_COUNT = 0
UNRESOLVED_DECISION_COUNT = 8
OWNER_ATTESTATION = NOT_COMPLETED
PHASE_12_17_4_RATIONALIZATION_DESIGN_GATE = BLOCKED_OWNER_DECISIONS
```
