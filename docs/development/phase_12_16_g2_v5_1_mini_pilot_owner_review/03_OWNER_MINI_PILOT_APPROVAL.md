# V5.1 mini-pilot — Owner approval attestation

The owner explicitly approved the mini-pilot, its exact ceiling, identities,
counts, and four-call allowlist on the frozen baseline. This approval does not
authorize live execution.

```text
OWNER_MINI_PILOT_APPROVAL = APPROVED
AUTHORIZED_BASELINE_COMMIT_SHA = c534b488276eabfa9f82b379282a043cdc0f4b65
AUTHORIZED_PARSER_V5_1_SHA256 = 2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b
AUTHORIZED_SCORER_CONTRACT_SHA256 = a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344
AUTHORIZED_MATRIX_SHA256 = 3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c
AUTHORIZED_PRICING_SHA256 = 31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8
AUTHORIZED_TRANSFER_SCOPE_SHA256 = c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93
VERIFIED_PREPARATION_MANIFEST_SHA256 = 29de80c58735ae66d730857265056bd98bf71a1e840f76d987a20d1a0b900c3c
AUTHORIZED_LOGICAL_OBSERVATION_COUNT = 5
AUTHORIZED_CARRY_FORWARD_COUNT = 1
AUTHORIZED_NEW_CALL_COUNT = 4
APPROVED_MINI_PILOT_CEILING_USD = 0.202400
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE
```

The preparation manifest hash was recomputed as linkage evidence; it is not
presented as an additional owner-supplied authorization field. The explicit
owner values themselves match every canonical identity and count.
