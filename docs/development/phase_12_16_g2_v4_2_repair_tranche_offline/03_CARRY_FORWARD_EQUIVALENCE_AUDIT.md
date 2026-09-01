# Phase 12.16-G2-V4.2 — Audit d'équivalence carry-forward

## Identité canonique

`CALL_SPEC_SHA256` est calculé à partir d'une projection canonique comprenant :

- provider, model et workload family ;
- hash du prompt/input canonique ;
- hash de la dépendance source réellement consommée ;
- scénario, criterion et anchor/input refs déclarées ;
- paramètres d'exécution, dont output budget et reasoning ;
- hash du bundle parser/scorer/transport applicable ;
- snapshot et quote de pricing.

Pour un score d'output, le hash de dépendance incorpore le call-spec de l'appel OpenAI
upstream. Un id identique ne suffit donc jamais à rendre un résultat réutilisable.

L'audit lit le safe report V4.1 exact, vérifie son SHA-256, reconstruit l'identité
V4.1 réellement exécutée, puis la compare à l'identité logique V4.2. Tout écart ou
statut non `COMPLETED` rend l'appel inéligible.

## Résultat sur les 102 records logiques

| Décision | Nombre | Motif |
| --- | ---: | --- |
| carry-forward éligible | 63 | `EQUIVALENT` |
| non éligible | 13 | `SOURCE_PROJECTION_CHANGED` |
| non éligible | 18 | `UPSTREAM_CALL_SPEC_CHANGED` |
| non éligible | 8 | `SOURCE_NOT_COMPLETED` |

`CARRY_FORWARD_SAFE = TRUE` signifie ici que la réutilisation des 63 records
explicitement éligibles est démontrée. Il ne signifie pas que les 94 succès V4.1 sont
tous réutilisables. Les 31 autres succès ne sont pas carry-forward.

## Provenance agrégée

Le builder de rapport agrégé produit 102 records distincts :

- pour les 63 carry-forward : source run `12.16-g2-v4-1-live`, baseline
  `71e4258baacc1f0914cf9a9087638736c2a4ebdd`, call-spec V4.1, statut
  `CARRY_FORWARD`, ledger `artifacts/calibration/12.16-g2-v4-1/ledger.json` ;
- pour les 39 records futurs : source run `12.16-g2-v4-2-live`, baseline encore à
  autoriser, call-spec V4.2, statut `PENDING_NEW_EXECUTION`, ledger
  `artifacts/calibration/12.16-g2-v4-2/ledger.json`.

Le validateur interdit les doublons, les trous et toute attribution des deux groupes
au même run. Aucune nouvelle exécution n'a été produite dans ce lot hors ligne.
