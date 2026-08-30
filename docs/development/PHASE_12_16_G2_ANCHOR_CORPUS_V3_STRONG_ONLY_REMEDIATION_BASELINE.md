# Phase 12.16-G2 — Baseline de remédiation strong-only du corpus v3

## Décision propriétaire

- OWNER_CALIBRATION_DECISION : `ALIGN_PRIMARY_CALIBRATION_TO_STRONG_ONLY_DELIVERABILITY`.
- ANCHOR_CORPUS_V2_STATUS : `CLOSED_FAILED_HUMAN_PREVALIDATION_BASELINE`.
- PRODUCTION_CONTENT_POLICY : `STRONG_ONLY`.
- PRIMARY_CALIBRATION_SEPARATION : `STRONG_VS_NON_STRONG`.
- SECONDARY_DIAGNOSTIC : `MIXED_VS_WEAK_ORDERING_NON_BLOCKING`.
- PROVIDER_RECALIBRATION_ALLOWED : `FALSE`.
- PROVIDER_ROUTE_CHANGE : `NONE`.
- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.

## Preuves v2 préservées

- Corpus v2 : `12.16-g1-v2` ; checksum `4fe17f4286eb1a713a3d41a95b99260ef470ba32cadf33c2267dfc4dbaada427`.
- Rapport humain v2 : `3ae6d71e47da917bcb904e5534ea4ec893d37887f4eba1b98c37c4ab4b0392fd`.
- Structures valides : `24/24`; STRONG TRES_SATISFAISANT : `16/16`.
- Ordres stricts : `4/16`; faibles : `15/16`; inversions : `1`; non évaluable : `0`.
- Différenciation perceptible : `11/16`; MIXED TRES_SATISFAISANT : `9/16`; WEAK : `6/16`.

## Corpus v3

- Version : `12.16-g1-v3`.
- Checksum : `dad8e7d08934b7d64c3f22c4c5fdf1e3ca39768854359c26f681852852ffb50c`.
- Cardinalités : `8 scénarios / 16 critères / 24 anchors / 48 couples`.
- Contenus STRONG carry-forward byte-equivalent : `8`.
- Contrôles négatifs carry-forward : `8`.
- Contrôles négatifs remédiés : `8`.
- Scénarios remédiés : `SCN-01, SCN-03, SCN-04, SCN-07, SCN-08`.
- IDs v3 nouveaux, opaques et disjoints de v1/v2.

## Paquet humain delta

- Paquet : `docs/development/PHASE_12_16_G2_V3_HUMAN_DELTA_PREVALIDATION_PACKET.md`.
- Items : `15`.
- Hash paquet : `0cd536bdbdca68cead009bad9ae09a1d11c514ff0774c34fbe4f14f5ae4d6477`.
- Clé locale ignorée : `artifacts/calibration/12.16-g2-anchor-corpus-v3/human_delta_prevalidation_reconciliation.json`.
- Hash clé : `afe21aab0e83e2046fd5e6a26c5f3548f75ecc702550f16b5a4b6c2d7a4c6205`.
- Formulaire : `NOT_COMPLETED`; aucun tier, ordre attendu ou résultat v2 exposé.

## Exécution bornée

- PROVIDER_CALLS : `0`; PROVIDER_COST : `0`.
- CREDENTIALS_RESOLVED : `FALSE`; PROVIDER_TRANSPORT_CONSTRUCTED : `FALSE`.
- GateEngine/runtime/routes : `UNCHANGED`.
- ADR-P12-066 : `ACCEPTED` pour la sémantique durable de livraison/calibration.

## Livraison

- Commit attendu : `test: establish strong-only pedagogical anchor corpus v3`.
- Parent exact : `7a08b992a312f6d154b9630a3151a9a45ba0a65d`.
- Branche : `phase12/12-16-provider-model-calibration`.
- main/origin-main inchangés attendus : `7ae02ee109bcc6399ec0f71616da6aef07abda81`.
- Fichiers suivis créés :
  - `architecture/adr/ADR-P12-066-strong-only-deliverability-calibration-semantics.md`
  - `docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V3_STRONG_ONLY_REMEDIATION_BASELINE.md`
  - `docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V3_CRITERION_DEFECT_ALIGNMENT_MATRIX.md`
  - `docs/development/PHASE_12_16_G2_V3_HUMAN_DELTA_PREVALIDATION_PACKET.md`
  - `tests/architecture/test_anchor_corpus_v3_fitness.py`
  - `tests/calibration/pedagogical/anchor_corpus_v3.py`
  - `tests/calibration/pedagogical/test_anchor_corpus_v3.py`
- NEXT_GATE : `12.16-G2-V3-HUMAN-DELTA-PREVALIDATION_READY`.
- Calibration fournisseur : `NOT_AUTHORIZED / NOT_EXECUTED`.
