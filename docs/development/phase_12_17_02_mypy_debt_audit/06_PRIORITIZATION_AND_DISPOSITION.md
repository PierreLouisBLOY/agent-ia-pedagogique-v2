# Phase 12.17.2 — Priorisation et disposition

## Priorisation des clusters

| Priorité | Cluster | Diagnostics | Risque réel | Effort racine | Disposition recommandée |
| ---: | --- | ---: | --- | --- | --- |
| 1 | `C02_PROVIDER_OPTIONAL_NARROWING` | 4 | Moyen : le comportement fail-closed existe, mais son contrat de contrôle de flux n'est pas compris par mypy dans un tooling provider ayant servi au live. | XS | Absorber dans 12.17.4 si le provider tooling est déplacé; sinon corriger avant toute nouvelle exécution live. |
| 2 | `C05_OPTIONAL_BUDGET_NARROWING` | 4 | Moyen-faible : les gardes runtime existent, mais deux versions du plan ne prouvent pas l'affinement du plafond. | S | Rationaliser les deux versions en 12.17.4 ou appliquer deux corrections locales coordonnées. |
| 3 | `C03_FIXED_TUPLE_CARDINALITY` | 4 | Faible à moyen : le runtime valide trois tiers, mais le type ne porte pas la cardinalité et la règle est répliquée. | M | Builder canonique en 12.17.4, avec préservation explicite des artefacts hashés. |
| 4 | `C08_BRANCH_SPEC_UNION` | 1 | Faible : incompatibilité statique entre deux branches de pilotage; pas de preuve d'échec runtime. | XS | Absorber dans la rationalisation des specs V5 en 12.17.4. |
| 5 | `C06_DYNAMIC_OBSERVATION_UNION` | 1 | Faible : collection hétérogène volontaire, mais contrat local implicite. | XS | Correction typée individuelle. |
| 6 | `C07_IMPLICIT_REEXPORT` | 1 | Faible : dépendance indirecte fragile entre modules versionnés. | XS | Importer depuis le module propriétaire lors de 12.17.4. |
| 7 | `C04_LOOP_VARIABLE_COLLISION` | 7 | Faible : une variable de boucle réutilisée produit six diagnostics en cascade. | XS | Correction typée individuelle. |
| 8 | `C01_STALE_TYPING_SCAFFOLD` | 11 | Faible : dette de casts/ignore devenue obsolète; bruit qui masque les signaux utiles. | S | Nettoyage mécanique individuel avec non-régression stricte. |

## Disposition chiffrée

- `13` changements individuels peuvent être traités sans décision architecturale : C01 (`11`), C04 (`1`) et C06 (`1`).
- `9` changements racines, couvrant `14` diagnostics, sont absorbables par la rationalisation 12.17.4 : C02, C03, C05, C07 et C08.
- `0` diagnostic ne se trouve dans le runtime de production analysé.
- `33` diagnostics se trouvent dans du tooling/test importé par les deux racines de contrôle.
- `2` fichiers sont des candidats forts à un mauvais placement architectural; aucun déplacement n'est autorisé dans ce lot.

## Principaux risques

1. Le contrat statique du provider Anthropic ne reflète pas son arrêt par exception, ce qui affaiblit la preuve fail-closed du tooling.
2. Les gardes de budget optionnel sont dupliquées dans deux plans versionnés et peuvent diverger lors d'une maintenance future.
3. La cardinalité forte/mixed/weak est reproduite dans quatre fichiers sans constructeur typé commun.
4. Les unions d'observations et de specs restent implicites dans deux chemins V5.
5. Les onze diagnostics de scaffolding obsolète augmentent le bruit et rendent une future régression plus difficile à isoler.

## Décision d'audit

`DISPOSITION = MIXED_TARGETED_REMEDIATION_AND_12_17_4_ABSORPTION`

Cette disposition ne constitue ni une correction, ni une autorisation de déplacement, ni une autorisation d'appel fournisseur.
