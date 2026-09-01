# Phase 12.16-G2-V4.2 — Audit final du carry-forward

## Partition et identité

L'audit post-approbation reconstruit l'identité canonique de chaque call V4.1 et V4.2
à partir des inputs et dépendances réellement applicables, et non du seul call id.

`63 + 39 = 102`

| Classe | Nombre | Disposition |
| --- | ---: | --- |
| Identité strictement équivalente | 63 | carry-forward |
| Projection source legacy au lieu de V4 | 13 | nouvelle exécution |
| Dépendance upstream modifiée | 18 | nouvelle exécution |
| Source V4.1 non terminée | 8 | nouvelle exécution |

Les 63 records carry-forward sont inchangés par rapport au manifeste approuvé. Les
31 succès liés à la mauvaise projection d'anchor restent exclus : 13 outputs OpenAI
directs et leurs 18 scorings Anthropic dépendants.

## Complétude de la tranche

- 7/7 Reviews failed ou skipped sont présentes ;
- 1/1 scoring Anthropic failed est présent exactement une fois ;
- aucun retry automatique n'est créé ;
- les canaries restent premiers dans chacune des trois familles ;
- aucune autre call spec ne dérive.

`CARRY_FORWARD_COUNT = 63`

`REPAIR_TRANCHE_MAX_CALL_COUNT = 39`

`OTHER_CALL_SPEC_DRIFT = 0`

`POST_APPROVAL_TECHNICAL_DRIFT = FALSE`
