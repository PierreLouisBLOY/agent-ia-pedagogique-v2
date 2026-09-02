# Exhaustive pairwise text-bound inventory

The inventory covers every string value accepted by the V5.2.3 pairwise output
schema. Fields named `evidence`, `reason`, `summary`, `verdict`, or `explanation`
do not exist in this output contract; therefore no hidden bound is assigned to
them.

| Field | Semantic role | V5.2.3 bound | Available evidence | Provider overrun risk | V5.2.4 bound | Decision |
| --- | --- | ---: | --- | --- | ---: | --- |
| `differences[*].locator_a` | Location in candidate A | 1..64 chars | Synthetic fixtures; live safe diagnostic at 80 | Proven | 1..128 chars | Raise |
| `differences[*].locator_b` | Symmetric location in candidate B | 1..64 chars | Synthetic fixtures; same provider-generated locator grammar | High by symmetry | 1..128 chars | Raise |
| `differences[*].observation` | Evidence-grounded comparison | 1..256 chars | Historical observed value at 191; boundary fixtures | Covered | 1..256 chars | Keep |
| `rationale` | Concise overall justification | 1..240 chars | Existing fixtures; no overrun diagnostic | No demonstrated gap | 1..240 chars | Keep |
| `decision` | Closed pairwise disposition | enum: `A_BETTER`, `B_BETTER`, `TIE`; max token 8 | Contract fixtures | None outside unknown-value failure | Same enum | Keep |
| `confidence` | Closed confidence | enum: `LOW`, `MEDIUM`, `HIGH`; max token 6 | Contract fixtures | None outside unknown-value failure | Same enum | Keep |
| `differences[*].significance` | Closed materiality | enum: `MATERIAL`, `NON_MATERIAL`, `OUT_OF_SCOPE`; max token 12 | Contract fixtures | None outside unknown-value failure | Same enum | Keep |
| `differences[*].favored_candidate` | Closed local preference | enum: `A`, `B`, `NEITHER`; max token 7 | Contract fixtures | None outside unknown-value failure | Same enum | Keep |
| Complete response | UTF-8 structured response envelope | None | V5.2.3 live lengths 1,890 and 1,444 chars; theoretical max-bound compact fixture 5,274 bytes | Unbounded whitespace/envelope growth | 1..8,192 bytes | Add |

## Justification

`128` doubles the old locator allowance, accepts the observed value `80`, and
retains 48 characters of headroom without creating an effectively unbounded
field. The symmetric A/B pair uses one profile to prevent field-by-field drift.

The observation stays at `256`: it already accepts the historical 191-character
value with 65 characters of headroom. The rationale stays at `240` because no
real or fixture evidence justifies widening it.

The global `8,192`-byte ceiling is 2,918 bytes above a compact response using
eight differences and every free-text field at its individual maximum. It
allows normal JSON serialization overhead while rejecting pathological payload
growth before parsing.
