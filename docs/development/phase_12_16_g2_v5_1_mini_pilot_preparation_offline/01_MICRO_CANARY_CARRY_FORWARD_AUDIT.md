# V5.1 mini-pilot — Micro-canary carry-forward audit

## Certified source

- Call ID: `cal.score.anchor.scn-06.strong.marking-scheme-coherence.r1`
- Live baseline: `02f7f69fefcdd0249c712e20c7fe7fc8fc30ee04`
- Result: score level `4`, adapter `PASS`, parser/schema `PASS`
- Safe report SHA-256:
  `858bc21c8ad10c88b95219afbaf57ffc892ae57165274fd0cc0af5f2a0513fa7`
- Ledger SHA-256:
  `baf9dc746a0b82a4c27ac98f578126e11e3e6ee6ebbd23da963a9bb304ac1f61`
- Raw response persistence: `NONE`
- Live authorization: `CONSUMED`

## Strict equality audit

| Identity dimension | Certified value | Result |
|---|---|---|
| V5.1 call-spec SHA-256 | `282b1e562aa24ace1072e0d9612e045c76950d83727a01ca1e840e091608a44e` | `PASS` |
| Source call-spec SHA-256 | `f897bee689581b1ed126b90dc17b6ff0f5912137d3baffe6980469accc76806e` | `PASS` |
| Parser SHA-256 | `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b` | `PASS` |
| Scorer SHA-256 | `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344` | `PASS` |
| Matrix SHA-256 | `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c` | `PASS` |
| Pricing SHA-256 | `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8` | `PASS` |
| Transfer-scope SHA-256 | `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93` | `PASS` |
| Transfer projection SHA-256 | `e44c8d0ce1a7ed044dc383157d859a16abb8897af7aed43f2bc6c2d71b124eb4` | `PASS` |
| Scenario / criterion | `SCN-06` / `scn-06.quality.marking-scheme-coherence` | `PASS` |
| Anchor identity | `anchor:cal.v4.scn-06.315be9953fb2` | `PASS` |
| Provider / model | `anthropic` / `claude-sonnet-5` | `PASS` |
| Input / output bounds | `8000` / `2048` | `PASS` |

All strict comparisons are implemented as pure-data checks in
`semantic_mini_pilot_v5_1.py`; any drift makes the carry-forward ineligible.

`MICRO_CANARY_CARRY_FORWARD = TRUE`
