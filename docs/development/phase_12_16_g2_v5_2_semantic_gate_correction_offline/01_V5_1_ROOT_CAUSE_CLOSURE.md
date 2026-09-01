# Phase 12.16-G2-V5.2 — Clôture de la cause racine V5.1

## Baseline diagnostique conservée

Le mini-pilote V5.1 reste figé avec :

- `V5_1_MINI_PILOT_FAIL`;
- Strong SCN-06 carry-forward : score `4`;
- Mixed SCN-06 observé : score `0`;
- arrêt avant Weak et les deux pairwise;
- coût historique `0.011164 USD`;
- autorisation live consommée et refermée.

Ni le verdict, ni le ledger, ni les rapports, ni les anchors historiques ne sont
modifiés par V5.2.

## Cause close

L'analyse V5.1 a établi :

- contenu Strong/Mixed/Weak attendu selon les checks : `4/0/1`;
- projection Mixed byte-fidèle : `PASS`;
- mapping evidence vers score : `PASS`;
- attente « Mixed doit valoir 1..3 » : `OVERCONSTRAINED`;
- cause racine : `SEMANTIC_GATE_EXPECTATION_TOO_RIGID`;
- confiance : `HIGH`.

La gate V5.1 déduisait `INTERMEDIATE` du fragment `.mixed.` du call ID, alors que la
baseline V4 définit Mixed et Weak comme contrôles négatifs non livrables et rend leur
ordre secondaire non bloquant. La revue humaine corrigée classe le triplet SCN-06
`Strong > Weak > Mixed`.

## Disposition V5.2

V5.2 remplace l'inférence depuis le nom de tier par des attentes explicites,
versionnées et sourcées. Le lot ne corrige que la logique d'acceptation future :

- `HISTORICAL_V5_1_VERDICT_REWRITTEN = FALSE`
- `HISTORICAL_ANCHOR_CHANGED = FALSE`
- `PROVIDER_CALLS = 0`
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`
