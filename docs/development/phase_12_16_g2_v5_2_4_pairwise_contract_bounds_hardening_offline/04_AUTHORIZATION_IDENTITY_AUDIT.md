# Authorization identity audit

The hardening changes only the versioned local pairwise output parser.

## SCN-01

- call ID: `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1`
- call-spec SHA-256:
  `d4143eca0ac6ba40152eecdc5c37cfa7c2f74b3cda39774db79feec54689c0ca`
- projection SHA-256:
  `8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d`
- expected disposition: `A_BETTER`
- recalculated single-call ceiling: `0.055600 USD`

## Shared identities

- transfer scope:
  `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93`
- scorer:
  `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`
- logical matrix:
  `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c`
- pricing:
  `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`
- semantic gate:
  `8dc0bdb7ca57c586ac8db887fcb7078e16377e1f8ae30f2d153096ce630c7eea`

`AUTHORIZATION_IDENTITIES_CHANGED = FALSE`

The pairwise output contract/parser identity did change, as intended. This is
not a change to the authorized call input or transfer payload. It nevertheless
requires a new freeze and owner approval before a future one-call live run.
