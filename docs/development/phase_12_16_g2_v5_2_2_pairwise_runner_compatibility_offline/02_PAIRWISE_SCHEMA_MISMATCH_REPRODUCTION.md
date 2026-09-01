# Pairwise schema mismatch reproduction

`PAIRWISE_SCHEMA_MISMATCH_REPRODUCED = TRUE`

The failure was reproduced offline with both exact authorized pairwise envelopes.
The former local helper in `.tmp/live_mini_pilot_v5_1.py` read these flat fields:

- `candidate_a_id`
- `candidate_a_projection`
- `candidate_b_id`
- `candidate_b_projection`

The canonical V5 pairwise contract supplies:

- `candidate_a = {candidate_id, projection}`
- `candidate_b = {candidate_id, projection}`

Both SCN-06 and SCN-01 therefore raised `PAIRWISE_PROJECTION_INVALID` under the
former helper. The provider stop occurred before the second transfer, so neither
pairwise projection was emitted.

- Former helper source SHA-256: `230ed083e8311d423bd48067137cfef122c7a5f7a4533ce80620a3184c7bdece`
- Provider calls during reproduction: `0`
- Credentials/transports resolved: `0/0`
