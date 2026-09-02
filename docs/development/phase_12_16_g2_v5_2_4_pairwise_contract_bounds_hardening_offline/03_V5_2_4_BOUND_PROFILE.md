# V5.2.4 bound profile

## Profile

| Constraint | V5.2.3 | V5.2.4 |
| --- | ---: | ---: |
| `locator_a` | 64 chars | 128 chars |
| `locator_b` | 64 chars | 128 chars |
| `differences[*].observation` | 256 chars | 256 chars |
| `rationale` | 240 chars | 240 chars |
| `differences` cardinality | 1..8 | 1..8 |
| Complete structured response | unbounded | 1..8,192 UTF-8 bytes |

All enum sets and semantic invariants remain unchanged. Text normalization is
limited to stripping outer whitespace. No field is truncated. Values beyond an
individual bound, a closed enum, or the response-size ceiling fail closed.

## Boundary matrix

- locator A and B PASS at old max `64`, old max + 1 `65`, observed `80`, new max
  - 1 `127`, and new max `128`;
- locator A and B FAIL CLOSED at `129`;
- observation PASS at `191`, `255`, and `256`, then FAIL CLOSED at `257`;
- rationale PASS at `239` and `240`, then FAIL CLOSED at `241`;
- a valid JSON object padded to exactly `8,192` UTF-8 bytes passes;
- the same object at `8,193` bytes fails closed before JSON parsing;
- nested A/B input passes and mixed nested/flat input fails closed;
- ambiguous `decision = BETTER` fails closed;
- no-truncation assertions compare every accepted boundary value byte-for-byte.

## Contract identity

- version: `12.16-g2-v5.2.4-comprehensive-pairwise-bounds-v1`
- base V5.2.3 contract: `285179c2b104a14837c2065e229aa89b6b93e2dfba4e75ebcaf9c416c5fb3508`
- V5.2.4 logical contract/parser SHA-256:
  `8a40ce2abfbb8fce7b1dd22526d8a30322f6f13749817fe6443c414e4a89b444`
- V5.2.4 implementation file SHA-256:
  `3f47351e8d188ddd7ed465a3d139cad8fd55c03c274ae259a385eaaf3a953a56`
- V5.2.4 boundary test file SHA-256:
  `c6eb0839c17533e7dd78e0de9e99c0140d615d0d13a8a6c5192908137cf936b7`

The new contract identity requires a technical freeze and explicit owner rebind
before any future live authorization.
