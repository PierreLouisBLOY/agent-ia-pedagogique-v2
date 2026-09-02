# Phase 12.17.2 — Clusters d'erreurs mypy

| Cluster | Erreurs | Fichiers | Cause commune | Fix canonique unique possible | Findings 12.17.1 |
| --- | ---: | ---: | --- | --- | --- |
| `C01_STALE_TYPING_SCAFFOLD` | 11 | 8 | Dix casts devenus redondants et un ignore devenu inutile. | Non : nettoyage mécanique par site, validable en lot. | `TYP-007` |
| `C02_PROVIDER_OPTIONAL_NARROWING` | 4 | 1 | `_configuration_error()` retourne toujours par exception mais est annoté `None`. | Oui : une correction de contrôle de flux peut fermer les quatre erreurs. | `TYP-002`, `ARC-003` |
| `C03_FIXED_TUPLE_CARDINALITY` | 4 | 4 | Les compréhensions produisent `tuple[str, ...]` alors que le contrat exige exactement trois anchors. | Potentiellement : builder canonique partagé, sous réserve des hashes historiques. | `TYP-003` |
| `C04_LOOP_VARIABLE_COLLISION` | 7 | 1 | `item` est réutilisé pour deux dataclasses dans deux boucles. | Oui : une distinction de variables supprime une racine et six cascades. | `TYP-004` |
| `C05_OPTIONAL_BUDGET_NARROWING` | 4 | 2 | Deux versions du call plan dupliquent le même helper fail-closed non affiné. | Oui après comparaison/consolidation; sinon un fix par fichier. | `TYP-005`, `ARC-002` |
| `C06_DYNAMIC_OBSERVATION_UNION` | 1 | 1 | Une collection hétérogène est inférée comme `object`. | Oui : annotation locale ou construction typée. | `TYP-006` |
| `C07_IMPLICIT_REEXPORT` | 1 | 1 | `AnchorTier` est importé depuis un module qui ne l'exporte pas explicitement. | Oui : dépendre du module propriétaire du type. | `ARC-002`, `BUS-002` |
| `C08_BRANCH_SPEC_UNION` | 1 | 1 | Une locale reçoit une spec micro-canary puis mini-pilot de types distincts. | Oui : union/protocol ou variables séparées. | `TYP-008`, `ARC-002` |

Total : `33 erreurs`, `15 fichiers`, `8 clusters`.

## Compression en causes racines

Sans rationalisation structurelle, les 33 diagnostics correspondent à environ `22` changements racines minimaux : `11 + 1 + 4 + 1 + 2 + 1 + 1 + 1` pour C01 à C08.

Treize changements sont indépendants d'une décision de placement/consolidation : les onze nettoyages C01, la variable de boucle C04 et la collection typée C06. Neuf changements racines couvrant quatorze erreurs pourraient être absorbés par la rationalisation 12.17.4 : composition provider, builders de cardinalité, deux plans budgétaires, export du type et union de specs.

Ces nombres expriment un plan minimal, pas des modifications déjà réalisées.
