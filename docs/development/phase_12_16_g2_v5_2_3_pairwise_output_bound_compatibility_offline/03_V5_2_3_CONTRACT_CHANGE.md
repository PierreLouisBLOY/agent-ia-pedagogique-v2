# V5.2.3 contract change

Implementation:

- module: `tests/calibration/pedagogical/pairwise_output_contract_v5_2_3.py`
- version: `12.16-g2-v5.2.3-pairwise-output-bound-v1`
- new local parser/output-contract SHA-256: `285179c2b104a14837c2065e229aa89b6b93e2dfba4e75ebcaf9c416c5fb3508`
- scope: pairwise output compatibility overlay only
- old/new observation maximum: `180 / 256`
- base V5.1 parser SHA-256: `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b`
- scorer semantic contract SHA-256: `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`

The overlay introduces versioned `V523PairwiseDifference` and
`V523PairwiseOutcome` models, a local acceptance schema and a safe response
processor. It preserves the existing pairwise decision invariants:

- a tie cannot contain a material difference;
- a winner requires a material difference favoring that candidate;
- conflicting material winners fail closed.

Outer whitespace normalization is unchanged. Content is never shortened,
summarized or truncated. Lengths `180`, `181`, `191`, `255` and `256` pass
unchanged. Length `257` fails closed with a safe diagnostic and no raw content.

Usage and exact cost metadata are persisted before parsing. Raw provider text is
never persisted by the compatibility processor.

The V5 scorer module, V5.1 parser contract, semantic gate and current provider
transfer envelopes are not modified. The V5.2.3 acceptance schema is an offline
overlay for technical freeze and owner review; this sub-step does not bind a live
runner or authorize transport.

`SILENT_TRUNCATION = FORBIDDEN`

`PAIRWISE_MAX_PLUS_ONE_POLICY = FAIL_CLOSED`
