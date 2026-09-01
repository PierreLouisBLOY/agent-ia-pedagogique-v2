# Phase 12.16-G2-V5.2 — Sélection et budget du mini-pilote

## Cardinalités

- Observations logiques : `5`.
- Carry-forward : `2`.
- Nouveaux appels : `3`.
- Provider futur : `ANTHROPIC_ONLY`.
- Scénarios couverts : `SCN-06` et `SCN-01`.
- Anchor intermédiaire inclus : `NON`.

## Carry-forward logique

1. Strong SCN-06 absolu, score attendu et observé `4`.
2. Mixed SCN-06 absolu, score attendu et observé `0`.

Ces deux observations ne doivent pas être rappelées.

## Trois nouveaux appels proposés

| Ordre | Call ID | Call-spec V5.2 SHA-256 | Projection SHA-256 | Attente | Plafond proposé |
|---:|---|---|---|---|---:|
| 1 | `cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1` | `a3646f66bd0d274cf30daf3024bbad5d204bb0d8182963460107243a0d81b707` | `8faf88c7f863294591d8ed3c47812db1d69edd8c38aafc98a1345f431f1af2dc` | score `1`, check 1 | `0.045600 USD` |
| 2 | `cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1` | `691794a224c1f440225dca29dddf34aff90c6556210c583263b006607509c196` | `e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8` | `A_BETTER` | `0.055600 USD` |
| 3 | `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1` | `d4143eca0ac6ba40152eecdc5c37cfa7c2f74b3cda39774db79feec54689c0ca` | `8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d` | `A_BETTER` | `0.055600 USD` |

## Recalcul du budget

| Call | Entrée max | Sortie max | Maximum avant marge | Marge 1,25 incluse |
|---|---:|---:|---:|---:|
| Weak absolu | `8000` | `2048` | `0.036480 USD` | `0.045600 USD` |
| Pairwise SCN-06 | `12000` | `2048` | `0.044480 USD` | `0.055600 USD` |
| Pairwise SCN-01 | `12000` | `2048` | `0.044480 USD` | `0.055600 USD` |
| **Total** |  |  | **`0.125440 USD`** | **`0.156800 USD`** |

- Marge de sécurité : `0.031360 USD`.
- `PROPOSED_V5_2_MINI_PILOT_CEILING_USD = 0.156800`.
- `APPROVED_V5_2_MINI_PILOT_CEILING_USD = NONE`.

Le plafond V5.1 de `0.202400 USD` n'est pas réutilisé. Aucun appel n'est autorisé par
ce document.
