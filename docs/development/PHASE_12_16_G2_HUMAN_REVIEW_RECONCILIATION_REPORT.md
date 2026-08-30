# Phase 12.16-G2 — Réconciliation de la revue humaine

## Résultat

- Statut : `PASS / CLOSED`.
- Exécution strictement hors ligne : `0` appel OpenAI, `0` appel Anthropic.
- Revue : `24/24` items, `48/48` appréciations, `24/24` structures et `24/24` actions.
- Relecteur : `OWNER_HUMAN_REVIEWER` ; date : `2026-08-30` ; grille : `human-review-v1`.
- Exposition déclarée exactement : `OUI — résultats agrégés et certains détails par critère consultés ; mapping REV→anchor, tiers attendus et scores individuels par item non consultés pendant la revue.`
- Classe d’exposition : `DETAILED_RESULTS_EXPOSED`.

## Intégrité des sources

- Paquet source : `d9ea4b33b84ee52c0460097cf1dd97e89f33a67106c57cc10dd611536b8d1e5e`.
- Revue complétée : `594e3220cb30cd26a706f847bb33ffdb2f26077a79374ef0405fddc3ff4425eb`.
- Clé locale : `d314ef0b6e26dec812e06f59c747af110b55804c88cc4f6a3e919aca0427e749` ; `24/24` SHA unitaires valides.
- Corpus : `12.16-g1-v1` ; checksum `abeec0b4e5e1f60f2974ec1c19de34a5307e1b7d92e11c7b811e338d3b2e626d`.

## Ordre humain

L’échelle humaine est uniquement ordinale. Aucun score pédagogique numérique n’en est dérivé.

- Ordres stricts : `0/16` ; ordres faibles : `16/16`.
- Égalités adjacentes : `28` ; inversions : `0`.
- Distinctions humaines : `4` ; relations non évaluables : `0`.

## Relations humain / Claude

Les comparaisons portent uniquement sur les relations ordinales strong/mixed et mixed/weak, jamais sur une équivalence entre libellé humain et fraction Claude.

- Accords de relation : `0`.
- Distinctions humaines seules : `4` ; distinctions modèle seules : `12`.
- Égalités partagées : `16` ; désaccords : `0` ; non-assessables : `0`.

## Diagnostic par critère

| Scénario | Critère | Humain S/M | Humain M/W | Claude S/M | Claude M/W | Cause | Disposition |
|---|---|---|---|---|---|---|---|
| SCN-01 | `scn-01.quality.clarity` | EQ | EQ | EQ | EQ | `STRUCTURAL_ANCHOR_DEFECT` | `REVISE_ANCHORS` |
| SCN-01 | `scn-01.quality.organization-utility` | EQ | EQ | EQ | GT | `STRUCTURAL_ANCHOR_DEFECT` | `REVISE_ANCHORS` |
| SCN-02 | `scn-02.quality.relevance` | EQ | EQ | EQ | EQ | `ANCHORS_TOO_SIMILAR_FOR_HUMAN_AND_MODEL` | `REVISE_ANCHORS` |
| SCN-02 | `scn-02.quality.coverage` | EQ | EQ | EQ | EQ | `ANCHORS_TOO_SIMILAR_FOR_HUMAN_AND_MODEL` | `REVISE_ANCHORS` |
| SCN-03 | `scn-03.quality.clarity` | GT | EQ | EQ | EQ | `MODEL_UNDER_DISCRIMINATES_HUMAN_CLEARLY_DISTINGUISHES` | `REVISE_ANCHORS` |
| SCN-03 | `scn-03.quality.level-adaptation` | GT | EQ | EQ | GT | `INSUFFICIENT_EVIDENCE` | `REVISE_ANCHORS` |
| SCN-04 | `scn-04.quality.fidelity` | GT | EQ | EQ | GT | `INSUFFICIENT_EVIDENCE` | `OWNER_DECISION_REQUIRED` |
| SCN-04 | `scn-04.quality.level-adaptation` | GT | EQ | EQ | GT | `INSUFFICIENT_EVIDENCE` | `OWNER_DECISION_REQUIRED` |
| SCN-05 | `scn-05.quality.difficulty-appropriateness` | EQ | EQ | GT | EQ | `INSUFFICIENT_EVIDENCE` | `OWNER_DECISION_REQUIRED` |
| SCN-05 | `scn-05.quality.instruction-clarity` | EQ | EQ | EQ | EQ | `ANCHORS_TOO_SIMILAR_FOR_HUMAN_AND_MODEL` | `REVISE_ANCHORS` |
| SCN-06 | `scn-06.quality.assessment-clarity` | EQ | EQ | GT | GT | `INSUFFICIENT_EVIDENCE` | `OWNER_DECISION_REQUIRED` |
| SCN-06 | `scn-06.quality.marking-scheme-coherence` | EQ | EQ | EQ | GT | `INSUFFICIENT_EVIDENCE` | `OWNER_DECISION_REQUIRED` |
| SCN-07 | `scn-07.quality.correction-quality` | EQ | EQ | EQ | GT | `INSUFFICIENT_EVIDENCE` | `OWNER_DECISION_REQUIRED` |
| SCN-07 | `scn-07.quality.remediation-clarity` | EQ | EQ | EQ | GT | `INSUFFICIENT_EVIDENCE` | `OWNER_DECISION_REQUIRED` |
| SCN-08 | `scn-08.quality.distractor-quality` | EQ | EQ | GT | EQ | `INSUFFICIENT_EVIDENCE` | `REVISE_ANCHORS` |
| SCN-08 | `scn-08.quality.feedback-quality` | EQ | EQ | EQ | GT | `INSUFFICIENT_EVIDENCE` | `REVISE_ANCHORS` |

## Décision bornée

- HUMAN_REVIEW_COMPLETE = `TRUE`.
- HUMAN_ANCHOR_EVIDENCE = `PARTIAL`.
- JUDGE_CALIBRATION_DISPOSITION = `ANCHOR_REVISION_REQUIRED`.
- CALIBRATION_CONFIDENCE = `PROVISIONAL_REVIEW_EXPOSURE_LIMITED`.
- RELEASE_THRESHOLD_ADOPTION = `NOT_ALLOWED`.
- PROVIDER_ROUTE_CHANGE = `NONE`.
- LIVE_PROVIDER_CALLS = `0`.
- NEXT_GATE = `OWNER_CALIBRATION_DECISION_READY`.

## Validation

- Régression calibration : `PASS_131`.
- Pytest global : `PASS_4316_SKIPPED_3_EXPLICIT_GATES`.
- Ruff global : `PASS`.
- Mypy : `PASS_689_SOURCE_FILES`.
- Compileall : `PASS`.

## Gouvernance et confidentialité

- Les commentaires, justifications et limites libres de la revue ne sont pas reproduits.
- Aucun contenu d’anchor, output fournisseur, secret, chemin absolu ou mapping REV→anchor n’est suivi dans ce rapport.
- Aucune révision d’anchor n’est lancée. Toute révision exige un nouveau corpus, un nouveau checksum, une nouvelle calibration et une nouvelle approbation.
- ADR : `NO`; ADR-P12-063 et ADR-P12-064 appliqués.
