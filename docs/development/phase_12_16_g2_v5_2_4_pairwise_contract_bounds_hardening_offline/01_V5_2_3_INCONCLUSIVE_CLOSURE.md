# V5.2.3 inconclusive closure

## Canonical input

- baseline commit: `0fd7c9f5198011a0388999050631b46681f631b3`
- V5.2.3 logical output contract: `285179c2b104a14837c2065e229aa89b6b93e2dfba4e75ebcaf9c416c5fb3508`
- V5.2.3 run manifest: `5fb12214d3d1a50e04fbecc38f66c0e7ebd9be03550588ddc32e51272e103312`
- safe report: `83e6276a5cf8204e92863e00bddd94f06d34ba49c4c7344271d01d5597c13209`
- safe ledger: `0a671ec0dc262b5727e9baba164f5b39dba97746a6fd740ae13ae2eb07e938fd`
- verdict: `V5_2_3_MINI_PILOT_INCONCLUSIVE`

## Closure finding

The SCN-06 pairwise observation completed as `A_BETTER`. SCN-01 remained
unusable because `$.differences[2].locator_a` had an observed trimmed length of
exactly `80`, while V5.2.3 accepted at most `64`.

An offline fixture containing an 80-character `locator_a` reproduces the exact
V5.2.3 `OUT_OF_BOUNDS` diagnostic at the same field path and expected constraint.

`PAIRWISE_LOCATOR_80_REPRODUCED = TRUE`

No provider response was reconstructed. The raw SCN-01 response remains absent.
No live authorization is available or implied by this remediation.

- `PROVIDER_CALLS = 0`
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`
- `COMMIT = NONE`
- `PUSH = NONE`
