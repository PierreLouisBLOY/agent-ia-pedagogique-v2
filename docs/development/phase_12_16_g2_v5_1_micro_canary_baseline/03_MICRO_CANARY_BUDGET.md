# V5.1 micro-canary — Exact budget

The ceiling is calculated from the selected call, not by dividing the robust
pilot ceiling.

- Maximum conservative input tokens: `8,000`
- Maximum output tokens: `2,048`
- Anthropic input price: `2.00 USD / 1M tokens`
- Anthropic output price: `10.00 USD / 1M tokens`
- Maximum before margin: `0.036480 USD`
- Canonical safety multiplier: `1.25`
- Safety margin: `0.009120 USD`
- `PROPOSED_MICRO_CANARY_CEILING_USD = 0.045600`
- `APPROVED_MICRO_CANARY_CEILING_USD = NONE`

The robust ceiling divided by 21 is not equal to this call-specific result and is
not used.
