# V5.1 mini-pilot — Final carry-forward proof

The passed micro-canary remains strictly reusable as the strong observation.

- Call ID: `cal.score.anchor.scn-06.strong.marking-scheme-coherence.r1`
- V5.1 call-spec SHA-256: `282b1e562aa24ace1072e0d9612e045c76950d83727a01ca1e840e091608a44e`
- Source call-spec SHA-256: `f897bee689581b1ed126b90dc17b6ff0f5912137d3baffe6980469accc76806e`
- Parser SHA-256: `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b`
- Scorer SHA-256: `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`
- Matrix SHA-256: `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c`
- Pricing SHA-256: `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`
- Transfer projection SHA-256: `e44c8d0ce1a7ed044dc383157d859a16abb8897af7aed43f2bc6c2d71b124eb4`
- Provider/model: `anthropic` / `claude-sonnet-5`
- Scenario/criterion: `SCN-06` / `scn-06.quality.marking-scheme-coherence`
- Anchor: `anchor:cal.v4.scn-06.315be9953fb2`
- Token bounds: `8000 / 2048`
- Certified score: `4`
- Parser/schema: `PASS`
- Provenance: `PASS`
- Raw response persistence: `NONE`
- Live authorization: `CONSUMED`

The strict equality audit covers call-spec, parser, scorer, matrix, pricing,
transfer scope, projection, criterion/anchor, provider/model, token budget, and
certified result state. Every dimension passes.

`MICRO_CANARY_CARRY_FORWARD = TRUE`
