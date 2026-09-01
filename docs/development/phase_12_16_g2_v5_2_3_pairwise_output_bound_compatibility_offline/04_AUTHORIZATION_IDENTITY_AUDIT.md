# Authorization identity audit

The V5.2.3 change is additive and offline. Existing inputs and authorization
identities remain byte-for-byte unchanged.

| Identity | Expected and observed SHA-256 | Status |
|---|---|---|
| SCN-06 call spec | `691794a224c1f440225dca29dddf34aff90c6556210c583263b006607509c196` | PASS |
| SCN-06 transfer projection | `e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8` | PASS |
| SCN-01 call spec | `d4143eca0ac6ba40152eecdc5c37cfa7c2f74b3cda39774db79feec54689c0ca` | PASS |
| SCN-01 transfer projection | `8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d` | PASS |
| logical matrix | `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c` | PASS |
| pricing | `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8` | PASS |
| semantic gate | `8dc0bdb7ca57c586ac8db887fcb7078e16377e1f8ae30f2d153096ce630c7eea` | PASS |
| transfer scope | `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93` | PASS |
| V4 anchor corpus | `9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034` | PASS |

Call IDs remain:

- `cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1`
- `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1`

The only new identity is the compatibility overlay:
`285179c2b104a14837c2065e229aa89b6b93e2dfba4e75ebcaf9c416c5fb3508`.
It must be bound explicitly during technical freeze and approved before any new
live authorization. Replacing the frozen outbound schema would require a fresh
transfer-hash audit; this offline lot does not do so.

`CALL_SPEC_PROJECTION_IDENTITIES_CHANGED = FALSE`

`ANCHOR_DATA_CHANGED = FALSE`
