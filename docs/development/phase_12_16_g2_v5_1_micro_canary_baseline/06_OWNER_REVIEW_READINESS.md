# V5.1 micro-canary — Owner review readiness

`V5_1_MICRO_CANARY_READINESS = GO_FOR_OWNER_REVIEW`

A future owner authorization must bind all of the following exactly:

- the post-freeze baseline commit SHA reported by the execution handoff;
- parser V5.1 SHA;
- canonical scorer, matrix and pricing SHA values;
- unchanged pedagogical transfer-scope SHA;
- micro-canary call-spec SHA;
- micro-canary transfer-projection SHA;
- one Anthropic call maximum;
- approved ceiling exactly `0.045600 USD`;
- provider `ANTHROPIC_ONLY`;
- no retry and immediate stop after the call.

Until that authorization exists:

- `APPROVED_MICRO_CANARY_CEILING_USD = NONE`
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`
- every future gate exits with `ABORT_BEFORE_CREDENTIALS`.
