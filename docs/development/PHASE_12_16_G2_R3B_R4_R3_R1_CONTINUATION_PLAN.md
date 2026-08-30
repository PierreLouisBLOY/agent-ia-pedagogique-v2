# Phase 12.16-G2-R3B-R4-R3-R1 — Plan de continuation

## Matrice gelée

- Version : `12.16-g2-r4-r4-anthropic-recovery-completion-v1`.
- Checksum : `8cdc7c5b1ed6eaeb02606b2130db43d398bdbe51d99116d97014cb014e8b3526`.
- Cardinalité : `38` appels Anthropic, retry/rerun `0`.
- Call 1 : canary de remédiation du HTTP 503 historique.
- Calls 2–38 : anciens slots R3 `PENDING`, avec nouveaux execution IDs.
- Ledger : `artifacts/calibration/12.16-g2-r4-r4/ledger.json` ; hash initial `1424dd5889608790a4d7f4b5f5a757db625f451777f5dc2dc8c0289034cbeb22`.

## Coût

- Maximum par call : `0.036480 USD`.
- Maximum avant marge : `1.386240 USD`.
- Marge : `0.346560 USD`.
- Plafond demandé : `1.732800 USD`.

## Calls

1. `remediation.r4-r3.http503.scn-07.b.correction-quality.canary.r1` → `cal.score.anchor.scn-07.b.correction-quality.r1` (`INITIAL_ANCHOR`).
2. `continuation.r4-r4.cal.score.anchor.scn-07.b.remediation-clarity.r1` → `cal.score.anchor.scn-07.b.remediation-clarity.r1` (`INITIAL_ANCHOR`).
3. `continuation.r4-r4.cal.score.anchor.scn-07.c.correction-quality.r1` → `cal.score.anchor.scn-07.c.correction-quality.r1` (`INITIAL_ANCHOR`).
4. `continuation.r4-r4.cal.score.anchor.scn-07.c.remediation-clarity.r1` → `cal.score.anchor.scn-07.c.remediation-clarity.r1` (`INITIAL_ANCHOR`).
5. `continuation.r4-r4.cal.score.anchor.scn-08.a.distractor-quality.r1` → `cal.score.anchor.scn-08.a.distractor-quality.r1` (`INITIAL_ANCHOR`).
6. `continuation.r4-r4.cal.score.anchor.scn-08.a.feedback-quality.r1` → `cal.score.anchor.scn-08.a.feedback-quality.r1` (`INITIAL_ANCHOR`).
7. `continuation.r4-r4.cal.score.anchor.scn-08.b.distractor-quality.r1` → `cal.score.anchor.scn-08.b.distractor-quality.r1` (`INITIAL_ANCHOR`).
8. `continuation.r4-r4.cal.score.anchor.scn-08.b.feedback-quality.r1` → `cal.score.anchor.scn-08.b.feedback-quality.r1` (`INITIAL_ANCHOR`).
9. `continuation.r4-r4.cal.score.anchor.scn-08.c.distractor-quality.r1` → `cal.score.anchor.scn-08.c.distractor-quality.r1` (`INITIAL_ANCHOR`).
10. `continuation.r4-r4.cal.score.anchor.scn-08.c.feedback-quality.r1` → `cal.score.anchor.scn-08.c.feedback-quality.r1` (`INITIAL_ANCHOR`).
11. `continuation.r4-r4.cal.score.anchor.scn-01.a.clarity.r2` → `cal.score.anchor.scn-01.a.clarity.r2` (`REPEATABILITY`).
12. `continuation.r4-r4.cal.score.anchor.scn-01.a.organization-utility.r2` → `cal.score.anchor.scn-01.a.organization-utility.r2` (`REPEATABILITY`).
13. `continuation.r4-r4.cal.score.anchor.scn-02.a.relevance.r2` → `cal.score.anchor.scn-02.a.relevance.r2` (`REPEATABILITY`).
14. `continuation.r4-r4.cal.score.anchor.scn-02.a.coverage.r2` → `cal.score.anchor.scn-02.a.coverage.r2` (`REPEATABILITY`).
15. `continuation.r4-r4.cal.score.anchor.scn-03.a.clarity.r2` → `cal.score.anchor.scn-03.a.clarity.r2` (`REPEATABILITY`).
16. `continuation.r4-r4.cal.score.anchor.scn-03.a.level-adaptation.r2` → `cal.score.anchor.scn-03.a.level-adaptation.r2` (`REPEATABILITY`).
17. `continuation.r4-r4.cal.score.anchor.scn-04.a.fidelity.r2` → `cal.score.anchor.scn-04.a.fidelity.r2` (`REPEATABILITY`).
18. `continuation.r4-r4.cal.score.anchor.scn-04.a.level-adaptation.r2` → `cal.score.anchor.scn-04.a.level-adaptation.r2` (`REPEATABILITY`).
19. `continuation.r4-r4.cal.score.anchor.scn-05.a.difficulty-appropriateness.r2` → `cal.score.anchor.scn-05.a.difficulty-appropriateness.r2` (`REPEATABILITY`).
20. `continuation.r4-r4.cal.score.anchor.scn-05.a.instruction-clarity.r2` → `cal.score.anchor.scn-05.a.instruction-clarity.r2` (`REPEATABILITY`).
21. `continuation.r4-r4.cal.score.anchor.scn-06.a.assessment-clarity.r2` → `cal.score.anchor.scn-06.a.assessment-clarity.r2` (`REPEATABILITY`).
22. `continuation.r4-r4.cal.score.anchor.scn-06.a.marking-scheme-coherence.r2` → `cal.score.anchor.scn-06.a.marking-scheme-coherence.r2` (`REPEATABILITY`).
23. `continuation.r4-r4.cal.score.anchor.scn-07.a.correction-quality.r2` → `cal.score.anchor.scn-07.a.correction-quality.r2` (`REPEATABILITY`).
24. `continuation.r4-r4.cal.score.anchor.scn-07.a.remediation-clarity.r2` → `cal.score.anchor.scn-07.a.remediation-clarity.r2` (`REPEATABILITY`).
25. `continuation.r4-r4.cal.score.anchor.scn-08.a.distractor-quality.r2` → `cal.score.anchor.scn-08.a.distractor-quality.r2` (`REPEATABILITY`).
26. `continuation.r4-r4.cal.score.anchor.scn-08.a.feedback-quality.r2` → `cal.score.anchor.scn-08.a.feedback-quality.r2` (`REPEATABILITY`).
27. `continuation.r4-r4.cal.score.output.scn-03.clarity.r1` → `cal.score.output.scn-03.clarity.r1` (`SELECTED_OUTPUT`).
28. `continuation.r4-r4.cal.score.output.scn-03.level-adaptation.r1` → `cal.score.output.scn-03.level-adaptation.r1` (`SELECTED_OUTPUT`).
29. `continuation.r4-r4.cal.score.output.scn-04.fidelity.r1` → `cal.score.output.scn-04.fidelity.r1` (`SELECTED_OUTPUT`).
30. `continuation.r4-r4.cal.score.output.scn-04.level-adaptation.r1` → `cal.score.output.scn-04.level-adaptation.r1` (`SELECTED_OUTPUT`).
31. `continuation.r4-r4.cal.score.output.scn-05.difficulty-appropriateness.r1` → `cal.score.output.scn-05.difficulty-appropriateness.r1` (`SELECTED_OUTPUT`).
32. `continuation.r4-r4.cal.score.output.scn-05.instruction-clarity.r1` → `cal.score.output.scn-05.instruction-clarity.r1` (`SELECTED_OUTPUT`).
33. `continuation.r4-r4.cal.score.output.scn-06.assessment-clarity.r1` → `cal.score.output.scn-06.assessment-clarity.r1` (`SELECTED_OUTPUT`).
34. `continuation.r4-r4.cal.score.output.scn-06.marking-scheme-coherence.r1` → `cal.score.output.scn-06.marking-scheme-coherence.r1` (`SELECTED_OUTPUT`).
35. `continuation.r4-r4.cal.score.output.scn-07.correction-quality.r1` → `cal.score.output.scn-07.correction-quality.r1` (`SELECTED_OUTPUT`).
36. `continuation.r4-r4.cal.score.output.scn-07.remediation-clarity.r1` → `cal.score.output.scn-07.remediation-clarity.r1` (`SELECTED_OUTPUT`).
37. `continuation.r4-r4.cal.score.output.scn-08.distractor-quality.r1` → `cal.score.output.scn-08.distractor-quality.r1` (`SELECTED_OUTPUT`).
38. `continuation.r4-r4.cal.score.output.scn-08.feedback-quality.r1` → `cal.score.output.scn-08.feedback-quality.r1` (`SELECTED_OUTPUT`).

## Approbation financière exacte requise

```text
J'approuve exclusivement l'exécution conditionnelle de la matrice
12.16-g2-r4-r4-anthropic-recovery-completion-v1,
checksum 8cdc7c5b1ed6eaeb02606b2130db43d398bdbe51d99116d97014cb014e8b3526,
38 appels maximum (38 Anthropic Scorer claude-sonnet-5, thinking adaptive, effort low, max_output_tokens 2048),
plafond 1.732800 USD,
aucun retry, canary en premier et arrêt immédiat au premier échec technique.
```

## Autorisation de transfert exacte requise

```text
J'autorise explicitement l'envoi à l'API Anthropic, exclusivement pour
la matrice conditionnelle 12.16-g2-r4-r4-anthropic-recovery-completion-v1,
checksum 8cdc7c5b1ed6eaeb02606b2130db43d398bdbe51d99116d97014cb014e8b3526,
des anchors synthétiques strictement nécessaires et des projections pédagogiques minimisées des six outputs historiques.
Aucune base SQLite, aucun document source complet et aucun secret supplémentaire.
```

Aucun de ces appels n'a été exécuté pendant R1.
