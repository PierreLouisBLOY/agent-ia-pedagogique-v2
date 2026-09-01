# Phase 12.16-G2-V5.2 — Snapshot d'identité exact

## État canonique soumis à revue

- `V5_2_SEMANTIC_GATE_CORRECTION = PASS`.
- `V5_2_MINI_PILOT_READINESS = GO_FOR_OWNER_REVIEW`.
- `V5_2_GATE_CONTRACT_SHA256 = 8dc0bdb7ca57c586ac8db887fcb7078e16377e1f8ae30f2d153096ce630c7eea`.
- `V5_2_LOGICAL_OBSERVATION_COUNT = 5`.
- `V5_2_CARRY_FORWARD_COUNT = 2`.
- `V5_2_NEW_CALL_COUNT = 3`.
- `INTERMEDIATE_ANCHOR_AVAILABLE = FALSE`.
- `PROPOSED_V5_2_MINI_PILOT_CEILING_USD = 0.156800`.
- `OWNER_V5_2_MINI_PILOT_APPROVAL = APPROVED`.
- `APPROVED_V5_2_MINI_PILOT_CEILING_USD = 0.156800`.
- `PEDAGOGICAL_TRANSFER_AUTHORIZED_FOR_V5_2_MINI_PILOT = TRUE`.
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`.

## Identités immuables

| Élément | SHA-256 / commit exact |
|---|---|
| Baseline Git | `c534b488276eabfa9f82b379282a043cdc0f4b65` |
| Parser V5.1 | `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b` |
| Scorer contract | `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344` |
| Matrice | `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c` |
| Pricing | `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8` |
| Gate contract V5.2 | `8dc0bdb7ca57c586ac8db887fcb7078e16377e1f8ae30f2d153096ce630c7eea` |
| Scope de transfert pédagogique | `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93` |

## Allowlist exacte des trois nouveaux appels

| Ordre | Call ID complet | Call-spec V5.2 SHA-256 | Projection SHA-256 | Plafond individuel |
|---:|---|---|---|---:|
| 1 | `cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1` | `a3646f66bd0d274cf30daf3024bbad5d204bb0d8182963460107243a0d81b707` | `8faf88c7f863294591d8ed3c47812db1d69edd8c38aafc98a1345f431f1af2dc` | `0.045600 USD` |
| 2 | `cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1` | `691794a224c1f440225dca29dddf34aff90c6556210c583263b006607509c196` | `e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8` | `0.055600 USD` |
| 3 | `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1` | `d4143eca0ac6ba40152eecdc5c37cfa7c2f74b3cda39774db79feec54689c0ca` | `8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d` | `0.055600 USD` |

Les attentes sont : Weak SCN-06 score `1`, pairwise SCN-06 `A_BETTER` et
pairwise SCN-01 `A_BETTER`. Aucun quatrième nouvel appel n'appartient à cette
configuration.

## Somme exacte

```text
0.045600 USD
+ 0.055600 USD
+ 0.055600 USD
= 0.156800 USD
```

Le plafond est approuvé pour cette identité exacte. Il n'est pas consommable tant
qu'une autorisation live séparée n'a pas été reçue.
