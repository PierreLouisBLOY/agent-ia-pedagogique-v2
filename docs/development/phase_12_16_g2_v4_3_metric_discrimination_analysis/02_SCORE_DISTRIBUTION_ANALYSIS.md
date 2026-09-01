# Phase 12.16-G2-V4.3 — Analyse de distribution des scores

## Méthode

Les statistiques utilisent les 48 scores primaires d'anchors, soit 16 critères multipliés par trois tiers. Les calculs sont exacts avec des rationnels. La variance est la variance de population.

## Histogramme global

| Score | Nombre | Part |
|---:|---:|---:|
| 0 | 19 | 39,5833 % |
| 1/2 | 1 | 2,0833 % |
| 1 | 28 | 58,3333 % |
| Total | 48 | 100 % |

La saturation est extrême : `47/48`, soit `97,9167 %`, des observations valent exactement 0 ou 1. La zone centrale ne contient qu'une observation (`1/2`). Il n'existe aucune preuve d'un arrondi numérique : ce sont les rationnels exacts renvoyés et normalisés.

## Statistiques par tier

| Tier | n | Moyenne | Médiane | Variance |
|---|---:|---:|---:|---:|
| Strong | 16 | 1 | 1 | 0 |
| Mixed | 16 | 3/8 = 0,375 | 0 | 15/64 = 0,234375 |
| Weak | 16 | 13/32 = 0,40625 | 0 | 231/1024 = 0,2255859375 |

La moyenne Weak est supérieure à la moyenne Mixed de `1/32`. Ce renversement agrégé est cohérent avec les cinq inversions `Mixed < Weak` et montre que les labels négatifs ne sont pas ordonnés par le Scorer.

## Statistiques par scénario/critère

Chaque ligne porte sur le triplet Strong/Mixed/Weak du critère.

| Scénario | Critère | Moyenne | Médiane | Variance |
|---|---|---:|---:|---:|
| SCN-01 | `scn-01.quality.clarity` | 2/3 | 1 | 2/9 |
| SCN-01 | `scn-01.quality.organization-utility` | 1/3 | 0 | 2/9 |
| SCN-02 | `scn-02.quality.relevance` | 1 | 1 | 0 |
| SCN-02 | `scn-02.quality.coverage` | 1 | 1 | 0 |
| SCN-03 | `scn-03.quality.clarity` | 2/3 | 1 | 2/9 |
| SCN-03 | `scn-03.quality.level-adaptation` | 2/3 | 1 | 2/9 |
| SCN-04 | `scn-04.quality.fidelity` | 2/3 | 1 | 2/9 |
| SCN-04 | `scn-04.quality.level-adaptation` | 1/3 | 0 | 2/9 |
| SCN-05 | `scn-05.quality.difficulty-appropriateness` | 2/3 | 1 | 2/9 |
| SCN-05 | `scn-05.quality.instruction-clarity` | 2/3 | 1 | 2/9 |
| SCN-06 | `scn-06.quality.assessment-clarity` | 2/3 | 1 | 2/9 |
| SCN-06 | `scn-06.quality.marking-scheme-coherence` | 1/2 | 1/2 | 1/6 |
| SCN-07 | `scn-07.quality.correction-quality` | 1/3 | 0 | 2/9 |
| SCN-07 | `scn-07.quality.remediation-clarity` | 1/3 | 0 | 2/9 |
| SCN-08 | `scn-08.quality.distractor-quality` | 2/3 | 1 | 2/9 |
| SCN-08 | `scn-08.quality.feedback-quality` | 1/3 | 0 | 2/9 |

Les deux critères SCN-02 ont une variance nulle à 1 : ils ne discriminent aucun tier. Quinze critères sur seize n'emploient que les deux extrêmes.

## Ties et deltas

| Mesure | Valeur exacte | Valeur décimale |
|---|---:|---:|
| Taux de ties adjacents | 13/32 | 40,625 % |
| Amplitude moyenne absolue Strong-Mixed | 5/8 | 0,625 |
| Amplitude moyenne absolue Mixed-Weak | 17/32 | 0,53125 |
| Amplitude moyenne absolue Strong-Weak | 19/32 | 0,59375 |
| Amplitude moyenne absolue, trois familles réunies | 7/12 | 0,583333... |
| Delta moyen signé Strong-Mixed | 5/8 | 0,625 |
| Delta moyen signé Mixed-Weak | -1/32 | -0,03125 |
| Delta moyen signé Strong-Weak | 19/32 | 0,59375 |

Le taux `13/32` porte sur les comparaisons adjacentes `S-M` et `M-W` de la métrique d'ordre. Il est distinct du taux de ties selected-output, qui vaut `6/6`.

## Diagnostic

Le profil n'est pas une saturation centrale, mais une saturation aux extrêmes. Il est compatible avec un Scorer qui transforme un jugement de conformité implicite en décision binaire, faute de barème opérationnel. Cette interprétation est une inférence contractuelle : aucune justification du modèle n'a été conservée.
