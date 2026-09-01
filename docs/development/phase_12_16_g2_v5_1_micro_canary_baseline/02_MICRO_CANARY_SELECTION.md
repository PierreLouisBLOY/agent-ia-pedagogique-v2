# V5.1 micro-canary — Selection

The selected call is the first Anthropic call in the frozen robust plan and the
same semantic case that exposed the original parser incompatibility.

- `MICRO_CANARY_CALL_ID = cal.score.anchor.scn-06.strong.marking-scheme-coherence.r1`
- Provider/model: `anthropic / claude-sonnet-5`
- Scenario/criterion: `SCN-06 / scn-06.quality.marking-scheme-coherence`
- Source canonical call-spec SHA-256:
  `f897bee689581b1ed126b90dc17b6ff0f5912137d3baffe6980469accc76806e`
- `MICRO_CANARY_CALL_SPEC_SHA256 = 282b1e562aa24ace1072e0d9612e045c76950d83727a01ca1e840e091608a44e`
- `MICRO_CANARY_TRANSFER_PROJECTION_SHA256 = e44c8d0ce1a7ed044dc383157d859a16abb8897af7aed43f2bc6c2d71b124eb4`

The projection hash is the SHA-256 of the exact allowlisted transfer envelope:
model, max output tokens, system instructions, minimized input payload and output
schema. It does not expose the projection content.

The dedicated call-spec identity additionally binds parser, scorer, matrix,
pricing and transfer-scope hashes.
