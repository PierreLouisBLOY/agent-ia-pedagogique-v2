# Phase 12.16-G2-V5.1 — Synthèse des preuves du run

## Périmètre

Cette analyse est strictement hors ligne. Elle examine l'appel
`cal.score.anchor.scn-06.mixed.marking-scheme-coherence.r1` du mini-pilote V5.1
sans résoudre de credential, ouvrir de transport ou reconstituer la réponse brute.

## Identités vérifiées

| Élément | Valeur |
|---|---|
| Baseline | `c534b488276eabfa9f82b379282a043cdc0f4b65` |
| Parser V5.1 | `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b` |
| Scorer V5 | `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344` |
| Matrice | `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c` |
| Pricing | `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8` |
| Scope de transfert | `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93` |
| Call-spec | `67312b3b73f4cd872f2b6b2f0585d02149c403a29d00c44582370c3b42c93c19` |
| Projection de transfert | `67f465002c21186b552ba62289fe49ce765c75f9ccb99a8cad088ece44fa1b7a` |

## Preuves sûres disponibles

| Champ | Valeur sûre |
|---|---|
| Score | `0` |
| Statut parser/schema | `PASS` |
| Événement avant parsing | `RESPONSE_RECEIVED / PENDING` |
| Événement terminal | `COMPLETED / PASS` |
| Stop reason | `end_turn` |
| Confidence | `NOT_PERSISTED_BY_SAFE_CONTRACT` |
| Evidence détaillée | `NOT_PERSISTED_BY_SAFE_CONTRACT` |
| Défauts détaillés | `NOT_PERSISTED_BY_SAFE_CONTRACT` |
| Rationale | `NOT_PERSISTED_BY_SAFE_CONTRACT` |
| Evidence-first synthétique | `true` — quatre enregistrements evidence/défaut ont couvert les quatre checks |
| Hash du contenu de réponse | `d854b69410681bad645e3eb337962aaef3e9570f7c18046cecc1c0d5082accf2` |
| Longueur du contenu non persisté | `1244` caractères |
| Tokens input/cache/output/total | `2017 / 0 / 713 / 2730` |
| Thinking tokens | `214` |
| Coût exact | `0.011164 USD` |

L'absence des formulations détaillées d'evidence, de défauts, de confidence et de
rationale est intentionnelle : le ledger n'enregistre que les métadonnées sûres et
le résultat sémantique minimal. Elles ne sont ni inférées, ni reconstruites depuis le
hash de réponse.

## Intégrité des sources du run

- `safe_report.json` : `67c38c12c0062117529ed69ab6ac496a0c323d7ebb95132be21f7c299091066f`.
- `safe_report.md` : `02ce7a32ef1b5060f0bc4e57e582375f1ca3d99b4c5d50447550e9dc385a9b58`.
- `ledger.json` : `eff93e6ca7e8c73009c37c013c7dc2373aaeb545fbcf7a1415b9e9f141495db3`.
- Un appel Anthropic a été effectué dans le run historique; aucun appel fournisseur
  n'a été effectué pour la présente analyse.
- `LIVE_AUTHORIZATION = CONSUMED` et
  `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`.
