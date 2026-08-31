# Phase 12.16-G2 — Baseline de remédiation disposition-first du corpus v4

## Décision propriétaire

- OWNER_CALIBRATION_DECISION : `ADOPT_DISPOSITION_FIRST_PAIRWISE_HUMAN_CALIBRATION`.
- ANCHOR_CORPUS_V3_STATUS : `CLOSED_FAILED_HUMAN_PREVALIDATION_BASELINE`.
- PRODUCTION_CONTENT_POLICY : `STRONG_ONLY`.
- PRIMARY_HUMAN_INSTRUMENT : `DELIVERABILITY_DISPOSITION_PLUS_BLIND_PAIRWISE_CRITERION_COMPARISON`.
- ABSOLUTE_QUALITY_LABELS : `DIAGNOSTIC_ONLY`.
- PROVIDER_RECALIBRATION_ALLOWED : `FALSE`.
- PROVIDER_ROUTE_CHANGE : `NONE`.
- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.

## Corpus v4

- Version : `12.16-g1-v4`.
- Checksum : `9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034`.
- Cardinalités : `8 scénarios / 16 critères / 24 anchors / 48 couples`.
- STRONG carry-forward byte-equivalent : `8/8`.
- Contrôles négatifs carry-forward byte-equivalent : `11/16`.
- Contrôles négatifs révisés : `5/16`.
- Politique de révision : `REVISE_ONLY_V3_NEGATIVES_WITH_ACTION_NONE`.
- IDs v4 opaques et disjoints de v1/v2/v3.

## Instrument humain

- Cartes scénario : `8`.
- Candidats anonymisés : `24`.
- Dispositions globales attendues : `24`.
- Classements critère par critère attendus : `16`.
- Paquet : `docs/development/PHASE_12_16_G2_V4_HUMAN_DISPOSITION_PAIRWISE_PACKET.md`.
- Hash paquet : `56bc9d28b65b2e7b82a982cf36afb56d13e147ce6c0716587acaef47e4c42a1f`.
- Clé locale ignorée : `artifacts/calibration/12.16-g2-anchor-corpus-v4/human_disposition_pairwise_reconciliation.json`.
- Hash clé : `a5b2ed4ebed755b128d3cc163f8004bedb57f2087bd2b444f9835069609edc21`.

## Gates pré-déclarées

- Livrabilité : `8/8 candidat livrable = DELIVER_AS_IS`; `0/16 contrôles = DELIVER_AS_IS`; `0 NON_EVALUABLE`.
- Discrimination : `16/16 candidat livrable > contrôle intermédiaire`; `16/16 candidat livrable > contrôle faible`.
- Ordre entre contrôles : `SECONDARY_DIAGNOSTIC_NON_BLOCKING`.

## Exécution bornée

- PROVIDER_CALLS : `0`; PROVIDER_COST : `0`.
- CREDENTIALS_RESOLVED : `FALSE`; PROVIDER_TRANSPORT_CONSTRUCTED : `FALSE`.
- RUNTIME_ROUTE_CHANGE : `NONE`.
- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.
- TEST_LEVEL : `T2_BOUNDED`; GLOBAL_SUITE_RUN : `NO`.
- NEXT_GATE : `12.16-G2-V4-HUMAN-DISPOSITION-PAIRWISE-PREVALIDATION_READY`.
