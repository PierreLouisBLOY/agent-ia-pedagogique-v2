# V5.1 mini-pilot — Minimal logical selection

## Methodological minimum

Five logical observations are necessary and sufficient:

1. one certified strong observation;
2. one real intermediate observation;
3. one real weak observation;
4. one direct pairwise observation with a known preference;
5. one further observation on a distinct scenario and criterion.

The strong observation is carried forward from the passed micro-canary. Four
new calls are therefore required. The selection covers `SCN-06` and `SCN-01`
and does not oversample `SCN-06` exclusively.

- `MINI_PILOT_LOGICAL_OBSERVATIONS = 5`
- `MINI_PILOT_NEW_CALL_COUNT = 4`

## Exact new calls

| Order | Call ID | Scenario / criterion | Expected semantic role | V5.1 call-spec SHA-256 | Transfer projection SHA-256 | Provider / model | Max input / output |
|---:|---|---|---|---|---|---|---:|
| 1 | `cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1` | `SCN-06` / `scn-06.quality.marking-scheme-coherence` | intermediate absolute canary | `67312b3b73f4cd872f2b6b2f0585d02149c403a29d00c44582370c3b42c93c19` | `67f465002c21186b552ba62289fe49ce765c75f9ccb99a8cad088ece44fa1b7a` | `anthropic` / `claude-sonnet-5` | `8000 / 2048` |
| 2 | `cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1` | `SCN-06` / `scn-06.quality.marking-scheme-coherence` | weak absolute control | `72ccc17ccfece21b070c0ea9c19b3bb93538196b60ab0605b374069170478938` | `8faf88c7f863294591d8ed3c47812db1d69edd8c38aafc98a1345f431f1af2dc` | `anthropic` / `claude-sonnet-5` | `8000 / 2048` |
| 3 | `cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1` | `SCN-06` / `scn-06.quality.marking-scheme-coherence` | known preference `A_BETTER` | `ded321befe1bb3f1c0402734e72be87e7ae7380f2990f22991919cb031725710` | `e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8` | `anthropic` / `claude-sonnet-5` | `12000 / 2048` |
| 4 | `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1` | `SCN-01` / `scn-01.quality.clarity` | distinct known preference `A_BETTER` | `5f67866cd65327621d32c70e4688b58dec0bf6ee996a4376bee78f4ba0f62653` | `8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d` | `anthropic` / `claude-sonnet-5` | `12000 / 2048` |

All four payload projections already belong to the unchanged robust-pilot
transfer scope. No scope extension is prepared or authorized here.
