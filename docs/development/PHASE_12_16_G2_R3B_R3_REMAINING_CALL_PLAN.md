# Phase 12.16-G2-R3B-R3 — Plan final des 71 appels Anthropic

## Matrice scellée

- Version : `12.16-g2-r3b-r4-completion-v1`.
- Checksum : `0298e4672f03def781bf7217b37567a456d6865aa35c157c4d956111962c7d8d`.
- Appels : `71 Anthropic / 0 OpenAI` ; retry/rerun : `0/0`.
- Répartition : `43` initial, `16` répétabilité, `12` selected-output.

## Readiness et arrêt systémique

- Readiness Anthropic importée par hashes : `PASSED`.
- Aucun canary supplémentaire n'est demandé.
- Au premier échec technique, la séquence se met en pause ; les futurs records restent `PENDING`.
- Un `STARTED` après interruption est ambigu et ferme la reprise automatique.

## Coût officiel

- Source : https://platform.claude.com/docs/en/about-claude/pricing.
- Claude Sonnet 5 : `2.00 USD/MTok input`, `0.20 cache hit`, `10.00 output`.
- Maximum avant marge : `1.499520 USD`.
- Marge 25 % : `0.374880 USD`.
- Plafond demandé : `1.874400 USD`.

## Signal ordinal préliminaire

- `SCN-01 clarity`: `a=1/1`, `b=1/1`, `c=0/1`.
- Monotonicité faible : `PASS` ; stricte : `FAIL`.
- Aucune modification des anchors ; calibration finale indisponible.

## Ledger R4

- Path ignoré : `artifacts/calibration/12.16-g2-r3b-r4/ledger.json`.
- États : `PENDING`, `STARTED`, `COMPLETED`, `FAILED`, `SKIPPED_DEPENDENCY_FAILED`.
- Plafond approuvé initial : `null` ; approbation explicite requise.

## Ordre canonique

| # | R4 call ID | Source R3 | Slot logique | Catégorie |
|---:|---|---|---|---|
| 1 | `r4.cal.score.anchor.scn-01.c.organization-utility.r1` | `r3.cal.score.anchor.scn-01.c.organization-utility.r1` | `cal.score.anchor.scn-01.c.organization-utility.r1` | `initial` |
| 2 | `r4.cal.score.anchor.scn-02.a.relevance.r1` | `r3.cal.score.anchor.scn-02.a.relevance.r1` | `cal.score.anchor.scn-02.a.relevance.r1` | `initial` |
| 3 | `r4.cal.score.anchor.scn-02.a.coverage.r1` | `r3.cal.score.anchor.scn-02.a.coverage.r1` | `cal.score.anchor.scn-02.a.coverage.r1` | `initial` |
| 4 | `r4.cal.score.anchor.scn-02.b.relevance.r1` | `r3.cal.score.anchor.scn-02.b.relevance.r1` | `cal.score.anchor.scn-02.b.relevance.r1` | `initial` |
| 5 | `r4.cal.score.anchor.scn-02.b.coverage.r1` | `r3.cal.score.anchor.scn-02.b.coverage.r1` | `cal.score.anchor.scn-02.b.coverage.r1` | `initial` |
| 6 | `r4.cal.score.anchor.scn-02.c.relevance.r1` | `r3.cal.score.anchor.scn-02.c.relevance.r1` | `cal.score.anchor.scn-02.c.relevance.r1` | `initial` |
| 7 | `r4.cal.score.anchor.scn-02.c.coverage.r1` | `r3.cal.score.anchor.scn-02.c.coverage.r1` | `cal.score.anchor.scn-02.c.coverage.r1` | `initial` |
| 8 | `r4.cal.score.anchor.scn-03.a.clarity.r1` | `r3.cal.score.anchor.scn-03.a.clarity.r1` | `cal.score.anchor.scn-03.a.clarity.r1` | `initial` |
| 9 | `r4.cal.score.anchor.scn-03.a.level-adaptation.r1` | `r3.cal.score.anchor.scn-03.a.level-adaptation.r1` | `cal.score.anchor.scn-03.a.level-adaptation.r1` | `initial` |
| 10 | `r4.cal.score.anchor.scn-03.b.clarity.r1` | `r3.cal.score.anchor.scn-03.b.clarity.r1` | `cal.score.anchor.scn-03.b.clarity.r1` | `initial` |
| 11 | `r4.cal.score.anchor.scn-03.b.level-adaptation.r1` | `r3.cal.score.anchor.scn-03.b.level-adaptation.r1` | `cal.score.anchor.scn-03.b.level-adaptation.r1` | `initial` |
| 12 | `r4.cal.score.anchor.scn-03.c.clarity.r1` | `r3.cal.score.anchor.scn-03.c.clarity.r1` | `cal.score.anchor.scn-03.c.clarity.r1` | `initial` |
| 13 | `r4.cal.score.anchor.scn-03.c.level-adaptation.r1` | `r3.cal.score.anchor.scn-03.c.level-adaptation.r1` | `cal.score.anchor.scn-03.c.level-adaptation.r1` | `initial` |
| 14 | `r4.cal.score.anchor.scn-04.a.fidelity.r1` | `r3.cal.score.anchor.scn-04.a.fidelity.r1` | `cal.score.anchor.scn-04.a.fidelity.r1` | `initial` |
| 15 | `r4.cal.score.anchor.scn-04.a.level-adaptation.r1` | `r3.cal.score.anchor.scn-04.a.level-adaptation.r1` | `cal.score.anchor.scn-04.a.level-adaptation.r1` | `initial` |
| 16 | `r4.cal.score.anchor.scn-04.b.fidelity.r1` | `r3.cal.score.anchor.scn-04.b.fidelity.r1` | `cal.score.anchor.scn-04.b.fidelity.r1` | `initial` |
| 17 | `r4.cal.score.anchor.scn-04.b.level-adaptation.r1` | `r3.cal.score.anchor.scn-04.b.level-adaptation.r1` | `cal.score.anchor.scn-04.b.level-adaptation.r1` | `initial` |
| 18 | `r4.cal.score.anchor.scn-04.c.fidelity.r1` | `r3.cal.score.anchor.scn-04.c.fidelity.r1` | `cal.score.anchor.scn-04.c.fidelity.r1` | `initial` |
| 19 | `r4.cal.score.anchor.scn-04.c.level-adaptation.r1` | `r3.cal.score.anchor.scn-04.c.level-adaptation.r1` | `cal.score.anchor.scn-04.c.level-adaptation.r1` | `initial` |
| 20 | `r4.cal.score.anchor.scn-05.a.difficulty-appropriateness.r1` | `r3.cal.score.anchor.scn-05.a.difficulty-appropriateness.r1` | `cal.score.anchor.scn-05.a.difficulty-appropriateness.r1` | `initial` |
| 21 | `r4.cal.score.anchor.scn-05.a.instruction-clarity.r1` | `r3.cal.score.anchor.scn-05.a.instruction-clarity.r1` | `cal.score.anchor.scn-05.a.instruction-clarity.r1` | `initial` |
| 22 | `r4.cal.score.anchor.scn-05.b.difficulty-appropriateness.r1` | `r3.cal.score.anchor.scn-05.b.difficulty-appropriateness.r1` | `cal.score.anchor.scn-05.b.difficulty-appropriateness.r1` | `initial` |
| 23 | `r4.cal.score.anchor.scn-05.b.instruction-clarity.r1` | `r3.cal.score.anchor.scn-05.b.instruction-clarity.r1` | `cal.score.anchor.scn-05.b.instruction-clarity.r1` | `initial` |
| 24 | `r4.cal.score.anchor.scn-05.c.difficulty-appropriateness.r1` | `r3.cal.score.anchor.scn-05.c.difficulty-appropriateness.r1` | `cal.score.anchor.scn-05.c.difficulty-appropriateness.r1` | `initial` |
| 25 | `r4.cal.score.anchor.scn-05.c.instruction-clarity.r1` | `r3.cal.score.anchor.scn-05.c.instruction-clarity.r1` | `cal.score.anchor.scn-05.c.instruction-clarity.r1` | `initial` |
| 26 | `r4.cal.score.anchor.scn-06.a.assessment-clarity.r1` | `r3.cal.score.anchor.scn-06.a.assessment-clarity.r1` | `cal.score.anchor.scn-06.a.assessment-clarity.r1` | `initial` |
| 27 | `r4.cal.score.anchor.scn-06.a.marking-scheme-coherence.r1` | `r3.cal.score.anchor.scn-06.a.marking-scheme-coherence.r1` | `cal.score.anchor.scn-06.a.marking-scheme-coherence.r1` | `initial` |
| 28 | `r4.cal.score.anchor.scn-06.b.assessment-clarity.r1` | `r3.cal.score.anchor.scn-06.b.assessment-clarity.r1` | `cal.score.anchor.scn-06.b.assessment-clarity.r1` | `initial` |
| 29 | `r4.cal.score.anchor.scn-06.b.marking-scheme-coherence.r1` | `r3.cal.score.anchor.scn-06.b.marking-scheme-coherence.r1` | `cal.score.anchor.scn-06.b.marking-scheme-coherence.r1` | `initial` |
| 30 | `r4.cal.score.anchor.scn-06.c.assessment-clarity.r1` | `r3.cal.score.anchor.scn-06.c.assessment-clarity.r1` | `cal.score.anchor.scn-06.c.assessment-clarity.r1` | `initial` |
| 31 | `r4.cal.score.anchor.scn-06.c.marking-scheme-coherence.r1` | `r3.cal.score.anchor.scn-06.c.marking-scheme-coherence.r1` | `cal.score.anchor.scn-06.c.marking-scheme-coherence.r1` | `initial` |
| 32 | `r4.cal.score.anchor.scn-07.a.correction-quality.r1` | `r3.cal.score.anchor.scn-07.a.correction-quality.r1` | `cal.score.anchor.scn-07.a.correction-quality.r1` | `initial` |
| 33 | `r4.cal.score.anchor.scn-07.a.remediation-clarity.r1` | `r3.cal.score.anchor.scn-07.a.remediation-clarity.r1` | `cal.score.anchor.scn-07.a.remediation-clarity.r1` | `initial` |
| 34 | `r4.cal.score.anchor.scn-07.b.correction-quality.r1` | `r3.cal.score.anchor.scn-07.b.correction-quality.r1` | `cal.score.anchor.scn-07.b.correction-quality.r1` | `initial` |
| 35 | `r4.cal.score.anchor.scn-07.b.remediation-clarity.r1` | `r3.cal.score.anchor.scn-07.b.remediation-clarity.r1` | `cal.score.anchor.scn-07.b.remediation-clarity.r1` | `initial` |
| 36 | `r4.cal.score.anchor.scn-07.c.correction-quality.r1` | `r3.cal.score.anchor.scn-07.c.correction-quality.r1` | `cal.score.anchor.scn-07.c.correction-quality.r1` | `initial` |
| 37 | `r4.cal.score.anchor.scn-07.c.remediation-clarity.r1` | `r3.cal.score.anchor.scn-07.c.remediation-clarity.r1` | `cal.score.anchor.scn-07.c.remediation-clarity.r1` | `initial` |
| 38 | `r4.cal.score.anchor.scn-08.a.distractor-quality.r1` | `r3.cal.score.anchor.scn-08.a.distractor-quality.r1` | `cal.score.anchor.scn-08.a.distractor-quality.r1` | `initial` |
| 39 | `r4.cal.score.anchor.scn-08.a.feedback-quality.r1` | `r3.cal.score.anchor.scn-08.a.feedback-quality.r1` | `cal.score.anchor.scn-08.a.feedback-quality.r1` | `initial` |
| 40 | `r4.cal.score.anchor.scn-08.b.distractor-quality.r1` | `r3.cal.score.anchor.scn-08.b.distractor-quality.r1` | `cal.score.anchor.scn-08.b.distractor-quality.r1` | `initial` |
| 41 | `r4.cal.score.anchor.scn-08.b.feedback-quality.r1` | `r3.cal.score.anchor.scn-08.b.feedback-quality.r1` | `cal.score.anchor.scn-08.b.feedback-quality.r1` | `initial` |
| 42 | `r4.cal.score.anchor.scn-08.c.distractor-quality.r1` | `r3.cal.score.anchor.scn-08.c.distractor-quality.r1` | `cal.score.anchor.scn-08.c.distractor-quality.r1` | `initial` |
| 43 | `r4.cal.score.anchor.scn-08.c.feedback-quality.r1` | `r3.cal.score.anchor.scn-08.c.feedback-quality.r1` | `cal.score.anchor.scn-08.c.feedback-quality.r1` | `initial` |
| 44 | `r4.cal.score.anchor.scn-01.a.clarity.r2` | `r3.cal.score.anchor.scn-01.a.clarity.r2` | `cal.score.anchor.scn-01.a.clarity.r2` | `repeatability` |
| 45 | `r4.cal.score.anchor.scn-01.a.organization-utility.r2` | `r3.cal.score.anchor.scn-01.a.organization-utility.r2` | `cal.score.anchor.scn-01.a.organization-utility.r2` | `repeatability` |
| 46 | `r4.cal.score.anchor.scn-02.a.relevance.r2` | `r3.cal.score.anchor.scn-02.a.relevance.r2` | `cal.score.anchor.scn-02.a.relevance.r2` | `repeatability` |
| 47 | `r4.cal.score.anchor.scn-02.a.coverage.r2` | `r3.cal.score.anchor.scn-02.a.coverage.r2` | `cal.score.anchor.scn-02.a.coverage.r2` | `repeatability` |
| 48 | `r4.cal.score.anchor.scn-03.a.clarity.r2` | `r3.cal.score.anchor.scn-03.a.clarity.r2` | `cal.score.anchor.scn-03.a.clarity.r2` | `repeatability` |
| 49 | `r4.cal.score.anchor.scn-03.a.level-adaptation.r2` | `r3.cal.score.anchor.scn-03.a.level-adaptation.r2` | `cal.score.anchor.scn-03.a.level-adaptation.r2` | `repeatability` |
| 50 | `r4.cal.score.anchor.scn-04.a.fidelity.r2` | `r3.cal.score.anchor.scn-04.a.fidelity.r2` | `cal.score.anchor.scn-04.a.fidelity.r2` | `repeatability` |
| 51 | `r4.cal.score.anchor.scn-04.a.level-adaptation.r2` | `r3.cal.score.anchor.scn-04.a.level-adaptation.r2` | `cal.score.anchor.scn-04.a.level-adaptation.r2` | `repeatability` |
| 52 | `r4.cal.score.anchor.scn-05.a.difficulty-appropriateness.r2` | `r3.cal.score.anchor.scn-05.a.difficulty-appropriateness.r2` | `cal.score.anchor.scn-05.a.difficulty-appropriateness.r2` | `repeatability` |
| 53 | `r4.cal.score.anchor.scn-05.a.instruction-clarity.r2` | `r3.cal.score.anchor.scn-05.a.instruction-clarity.r2` | `cal.score.anchor.scn-05.a.instruction-clarity.r2` | `repeatability` |
| 54 | `r4.cal.score.anchor.scn-06.a.assessment-clarity.r2` | `r3.cal.score.anchor.scn-06.a.assessment-clarity.r2` | `cal.score.anchor.scn-06.a.assessment-clarity.r2` | `repeatability` |
| 55 | `r4.cal.score.anchor.scn-06.a.marking-scheme-coherence.r2` | `r3.cal.score.anchor.scn-06.a.marking-scheme-coherence.r2` | `cal.score.anchor.scn-06.a.marking-scheme-coherence.r2` | `repeatability` |
| 56 | `r4.cal.score.anchor.scn-07.a.correction-quality.r2` | `r3.cal.score.anchor.scn-07.a.correction-quality.r2` | `cal.score.anchor.scn-07.a.correction-quality.r2` | `repeatability` |
| 57 | `r4.cal.score.anchor.scn-07.a.remediation-clarity.r2` | `r3.cal.score.anchor.scn-07.a.remediation-clarity.r2` | `cal.score.anchor.scn-07.a.remediation-clarity.r2` | `repeatability` |
| 58 | `r4.cal.score.anchor.scn-08.a.distractor-quality.r2` | `r3.cal.score.anchor.scn-08.a.distractor-quality.r2` | `cal.score.anchor.scn-08.a.distractor-quality.r2` | `repeatability` |
| 59 | `r4.cal.score.anchor.scn-08.a.feedback-quality.r2` | `r3.cal.score.anchor.scn-08.a.feedback-quality.r2` | `cal.score.anchor.scn-08.a.feedback-quality.r2` | `repeatability` |
| 60 | `r4.cal.score.output.scn-03.clarity.r1` | `r3.cal.score.output.scn-03.clarity.r1` | `cal.score.output.scn-03.clarity.r1` | `selected-output` |
| 61 | `r4.cal.score.output.scn-03.level-adaptation.r1` | `r3.cal.score.output.scn-03.level-adaptation.r1` | `cal.score.output.scn-03.level-adaptation.r1` | `selected-output` |
| 62 | `r4.cal.score.output.scn-04.fidelity.r1` | `r3.cal.score.output.scn-04.fidelity.r1` | `cal.score.output.scn-04.fidelity.r1` | `selected-output` |
| 63 | `r4.cal.score.output.scn-04.level-adaptation.r1` | `r3.cal.score.output.scn-04.level-adaptation.r1` | `cal.score.output.scn-04.level-adaptation.r1` | `selected-output` |
| 64 | `r4.cal.score.output.scn-05.difficulty-appropriateness.r1` | `r3.cal.score.output.scn-05.difficulty-appropriateness.r1` | `cal.score.output.scn-05.difficulty-appropriateness.r1` | `selected-output` |
| 65 | `r4.cal.score.output.scn-05.instruction-clarity.r1` | `r3.cal.score.output.scn-05.instruction-clarity.r1` | `cal.score.output.scn-05.instruction-clarity.r1` | `selected-output` |
| 66 | `r4.cal.score.output.scn-06.assessment-clarity.r1` | `r3.cal.score.output.scn-06.assessment-clarity.r1` | `cal.score.output.scn-06.assessment-clarity.r1` | `selected-output` |
| 67 | `r4.cal.score.output.scn-06.marking-scheme-coherence.r1` | `r3.cal.score.output.scn-06.marking-scheme-coherence.r1` | `cal.score.output.scn-06.marking-scheme-coherence.r1` | `selected-output` |
| 68 | `r4.cal.score.output.scn-07.correction-quality.r1` | `r3.cal.score.output.scn-07.correction-quality.r1` | `cal.score.output.scn-07.correction-quality.r1` | `selected-output` |
| 69 | `r4.cal.score.output.scn-07.remediation-clarity.r1` | `r3.cal.score.output.scn-07.remediation-clarity.r1` | `cal.score.output.scn-07.remediation-clarity.r1` | `selected-output` |
| 70 | `r4.cal.score.output.scn-08.distractor-quality.r1` | `r3.cal.score.output.scn-08.distractor-quality.r1` | `cal.score.output.scn-08.distractor-quality.r1` | `selected-output` |
| 71 | `r4.cal.score.output.scn-08.feedback-quality.r1` | `r3.cal.score.output.scn-08.feedback-quality.r1` | `cal.score.output.scn-08.feedback-quality.r1` | `selected-output` |

## Approbation exacte requise

```text
J'approuve exclusivement l'exécution de la matrice
12.16-g2-r3b-r4-completion-v1,
checksum 0298e4672f03def781bf7217b37567a456d6865aa35c157c4d956111962c7d8d,
71 appels maximum (71 Anthropic Scorer claude-sonnet-5, max_output_tokens 512),
plafond 1.874400 USD,
aucun retry et arrêt immédiat de la séquence au premier échec technique avant tout appel suivant.
```

R3 ne lance aucun appel et s'arrête avant R4.
