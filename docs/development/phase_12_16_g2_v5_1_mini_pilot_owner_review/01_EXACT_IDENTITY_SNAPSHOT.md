# V5.1 mini-pilot — Exact identity snapshot

## Baseline and canonical identities

- Baseline commit SHA: `c534b488276eabfa9f82b379282a043cdc0f4b65`
- Parser SHA-256: `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b`
- Scorer SHA-256: `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`
- Matrix SHA-256: `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c`
- Pricing SHA-256: `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`
- Transfer-scope SHA-256: `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93`
- Preparation manifest SHA-256: `29de80c58735ae66d730857265056bd98bf71a1e840f76d987a20d1a0b900c3c`

The preparation manifest contains ten entries; all ten were recomputed and
verified against the baseline before this snapshot was created.

## Exact four-call allowlist

| Order | Call ID | Call-spec SHA-256 | Transfer projection SHA-256 |
|---:|---|---|---|
| 1 | `cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1` | `67312b3b73f4cd872f2b6b2f0585d02149c403a29d00c44582370c3b42c93c19` | `67f465002c21186b552ba62289fe49ce765c75f9ccb99a8cad088ece44fa1b7a` |
| 2 | `cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1` | `72ccc17ccfece21b070c0ea9c19b3bb93538196b60ab0605b374069170478938` | `8faf88c7f863294591d8ed3c47812db1d69edd8c38aafc98a1345f431f1af2dc` |
| 3 | `cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1` | `ded321befe1bb3f1c0402734e72be87e7ae7380f2990f22991919cb031725710` | `e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8` |
| 4 | `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1` | `5f67866cd65327621d32c70e4688b58dec0bf6ee996a4376bee78f4ba0f62653` | `8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d` |

Provider/model for all four calls: `anthropic` / `claude-sonnet-5`.
