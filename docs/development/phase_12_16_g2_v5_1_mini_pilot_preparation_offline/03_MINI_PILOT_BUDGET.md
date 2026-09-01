# V5.1 mini-pilot — Exact offline budget

Canonical pricing identity:
`31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`.

The calculation uses each call's own input and output bounds, canonical model
pricing, and the canonical `1.25` safety multiplier.

| Call | Input bound | Output bound | Maximum before margin | Proposed ceiling |
|---|---:|---:|---:|---:|
| SCN-06 mixed absolute | 8,000 | 2,048 | `0.036480 USD` | `0.045600 USD` |
| SCN-06 weak absolute | 8,000 | 2,048 | `0.036480 USD` | `0.045600 USD` |
| SCN-06 pairwise | 12,000 | 2,048 | `0.044480 USD` | `0.055600 USD` |
| SCN-01 pairwise | 12,000 | 2,048 | `0.044480 USD` | `0.055600 USD` |

- Maximum before margin: `0.161920 USD`
- Safety margin: `0.040480 USD`
- `PROPOSED_MINI_PILOT_CEILING_USD = 0.202400`
- `APPROVED_MINI_PILOT_CEILING_USD = NONE`

The ceiling is deliberately not `0.045600 × 4`; the pairwise calls have larger
input bounds and therefore distinct exact ceilings.
