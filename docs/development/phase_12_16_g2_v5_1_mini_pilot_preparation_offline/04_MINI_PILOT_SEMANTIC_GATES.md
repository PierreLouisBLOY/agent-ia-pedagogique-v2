# V5.1 mini-pilot — Semantic and fail-closed gates

## Final semantic gates

The future mini-pilot is `PASS` only when all five logical observations satisfy:

- parser/schema `PASS` on 100% of observations;
- every absolute score is in `0..4`;
- SCN-06 strong > intermediate > weak;
- the mixed anchor receives a real intermediate score in `1..3`;
- both pairwise decisions equal their known `A_BETTER` preference;
- neither controlled pairwise comparison produces a false `TIE`;
- evidence-first coverage is present;
- transfer scope and provenance are `PASS`.

Future verdicts are exactly:

- `V5_1_MINI_PILOT_PASS`;
- `V5_1_MINI_PILOT_FAIL`;
- `V5_1_MINI_PILOT_INCONCLUSIVE`.

## Sequential fail-closed execution

The prepared pure-data gate requires this exact order:

1. SCN-06 mixed absolute canary;
2. SCN-06 weak absolute only after the canary passes parser/schema,
   evidence-first, provenance, and returns an intermediate score;
3. SCN-06 pairwise only after the carried strong score and new mixed/weak
   scores establish strict ordering;
4. SCN-01 pairwise only after the first pairwise returns `A_BETTER`.

Any parser/schema/systemic failure stops the sequence. Duplicate call IDs,
out-of-order fanout, retry, rerun, ceiling drift, identity drift, provider drift,
or missing live authorization fail closed before credentials.

Current state:

- provider calls: `0`;
- credentials / transport: `0 / 0`;
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`.
