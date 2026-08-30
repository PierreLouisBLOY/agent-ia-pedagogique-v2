# Phase 12.16-G2 — Rapport final d’analyse de calibration

## Résultat

- Statut : `PASS / CLOSED`.
- Analyse strictement hors ligne : `0` appel OpenAI, `0` appel Anthropic, `0.000000 USD`.
- Manifeste final : `76` résultats ; SHA-256 `273c5b6e9cfe36d5bebf364337a050eecb8d13077f3409c34da6c8f7f8698677`.
- Split : `48 initial / 16 repeatability / 12 selected-output`.
- Policy : `claude-sonnet-5 / adaptive / low / 2048`, uniforme.

## Preuves

- r2_ledger_sha256 : `ef694ad8174a28079db030086d83d0ffb8d02d7aed598092961b821b3fdd2a31`.
- r2_summary_sha256 : `ec88b72b616793bd4d215ec1f4a5e24a03b458691e1b00ce7491b4f6486d5948`.
- r2_raw_sha256 : `a16287401cc87863d23dc170b76cf2983ccae1909374d2a3b6af8226642f6053`.
- r3_ledger_sha256 : `bd4f9272730c225a7e1a309137cf937bcb0b8a9603446cc76c8d94871a029c99`.
- r3_summary_sha256 : `c3052b33193bf6542cd96a2ff1706c8d210e297c736d1d3ffa101676c9405729`.
- r3_transfer_manifest_sha256 : `c8742f5e4a46215a34141e93b17b36a730c6ab6136b3c92ad3eba073be1e905a`.
- r3_raw_ordered_list_sha256 : `f39d83334eda6b0f87b4ecf363e9f432d818b298d55defa6c1076ec766a34c52`.
- continuation_ledger_sha256 : `4271bbcc24d453fa596eb200c2e4bcf02892599175fbc106ce3e684154f0dd17`.
- continuation_summary_sha256 : `83c5da3d662a33036d840da147920ed2f137c9704039a5a42a861cf5b34da7fd`.
- continuation_transfer_manifest_sha256 : `723ce92f820c2e18416d19ed372ecbe3fb2065b9a50fd54c664834c12170f685`.
- continuation_raw_call_order_sha256 : `a6b75cb01e8fe8ce3935b1c4ba7b8a060a79c949eb39e340e0c03115b7c9a894`.

## Ordre des ancres

- Preuve ordinale : `PARTIAL`.
- Ordres stricts : `1/16`.
- Ordres faibles : `16/16`.
- Égalités adjacentes : `20` ; inversions : `0`.
- Règle pré-déclarée : STRONG iff all 16 complete orderings are strict; CONTRADICTORY iff any adjacent inversion exists; PARTIAL iff complete and weak without inversion; otherwise INSUFFICIENT.

| Scénario | Critère | strong | mixed | weak | strict | égalités | inversions | range | distincts | saturation |
|---|---|---:|---:|---:|:---:|---:|---:|---:|---:|---:|
| SCN-01 | `scn-01.quality.clarity` | 1/1 | 1/1 | 1/1 | FAIL | 2 | 0 | 0/1 | 1 | 3 |
| SCN-01 | `scn-01.quality.organization-utility` | 1/1 | 1/1 | 1/2 | FAIL | 1 | 0 | 1/2 | 2 | 2 |
| SCN-02 | `scn-02.quality.relevance` | 1/1 | 1/1 | 1/1 | FAIL | 2 | 0 | 0/1 | 1 | 3 |
| SCN-02 | `scn-02.quality.coverage` | 1/1 | 1/1 | 1/1 | FAIL | 2 | 0 | 0/1 | 1 | 3 |
| SCN-03 | `scn-03.quality.clarity` | 1/1 | 1/1 | 1/1 | FAIL | 2 | 0 | 0/1 | 1 | 3 |
| SCN-03 | `scn-03.quality.level-adaptation` | 1/1 | 1/1 | 0/1 | FAIL | 1 | 0 | 1/1 | 2 | 3 |
| SCN-04 | `scn-04.quality.fidelity` | 1/1 | 1/1 | 0/1 | FAIL | 1 | 0 | 1/1 | 2 | 3 |
| SCN-04 | `scn-04.quality.level-adaptation` | 1/1 | 1/1 | 1/2 | FAIL | 1 | 0 | 1/2 | 2 | 2 |
| SCN-05 | `scn-05.quality.difficulty-appropriateness` | 1/1 | 0/1 | 0/1 | FAIL | 1 | 0 | 1/1 | 2 | 3 |
| SCN-05 | `scn-05.quality.instruction-clarity` | 0/1 | 0/1 | 0/1 | FAIL | 2 | 0 | 0/1 | 1 | 3 |
| SCN-06 | `scn-06.quality.assessment-clarity` | 1/1 | 1/2 | 0/1 | PASS | 0 | 0 | 1/1 | 3 | 2 |
| SCN-06 | `scn-06.quality.marking-scheme-coherence` | 1/1 | 1/1 | 0/1 | FAIL | 1 | 0 | 1/1 | 2 | 3 |
| SCN-07 | `scn-07.quality.correction-quality` | 1/1 | 1/1 | 0/1 | FAIL | 1 | 0 | 1/1 | 2 | 3 |
| SCN-07 | `scn-07.quality.remediation-clarity` | 1/1 | 1/1 | 0/1 | FAIL | 1 | 0 | 1/1 | 2 | 3 |
| SCN-08 | `scn-08.quality.distractor-quality` | 1/1 | 0/1 | 0/1 | FAIL | 1 | 0 | 1/1 | 2 | 3 |
| SCN-08 | `scn-08.quality.feedback-quality` | 1/1 | 1/1 | 0/1 | FAIL | 1 | 0 | 1/1 | 2 | 3 |

### Distribution exacte

Valeurs distinctes : `3` ; zéros : `14` ; uns : `31` ; intermédiaires : `3`.

| Fraction | Fréquence |
|---:|---:|
| 0/1 | 14 |
| 1/2 | 3 |
| 1/1 | 31 |

| Tier d’analyse | Moyenne rationnelle | Médiane rationnelle |
|---|---:|---:|
| STRONG | 15/16 | 1/1 |
| MIXED | 25/32 | 1/1 |
| WEAK_BUT_STRUCTURALLY_VALID | 5/16 | 0/1 |

## Répétabilité

- Preuve : `PARTIAL` ; deux observations par groupe seulement : `TRUE`.
- Accord exact : `14/16` (7/8).
- Spread maximal : `1/1` ; delta absolu moyen : `9/80`.

| Critère | Initial | Répétition | Delta absolu | Direction |
|---|---:|---:|---:|---|
| `scn-01.quality.clarity` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-01.quality.organization-utility` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-02.quality.coverage` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-02.quality.relevance` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-03.quality.clarity` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-03.quality.level-adaptation` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-04.quality.fidelity` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-04.quality.level-adaptation` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-05.quality.difficulty-appropriateness` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-05.quality.instruction-clarity` | 0/1 | 0/1 | 0/1 | UNCHANGED |
| `scn-06.quality.assessment-clarity` | 1/1 | 0/1 | 1/1 | DOWN |
| `scn-06.quality.marking-scheme-coherence` | 1/1 | 1/5 | 4/5 | DOWN |
| `scn-07.quality.correction-quality` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-07.quality.remediation-clarity` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-08.quality.distractor-quality` | 1/1 | 1/1 | 0/1 | UNCHANGED |
| `scn-08.quality.feedback-quality` | 1/1 | 1/1 | 0/1 | UNCHANGED |

## Selected-output

- Statut : `DESCRIPTIVE_ONLY`.
- FALLBACK_SOFT_QUALITY_COMPARISON = `NOT_ESTABLISHED`.

| Source | Critère | Score | strong/mixed/weak | Classe relative | Modèle source |
|---|---|---:|---:|---|---|
| `cal.generation.course.primary.r1` | `scn-03.quality.clarity` | 1/1 | 1/1 ; 1/1 ; 1/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-terra` |
| `cal.generation.course.primary.r1` | `scn-03.quality.level-adaptation` | 1/1 | 1/1 ; 1/1 ; 0/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-terra` |
| `cal.transformation.resource.primary.r1` | `scn-04.quality.fidelity` | 1/1 | 1/1 ; 1/1 ; 0/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-terra` |
| `cal.transformation.resource.primary.r1` | `scn-04.quality.level-adaptation` | 1/1 | 1/1 ; 1/1 ; 1/2 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-terra` |
| `cal.generation.exercise.primary.r1` | `scn-05.quality.difficulty-appropriateness` | 1/1 | 1/1 ; 0/1 ; 0/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-terra` |
| `cal.generation.exercise.primary.r1` | `scn-05.quality.instruction-clarity` | 0/1 | 0/1 ; 0/1 ; 0/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-terra` |
| `cal.generation.assessment.primary.r1` | `scn-06.quality.assessment-clarity` | 1/1 | 1/1 ; 1/2 ; 0/1 | EQUAL_STRONG | `gpt-5.6-terra` |
| `cal.generation.assessment.primary.r1` | `scn-06.quality.marking-scheme-coherence` | 1/1 | 1/1 ; 1/1 ; 0/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-terra` |
| `cal.correction.remediation.primary.r1` | `scn-07.quality.correction-quality` | 1/1 | 1/1 ; 1/1 ; 0/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-sol` |
| `cal.correction.remediation.primary.r1` | `scn-07.quality.remediation-clarity` | 1/1 | 1/1 ; 1/1 ; 0/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-sol` |
| `cal.generation.qcm.primary.r1` | `scn-08.quality.distractor-quality` | 1/1 | 1/1 ; 0/1 ; 0/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-terra` |
| `cal.generation.qcm.primary.r1` | `scn-08.quality.feedback-quality` | 1/1 | 1/1 ; 1/1 ; 0/1 | UNCLASSIFIABLE_NON_MONOTONIC_ANCHORS | `gpt-5.6-terra` |

## Fiabilité technique finale

- Réponses structurées valides : `76/76`; SCORED `76`, INCONCLUSIVE `0`, error `0`, refusal `0`.
- Tokens : input `79273`, cache `0`, output `5016`, thinking `2789`, total `84289`.
- Latence ms : total `184378`, min `1144`, médiane `2241/1`, p95 `3917`, max `12125`.
- Coût final Anthropic mesuré : `0.208706 USD`.

## Résultats OpenAI réutilisés

- `20` résultats terminaux audités : `13 G2 + 1 R2B + 6 R3B`; aucun nouvel appel.
- CORRECTION : `3` résultats, statuts `{'COMPLETED': 3}`, tokens `2355`, latence `10845 ms`, coût `0.016158 USD`.
- GENERATION : `8` résultats, statuts `{'COMPLETED': 8}`, tokens `5955`, latence `31333 ms`, coût `0.035376 USD`.
- REVIEW_SOL : `5` résultats, statuts `{'PARTIAL': 5}`, tokens `10520`, latence `95208 ms`, coût `0.140464 USD`.
- REVIEW_TERRA : `2` résultats, statuts `{'SUCCEEDED': 2}`, tokens `2560`, latence `12649 ms`, coût `0.013320 USD`.
- TRANSFORMATION : `2` résultats, statuts `{'COMPLETED': 2}`, tokens `1510`, latence `4302 ms`, coût `0.006420 USD`.

## Comptabilité sans double comptage

- A. Final useful OpenAI : `0.211738 USD`.
- B. Final uniform Anthropic : `0.208706 USD`.
- C. Diagnostic/remédiation mesuré : `0.054800 USD`.
- D. Réserves conservatrices non prouvées facturées : `1.957696 USD`.
- Coût final utile : `0.420444 USD`; coût expérimental mesuré : `0.475244 USD`.
- Les dashboards fournisseurs restent la source de vérité de facturation.

## Décision bornée et revue humaine

- ANCHOR_ORDINAL_EVIDENCE = `PARTIAL`.
- REPEATABILITY_EVIDENCE = `PARTIAL`.
- SELECTED_OUTPUT_EVIDENCE = `DESCRIPTIVE_ONLY`.
- HUMAN_ANCHOR_REVIEW = `NOT_COMPLETED`.
- CALIBRATION_CONFIDENCE = `PROVISIONAL_PENDING_HUMAN_REVIEW`.
- RELEASE_THRESHOLD_ADOPTION = `NOT_ALLOWED`.
- PROVIDER_ROUTE_CHANGE = `NONE`.
- Paquet aveugle : `docs/development/PHASE_12_16_G2_HUMAN_ANCHOR_REVIEW_PACKET.md` ; 24 items ; statut `NOT_COMPLETED`.

## Validation et livraison

- Tests ciblés/régression : `PASS_37`.
- Pytest global : `PASS_4298_SKIPPED_3_EXPLICIT_OPTIONAL_GATES`.
- Ruff global : `PASS`.
- Mypy backend + evaluation_harness : `PASS_689_SOURCE_FILES`.
- Compileall : `PASS`.
- Diff-check : `PASS` ; sécurité : `PASS_NO_SECRET_PRIVATE_PATH_RUNTIME_DATA`.
- Commit attendu : `test: analyze pedagogical model calibration` ; parent `123b4ebec6633df5c4512fce0e4755415f00c38d`.
- Branche : `phase12/12-16-provider-model-calibration` ; main inchangée : `True`.
- Le SHA du commit est rapporté après création ; il n’est pas auto-référencé dans le commit.

## Reproductibilité, sécurité et gouvernance

- Projection canonique : `be3d7f03f9fa3fd47b565cbeca51a6c8f48aa70a7f86f6dc9de53be42f24cc90`.
- Paquet humain : `d9ea4b33b84ee52c0460097cf1dd97e89f33a67106c57cc10dd611536b8d1e5e`.
- Aucun float, timestamp variable, raw output, prompt, secret, request ID ou chemin absolu dans les rapports.
- ADR : `NO`; ADR-P12-063 et ADR-P12-064 appliqués.
- Route provider : `NONE`; seuil de release : `NOT_ALLOWED`.
- Prochaine gate : `12.16-G2-HUMAN_ANCHOR_REVIEW_READY`.
