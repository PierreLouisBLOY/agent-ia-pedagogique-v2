# V5.1 — Usage-before-parse telemetry

`process_anthropic_v5_1_response()` now imposes this order:

1. receive the typed Anthropic response;
2. validate token usage;
3. calculate exact cost from the frozen pricing snapshot;
4. persist usage, exact cost, stop reason, response hash and response length;
5. parse and apply the canonical semantic invariants;
6. persist either the safe outcome summary or the privacy-safe diagnostic.

The first persistence callback is therefore completed while parser status is
`PENDING`. A later parse failure cannot erase measured usage.

The exact-cost fixture uses 1,000 input tokens, including 100 cached tokens, and
500 output tokens. At the frozen Claude Sonnet 5 prices the persisted cost is
`0.006820 USD`, even though parsing subsequently fails.

The truncated-response fixture also persists usage and cost before emitting
`RESPONSE_TRUNCATED`.
