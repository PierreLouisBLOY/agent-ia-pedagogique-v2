# Phase 12.16 — Final live evidence

## V5.2.4 execution

The final live operation was the single authorized call `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1` on baseline `8b0c8bd43a988acf163b195cf0aed13024e379aa`.

| Evidence | Result |
| --- | --- |
| Attempted / completed / failed / skipped | `1 / 1 / 0 / 0` |
| Provider split | Anthropic `1`, OpenAI `0` |
| Retry / rerun | `0 / 0` |
| Decision | `A_BETTER` |
| Expected decision | `A_BETTER` |
| Exact measured cost | `0.009908 USD` |
| Authorized ceiling | `0.055600 USD` |
| Remaining margin | `0.045692 USD` |
| Input / output / total tokens | `1944 / 602 / 2546` |
| Raw response persisted | `false` |

The four carry-forward observations were neither reissued nor retransmitted. The final evidence set therefore contains five logical observations while using exactly one new provider call.

## Integrity proofs

| Proof | SHA-256 |
| --- | --- |
| Safe report JSON | `5737b84fe1be85d9c033328d48de4c086b0251e4d7f0722139b84a9b7cbfdce7` |
| Execution ledger JSON | `64a2c2a2ef8e29adae3c85fed8d5c9b80b459b06fac01088caa6ab5e8260ec7d` |
| Final live evidence manifest | `a3c6a2d69749f9caa1abf9e05fd195ffcdf0a80f02ad651c1acd4cf3eea270b7` |

The recomputed hashes match the approved closure inputs. The ledger records response receipt before parser completion, parser/schema `PASS`, evidence-first presence and transfer provenance `PASS`.

## Final live state

- `V5_2_4_MINI_PILOT_PASS`
- `PHASE_12_16_CLOSURE_READINESS = READY`
- `LIVE_AUTHORIZATION = CONSUMED`
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`
- `PUSH = NONE`
