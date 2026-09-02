# Phase 12.17.2 — Recommandation de sous-étape suivante

## Recommandation

`NEXT_RECOMMENDED_SUBSTEP = 12.17.2A_TARGETED_TYPING_REMEDIATION`

`RECOMMENDED_STRATEGY = MIXED`

La prochaine action recommandée est un lot propriétaire distinct, borné aux `13` changements individuels de C01, C04 et C06. Il doit réduire `19` diagnostics sans décision de placement ni consolidation architecturale.

Après validation de ce lot :

1. conduire 12.17.3, l'audit des règles métier, comme phase indépendante;
2. traiter en 12.17.4 les `9` changements racines restants couvrant `14` diagnostics, avec décision explicite sur les deux fichiers provider mal placés;
3. rejouer les deux contrôles mypy après chaque frontière, sans appel fournisseur.

## Pourquoi ne pas tout corriger immédiatement

Les diagnostics C02, C03, C05, C07 et C08 recouvrent des choix de propriété, de versioning et de placement. Une correction locale préalable pourrait dupliquer le travail ou altérer des artefacts historiques hashés. À l'inverse, C01, C04 et C06 sont suffisamment localisés pour constituer un lot statique contrôlable.

Cette recommandation n'engage aucune modification. La sous-étape 12.17.3 n'a pas été démarrée.
