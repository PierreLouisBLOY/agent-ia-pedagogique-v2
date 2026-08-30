# Phase 12.16-G2 — Baseline de remédiation du corpus d'anchors v2

## Décision et références

- OWNER_CALIBRATION_DECISION : `REVISE_ANCHOR_CORPUS_FIRST`.
- ANCHOR_CORPUS_V1_STATUS : `CLOSED_DIAGNOSTIC_BASELINE`.
- ANTHROPIC_SCORER_POLICY : `KEEP_PROVISIONALLY_EXPLICIT_ADAPTIVE_LOW_2048`.
- JUDGE_RECALIBRATION : `DEFERRED_UNTIL_V2_HUMAN_PREVALIDATION`.
- PROVIDER_ROUTE_CHANGE : `NONE`.
- RELEASE_THRESHOLD_ADOPTION : `NOT_ALLOWED`.
- Sources : rapport machine final v1, réconciliation humaine et ADR-P12-063/064.

## Intégrité v1

- Version : `12.16-g1-v1` ; statut : `CLOSED_DIAGNOSTIC_BASELINE`.
- Checksum corpus : `abeec0b4e5e1f60f2974ec1c19de34a5307e1b7d92e11c7b811e338d3b2e626d`.
- Hash owner : `53da2068fa6585086fe955b633a1d8e173cf770c8b5cb5e71f6cc8cc474e7317`.
- Hash rapport machine : `f08fad954918f82e690a539b35f02a88ce3d08818a95f6c18df982f4c3d7c272`.
- Hash réconciliation humaine : `568e810af5a3cee9e46a56696300066db421d2dfc330f721718318be85a8b6cd`.
- Les owners, rapports, preuves et paquets v1 ne sont pas modifiés.

## Corpus v2

- Version : `12.16-g1-v2`.
- Checksum : `4fe17f4286eb1a713a3d41a95b99260ef470ba32cadf33c2267dfc4dbaada427`.
- Cardinalité : `24 anchors / 48 couples / 8 scénarios / 16 critères`.
- IDs : nouveaux, opaques, uniques et disjoints de v1.
- Structure : `24/24` anchors avec sections requises exactes.
- Matrice : `16/16` critères avec défauts controlled strong/mixed/weak.
- SCN-01 : le défaut structurel mixed est supprimé; les trois contenus conservent context et summary.

## Prévalidation humaine

- Paquet : `docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_PACKET.md`.
- Hash paquet : `81bca8cc998e866c7b08f22af65c009714b5e4d5068fb0c19b2ba6598a7d48c9`.
- 24 IDs aveugles nouveaux; ordre déterministe différent de v1; aucun tier ou score.
- REVIEW_STATUS : `NOT_COMPLETED`; aucune appréciation humaine n'est préremplie.
- Clé locale ignorée : `artifacts/calibration/12.16-g2-anchor-corpus-v2/human_prevalidation_reconciliation.json`.
- Hash clé : `eb20fe93ae76215218fea3958bd44d6e2c0d7d5c476cec4350e6eb6146084ef0`.
- Relecteur préféré : `SECOND_COMPETENT_HUMAN_NOT_EXPOSED_TO_MACHINE_RESULTS`.
- Fallback : `OWNER_HUMAN_REVIEWER` avec nouveaux IDs, exposition déclarée et aucun rapport machine ouvert pendant la revue.
- Gate : 24/24 structures, 16/16 ordres faibles, 0 inversion, 0 non-évaluable et différenciation perceptible des 16 critères.
- Objectif de design : `16/16` ordres humains stricts; toute égalité reçoit une disposition avant une évaluation fournisseur.

## Exécution bornée

- OPENAI_CALLS : `0`; ANTHROPIC_CALLS : `0`; PROVIDER_COST : `0`.
- CREDENTIALS_RESOLVED : `FALSE`; PROVIDER_TRANSPORT_CONSTRUCTED : `FALSE`.
- Policy scorer : conservée; judge recalibration : différée; route runtime : inchangée.
- Calibration live/matrice fournisseur : `NOT_PREPARED / NOT_EXECUTED`.
- ADR_REQUIRED : `YES`; ADR-P12-065 accepté pour le nouvel owner versionné.

## Validations exécutées

- Audit statique v2 : `9/9` règles actives, `0` issue sur le corpus canonique.
- Tests ciblés v2 : `19 passed`.
- Régression calibration : `149 passed, 1 skipped` (gate live explicitement désactivée).
- Suite globale : `4335 passed, 3 skipped`.
- Ruff global : `PASS`.
- mypy `backend evaluation_harness` : `PASS`, 689 fichiers source.
- compileall `backend evaluation_harness tests/calibration/pedagogical` : `PASS`.
- Aucun test live fournisseur n'a été activé.

## Livraison

- Commit attendu : `test: establish revised pedagogical anchor corpus`.
- Parent exact : `523d9bffaacebdae930a5a083ac466a3944d459a`.
- Branche/upstream : `phase12/12-16-provider-model-calibration`.
- main/origin-main attendus inchangés : `7ae02ee109bcc6399ec0f71616da6aef07abda81`.
- Fichiers suivis créés :
  - `architecture/adr/ADR-P12-065-versioned-human-prevalidated-anchor-corpus.md`
  - `docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V2_REMEDIATION_BASELINE.md`
  - `docs/development/PHASE_12_16_G2_ANCHOR_CORPUS_V2_DIFFERENTIATION_MATRIX.md`
  - `docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_PACKET.md`
  - `tests/architecture/test_anchor_corpus_v2_fitness.py`
  - `tests/calibration/pedagogical/anchor_corpus_v2.py`
  - `tests/unit/test_pedagogical_calibration_anchor_corpus_v2.py`
- Worktree final attendu : `clean`.
- NEXT_GATE : `12.16-G2-V2-HUMAN-PREVALIDATION_READY`.
