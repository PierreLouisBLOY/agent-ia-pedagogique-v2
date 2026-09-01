# V5.1 — Provider-to-contract adapter design

The new offline adapter is
`tests/calibration/pedagogical/semantic_parser_adapter_v5_1.py`.

## Closed normalization policy

- Enum values: trim outer whitespace, uppercase, and normalize whitespace or
  hyphens to underscores.
- Bounded prose and locators: trim outer whitespace only.
- Check identifiers: casefold only when the result is exactly one check id from
  the active canonical rubric.
- Explicit decision aliases only: `A -> A_BETTER`, `B -> B_BETTER`, and
  `EQUAL -> TIE`.
- The deliberately ambiguous token `BETTER` fails; it cannot select A or B.
- Unknown values, ambiguous aliases, invalid types, missing fields, extra fields
  and exceeded bounds all fail closed.
- No default value is ever injected.

After adaptation, the normalized object is passed to the unchanged V5 canonical
parser. Evidence coverage, score derivation and pairwise semantic invariants
therefore remain authoritative.

## Identity

- V5.1 parser contract SHA-256:
  `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b`
- Canonical V5 scorer contract SHA-256:
  `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`
- Canonical contract changed: `FALSE`
