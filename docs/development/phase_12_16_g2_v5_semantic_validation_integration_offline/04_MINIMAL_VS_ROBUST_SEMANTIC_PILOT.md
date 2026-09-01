# Phase 12.16-G2-V5 — Pilote sémantique minimal et robuste

## Choix minimal

`MINIMAL_PILOT` contient quatre nouveaux appels Anthropic et aucun appel OpenAI :

1. score absolu SCN-06 / cohérence du barème / Strong ;
2. score absolu SCN-06 / cohérence du barème / Mixed ;
3. score absolu SCN-06 / cohérence du barème / Weak ;
4. pairwise direct Strong vs Mixed sur le même critère.

Ce choix est minimal au sens des six observations demandées : trois scores sont indispensables à `Strong > Mixed > Weak`, et un quatrième appel distinct est indispensable à un vrai pairwise. Les quatre réponses traversent le parser/schema réel V5. La distribution révèle les extrêmes et l'emploi éventuel des niveaux intermédiaires 1–3.

Avantage : quatre appels seulement et test d'un critère historiquement inversé. Limite : un seul critère, une seule orientation pairwise attendue et aucune comparaison d'outputs.

## Choix robuste

`ROBUST_PILOT` contient 21 nouveaux appels Anthropic et aucun appel OpenAI :

- 15 scores absolus, soit cinq triplets Strong/Mixed/Weak ;
- 5 pairwise directs d'anchors ;
- 1 pairwise direct d'outputs quasi équivalents SCN-03.

Les cinq critères sont ceux des inversions historiques :

- SCN-01 clarté ;
- SCN-04 fidélité ;
- SCN-06 clarté de l'évaluation ;
- SCN-06 cohérence du barème ;
- SCN-08 qualité des distracteurs.

Les pairwise attendent trois `A_BETTER`, deux `B_BETTER` par inversion contrôlée de l'ordre A/B, puis un `TIE` sur les outputs SCN-03 quasi équivalents. Cela détecte un juge positionnel, un pairwise toujours-tie et un pairwise toujours-A/B.

## Ordonnancement fail-closed

Les quatre appels du pilote minimal sont les canaries du pilote robuste. Les 17 appels restants constituent le fanout. Le fanout est interdit tant que les canaries ne démontrent pas :

- trois réponses parsées et scorées ;
- `Strong > Mixed > Weak` ;
- au moins un score intermédiaire ;
- décision pairwise `A_BETTER` attendue.

Ces pilotes sont des diagnostics sémantiques. Ils ne fixent ni seuil final de release ni politique de promotion.

