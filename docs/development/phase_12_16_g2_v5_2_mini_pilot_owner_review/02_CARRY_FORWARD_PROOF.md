# Phase 12.16-G2-V5.2 — Preuve des carry-forward

## Règle de compatibilité

La compatibilité est versionnée par
`12.16-g2-v5.2-gate-only-carry-forward-v1`. Le wrapper historique V5.1 n'est
pas l'identité de gate V5.2. La réutilisation est recevable parce que le call-spec
provider, le parser, le scorer, la matrice, le pricing, le scope de transfert, la
projection, le modèle et les budgets de tokens restent identiques. Seule la gate
d'interprétation change.

## Strong SCN-06

- Call ID : `cal.score.anchor.scn-06.strong.marking-scheme-coherence.r1`.
- Wrapper V5.1 SHA-256 :
  `282b1e562aa24ace1072e0d9612e045c76950d83727a01ca1e840e091608a44e`.
- Call-spec provider SHA-256 :
  `f897bee689581b1ed126b90dc17b6ff0f5912137d3baffe6980469accc76806e`.
- Projection SHA-256 :
  `e44c8d0ce1a7ed044dc383157d859a16abb8897af7aed43f2bc6c2d71b124eb4`.
- Score attendu et observé : `4`.
- Parser/schema : `PASS`.
- Provenance et résultat certifié : `PASS`.
- Retransmission ou rappel : `INTERDIT`.

`STRONG_CARRY_FORWARD = TRUE`

## Mixed SCN-06

- Call ID : `cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1`.
- Wrapper V5.1 SHA-256 :
  `67312b3b73f4cd872f2b6b2f0585d02149c403a29d00c44582370c3b42c93c19`.
- Call-spec provider SHA-256 :
  `d55351eadd12cab8da5bdc7c2fd8331198c132f95089df1bb753392bbf2a3361`.
- Projection SHA-256 :
  `67f465002c21186b552ba62289fe49ce765c75f9ccb99a8cad088ece44fa1b7a`.
- Score attendu et observé : `0`.
- Parser/schema : `PASS`.
- Projection, mapping et provenance : `PASS`.
- Retransmission ou rappel : `INTERDIT`.

`MIXED_CARRY_FORWARD = TRUE`

## Conclusion

Les deux résultats conservent une provenance intacte et satisfont la politique de
compatibilité versionnée. Ils constituent deux observations logiques sans nouvel
appel provider. Une dérive de l'une des identités liées doit fermer la gate.
