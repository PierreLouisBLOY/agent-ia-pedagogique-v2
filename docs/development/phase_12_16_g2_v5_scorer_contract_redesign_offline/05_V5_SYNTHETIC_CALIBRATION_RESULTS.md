# Phase 12.16-G2-V5 — Résultats de calibration synthétique offline

## Corpus

- 16 critères.
- 6 classes par critère : absent, contradiction, Weak, Mixed, satisfaisant, Strong.
- 96 fixtures de score.
- 4 classes pairwise par critère.
- 64 fixtures pairwise.

Le moteur de référence ne lit aucun label tier dans une observation. Il évalue un `V5EvidenceProfile` : les contrôles étayés déterminent le niveau, et une contradiction matérielle force 0.

## Monotonie

Le triplet synthétique principal est `Strong = 4`, `Mixed = 2`, `Weak = 1` pour chaque critère.

| Scénario | Critères | Triplets strictement monotones | Inversions | Ties adjacents |
|---|---:|---:|---:|---:|
| SCN-01 | 2 | 2/2 | 0 | 0 |
| SCN-02 | 2 | 2/2 | 0 | 0 |
| SCN-03 | 2 | 2/2 | 0 | 0 |
| SCN-04 | 2 | 2/2 | 0 | 0 |
| SCN-05 | 2 | 2/2 | 0 | 0 |
| SCN-06 | 2 | 2/2 | 0 | 0 |
| SCN-07 | 2 | 2/2 | 0 | 0 |
| SCN-08 | 2 | 2/2 | 0 | 0 |
| Total | 16 | 16/16 | 0 | 0 |

`STRICT_MONOTONICITY_OFFLINE = 16/16`

## Distribution

| Niveau | Nombre | Part |
|---:|---:|---:|
| 0 | 32 | 33,3333 % |
| 1 | 16 | 16,6667 % |
| 2 | 16 | 16,6667 % |
| 3 | 16 | 16,6667 % |
| 4 | 16 | 16,6667 % |
| Total | 96 | 100 % |

- Scores extrêmes 0 ou 4 : `48/96 = 50 %`.
- Scores intermédiaires 1, 2 ou 3 : `48/96 = 50 %`.
- Chaque niveau intermédiaire est atteint `16` fois.
- La distribution n'est pas quasi binaire : la moitié du corpus se situe aux niveaux intermédiaires, contre `1/48` dans V4.

Le niveau 0 est volontairement surreprésenté par deux classes différentes : absence et contradiction. Cette duplication vérifie les deux chemins sémantiques vers zéro sans masquer les niveaux intermédiaires.

## Pairwise

| Mesure | Résultat |
|---|---:|
| Fixtures | 64 |
| Décisions correctes | 64 |
| Accuracy | 100 % |
| Ties attendus | 32 |
| Ties observés | 32 |
| Faux ties | 0 |

Les différences hors critère sont correctement ignorées dans `16/16` cas. Les quasi-identités produisent `16/16` ties. Les différences matérielles A et B produisent `32/32` préférences correctes.

## Audit des anchors canoniques V4

| Vérification | Résultat |
|---|---:|
| Hash corpus historique préservé | PASS |
| Anchors | 24 |
| Observations V5 construites | 48/48 |
| Rubriques couvertes | 16/16 |
| Triplets textuellement distincts | 16/16 |
| Fuites tier/provider/model/score attendu | 0 |
| Scoring sémantique simulé | NON |

`CANONICAL_ANCHOR_SEMANTIC_SCORING = NOT_EXECUTED_OFFLINE_WITHOUT_A_SEMANTIC_JUDGE`

Ce non-scoring est une borne méthodologique, pas un échec : attribuer manuellement les niveaux aux anchors historiques en utilisant leurs tiers aurait rendu la démonstration circulaire. Leur prévalidation sémantique est une action propriétaire ultérieure.

## Gates synthétiques V5

| Gate | Verdict |
|---|---|
| Aucune inversion synthétique | PASS |
| Niveaux intermédiaires atteignables | PASS |
| Distribution non quasi binaire | PASS |
| Pairwise sur différences contrôlées | PASS |
| Tie réservé aux équivalences/non-matériel/hors-scope | PASS |
| Parser/schema | PASS |
| Anchor blinding | PASS |
| Live fail-closed | PASS |

`V5_DISCRIMINATION_OFFLINE = PASS`
