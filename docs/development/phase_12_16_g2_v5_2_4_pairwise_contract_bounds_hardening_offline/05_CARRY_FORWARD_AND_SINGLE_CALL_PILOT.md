# Carry-forward and proposed single-call pilot

The V5.2.3 safe report and ledger are hash-bound before their values are used.
The carry-forward proof establishes:

- Strong SCN-06 = `4`: TRUE
- Weak SCN-06 = `1`: TRUE
- Mixed SCN-06 = `0`: TRUE
- Pairwise SCN-06 = `A_BETTER`: TRUE

The SCN-06 pairwise safe record is `COMPLETED`, schema `PASS`, contains no raw
response, and retains the authorized projection SHA-256
`e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8`.
It is reusable without provider recall or retransmission.

`CARRY_FORWARD = 4/4 TRUE`

## Proposed V5.2.4 mini-pilot

- logical observations: `5`
- carry-forward: `4`
- new calls: `1`
- only new call: `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1`
- proposed ceiling: `0.055600 USD`
- approved ceiling: `NONE`

`PROPOSED_V5_2_4_CEILING_USD = 0.055600`

`APPROVED_V5_2_4_CEILING_USD = NONE`

This is a readiness proposal only. It does not authorize a provider call.
