# Phase 12.16-G2-V5 — Préparation de la revue propriétaire

## Statut

`V5_SEMANTIC_PILOT_READINESS = GO_FOR_OWNER_REVIEW`.

Cette readiness signifie que le plan offline est cohérent, hashé, budgété, testé et fail-closed. Elle ne constitue ni une approbation financière, ni une autorisation de transfert, ni une autorisation live.

## Choix soumis au propriétaire

Le propriétaire peut examiner l'une des deux tranches sans que ce document la sélectionne :

| Option | Appels | Plafond proposé | Couverture |
|---|---:|---:|---|
| Minimal | 4 Anthropic | 0.192400 USD | un triplet historiquement inversé + un pairwise |
| Robuste | 21 Anthropic | 1.017600 USD | cinq inversions historiques + orientations A/B + tie output |

Le robuste apporte une preuve sémantique plus stable ; le minimal est le plus petit test techniquement informatif.

## Éléments qui resteraient nécessaires avant tout live

- sélection explicite d'une tranche exacte ;
- approbation financière exacte avec nombre maximal d'appels et plafond ;
- autorisation de transfert minimisée décrivant les projections autorisées ;
- baseline, matrice, pricing, contrat et manifest exactement identifiés ;
- maintien de `aucun retry/rerun` ;
- canaries en premier et arrêt avant fanout à la première gate échouée.

`APPROVED_PILOT_CEILING_USD = NONE` et `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE` dans cette baseline.

## Limite sémantique explicite

Les performances du contrat V5 sur fixtures synthétiques sont établies, mais aucun juge réel n'a encore évalué les anchors avec ce contrat. Le verdict d'un futur pilote ne doit pas être préjugé et aucun seuil de release n'est adopté.

