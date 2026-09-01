# V5.1 mini-pilot — Owner review readiness

The offline preparation is ready for owner review. It does not constitute
financial approval, transfer authorization on the future freeze baseline, or
live authorization.

Owner review must bind any later authorization to:

- the local freeze baseline commit reported after commit creation;
- parser SHA-256
  `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b`;
- scorer SHA-256
  `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`;
- matrix SHA-256
  `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c`;
- pricing SHA-256
  `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`;
- unchanged transfer-scope SHA-256
  `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93`;
- exactly four new calls and the four call-spec/projection pairs listed in
  `02_MINI_PILOT_SELECTION.md`;
- proposed ceiling `0.202400 USD`;
- Anthropic only, no retry, no rerun, and immediate fail-closed sequencing.

Current approval state:

- `APPROVED_MINI_PILOT_CEILING_USD = NONE`
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`
- `V5_1_MINI_PILOT_READINESS = GO_FOR_OWNER_REVIEW`
