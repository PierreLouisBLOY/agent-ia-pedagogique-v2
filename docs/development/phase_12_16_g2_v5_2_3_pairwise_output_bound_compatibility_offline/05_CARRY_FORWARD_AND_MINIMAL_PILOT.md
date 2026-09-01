# Carry-forward and minimal pilot

## Carry-forward proof

| Observation | Value | Eligibility | Reissued | Retransmitted |
|---|---:|---|---|---|
| Strong SCN-06 | `4` | `TRUE` | `FALSE` | `FALSE` |
| Weak SCN-06 | `1` | `TRUE` | `FALSE` | `FALSE` |
| Mixed SCN-06 | `0` | `TRUE` | `FALSE` | `FALSE` |

Strong and Mixed pass the unchanged canonical carry-forward audits. Weak passes
all ten safe V5.2.2 audit dimensions: contracts, call spec, projection, parser,
score, evidence-first, provenance, raw absence, consumed authorization and
single emission. The V5.2.3 module does not import, mutate or reparse any absolute
observation.

`STRONG_CARRY_FORWARD = TRUE`

`WEAK_CARRY_FORWARD = TRUE`

`MIXED_CARRY_FORWARD = TRUE`

## Minimal future pilot

- Logical observations: `5`
- Carry-forward: `3`
- New calls: `2`
- Exploitable pairwise carry-forward: `0`
- New calls: SCN-06 pairwise, then SCN-01 pairwise
- Per-call proposed ceiling: `0.055600 USD`
- Exact total proposed ceiling: `0.111200 USD`
- Approval for V5.2.3: `NONE`
- Current live authorization: `FALSE`

The proposed ceiling is recomputed from the unchanged call specifications and
pricing snapshot. The consumed V5.2.2 authorization and its measured cost do not
authorize or reduce a future V5.2.3 run.

`PROPOSED_V5_2_3_CEILING_USD = 0.111200`

`APPROVED_V5_2_3_CEILING_USD = NONE`
