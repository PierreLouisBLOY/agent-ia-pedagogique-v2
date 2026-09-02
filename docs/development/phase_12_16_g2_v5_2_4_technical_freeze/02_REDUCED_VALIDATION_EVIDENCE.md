# V5.2.4 reduced validation evidence

No global suite was executed.

| Validation | Result |
| --- | --- |
| V5.2.4 targeted contract tests | `29 passed` |
| Ruff on contract and principal test | PASS |
| Strict mypy on the two-file scope, imports skipped, pytest decorator exception only | PASS |
| Compileall on contract and principal test | PASS |
| `git diff --check` | PASS |
| SCN-01 call-spec/projection identity | PASS |
| Carry-forward hash-bound proof | `4/4` PASS |
| Single-call budget | `0.055600 USD` PASS |
| Live default closed | PASS |

The targeted tests cover locator values `64`, `65`, `80`, `127`, `128`, and
fail-closed `129` for both candidates; observation `191`, `255`, `256`, and
fail-closed `257`; rationale `239`, `240`, and fail-closed `241`; total output
`8192` and fail-closed `8193` UTF-8 bytes; no truncation; nested payload;
ambiguity; safe persistence; carry-forward; identities; budget; and contract
hash.

- provider calls: `0`
- credentials resolved: `0`
- transports opened: `0`
- retry/rerun: `0/0`
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`
