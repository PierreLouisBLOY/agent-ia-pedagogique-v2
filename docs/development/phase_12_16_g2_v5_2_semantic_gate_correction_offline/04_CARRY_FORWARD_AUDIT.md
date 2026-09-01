# Phase 12.16-G2-V5.2 — Audit carry-forward

## Politique de compatibilité

Version : `12.16-g2-v5.2-gate-only-carry-forward-v1`.

Les wrappers de call-spec V5.1 et l'identité de gate V5.2 ne sont pas égaux. La
réutilisation est recevable uniquement par compatibilité versionnée : le call-spec
provider, le parser, le scorer, la matrice, le pricing, le scope, la projection, le
modèle et les budgets de tokens doivent être identiques. Seule l'interprétation de la
gate change.

## Strong SCN-06

- Call : `cal.score.anchor.scn-06.strong.marking-scheme-coherence.r1`.
- Wrapper V5.1 :
  `282b1e562aa24ace1072e0d9612e045c76950d83727a01ca1e840e091608a44e`.
- Call-spec provider :
  `f897bee689581b1ed126b90dc17b6ff0f5912137d3baffe6980469accc76806e`.
- Projection :
  `e44c8d0ce1a7ed044dc383157d859a16abb8897af7aed43f2bc6c2d71b124eb4`.
- Parser/schema : `PASS`; score `4`; quatre checks attendus.
- Provenance et résultat certifié : `PASS`.
- `STRONG_CARRY_FORWARD = TRUE`.

## Mixed SCN-06

- Call : `cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1`.
- Wrapper V5.1 :
  `67312b3b73f4cd872f2b6b2f0585d02149c403a29d00c44582370c3b42c93c19`.
- Call-spec provider :
  `d55351eadd12cab8da5bdc7c2fd8331198c132f95089df1bb753392bbf2a3361`.
- Projection :
  `67f465002c21186b552ba62289fe49ce765c75f9ccb99a8cad088ece44fa1b7a`.
- Parser/schema : `PASS`; score `0`; zéro check attendu.
- Projection, mapping et provenance : `PASS`.
- `MIXED_CARRY_FORWARD = TRUE`.

## Identités inchangées

- Parser : `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b`.
- Scorer : `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`.
- Matrice : `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c`.
- Pricing : `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`.
- Scope : `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93`.
