# Phase 12.16-G2-V5.2 — Attestation propriétaire approuvée

## Statut effectif

```text
OWNER_V5_2_MINI_PILOT_APPROVAL = APPROVED
APPROVED_V5_2_MINI_PILOT_CEILING_USD = 0.156800
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE
```

Cette décision propriétaire a été reçue explicitement le `2026-09-01`. Elle
approuve la configuration et le plafond du mini-pilote, mais ne constitue pas une
autorisation live.

## Configuration exacte présentée au propriétaire

```text
BASELINE_COMMIT_SHA = c534b488276eabfa9f82b379282a043cdc0f4b65
PARSER_V5_1_SHA256 = 2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b
SCORER_CONTRACT_SHA256 = a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344
MATRIX_SHA256 = 3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c
PRICING_SHA256 = 31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8
V5_2_GATE_CONTRACT_SHA256 = 8dc0bdb7ca57c586ac8db887fcb7078e16377e1f8ae30f2d153096ce630c7eea
PEDAGOGICAL_TRANSFER_SCOPE_SHA256 = c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93
AUTHORIZED_LOGICAL_OBSERVATION_COUNT = 5
AUTHORIZED_CARRY_FORWARD_COUNT = 2
AUTHORIZED_NEW_CALL_COUNT = 3
AUTHORIZED_STRONG_EXPECTED_SCORE = 4
AUTHORIZED_MIXED_EXPECTED_SCORE = 0
AUTHORIZED_WEAK_EXPECTED_SCORE = 1
INTERMEDIATE_ANCHOR_AVAILABLE = FALSE
PROPOSED_V5_2_MINI_PILOT_CEILING_USD = 0.156800
```

## Trois identités à approuver sans abréviation

```text
CALL_ID_1 = cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1
CALL_SPEC_SHA256_1 = a3646f66bd0d274cf30daf3024bbad5d204bb0d8182963460107243a0d81b707
PROJECTION_SHA256_1 = 8faf88c7f863294591d8ed3c47812db1d69edd8c38aafc98a1345f431f1af2dc
CALL_CEILING_USD_1 = 0.045600

CALL_ID_2 = cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1
CALL_SPEC_SHA256_2 = 691794a224c1f440225dca29dddf34aff90c6556210c583263b006607509c196
PROJECTION_SHA256_2 = e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8
CALL_CEILING_USD_2 = 0.055600

CALL_ID_3 = cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1
CALL_SPEC_SHA256_3 = d4143eca0ac6ba40152eecdc5c37cfa7c2f74b3cda39774db79feec54689c0ca
PROJECTION_SHA256_3 = 8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d
CALL_CEILING_USD_3 = 0.055600
```

Les trois identités ci-dessus, les deux carry-forward, les cinq observations
logiques et le plafond de `0.156800 USD` sont approuvés. Une autorisation live
distincte reste obligatoire avant tout appel fournisseur.
