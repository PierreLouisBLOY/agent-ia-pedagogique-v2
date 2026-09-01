# Phase 12.16-G2-V4.3 — Final handoff

## Statut

`V4_3_METRIC_DISCRIMINATION_ANALYSIS = PASS`

Le lot demandé est complet et strictement hors ligne. `PASS` signifie que l'analyse a été produite, que les constats sont réconciliés avec les artefacts et que les validations ciblées ont réussi. Il ne signifie ni adoption d'un seuil de release, ni succès discriminant du protocole V4.2.

## Résultats

- `PRIMARY_ROOT_CAUSE = SCORER_CONTRACT_UNDERSPECIFIED_FOR_PEDAGOGICAL_DISCRIMINATION`
- `SECONDARY_ROOT_CAUSES = [POST_HOC_PAIRWISE_FROM_INDEPENDENT_SATURATED_SCORES, TRINARY_METRIC_VS_V4_PRIMARY_GATE_MISMATCH, NEGATIVE_CONTROL_PROXIMITY_AND_DEFECT_LEXICAL_LEAKAGE, RATIONALE_AUDITABILITY_GAP]`
- `CONFIDENCE = HIGH`
- Monotonie trinaire stricte : `0/16`.
- Monotonie trinaire faible : `11/16`.
- Gate primaire V4 recalculée `Strong > each negative` : `6/16`.
- Inversions : `5`, toutes `Mixed < Weak`.
- Ties adjacents anchors : `13/32`.
- Pairwise selected-output : `6/6` ties, tous `1/1 == 1/1`.
- Saturation extrême : `47/48` scores à 0 ou 1.
- Recommandation : préparer une V5 provider-neutral avec critères opérationnels, échelle définie, rationale structurée, comparaison A/B directe et séparation des métriques primaire/secondaire.

## Baseline et provenance vérifiées

- Baseline commit : `a560d6ca1989ba3dd13c9d02eeb97ef3fff6238b`.
- Matrice V4.2 : `605358444f1bc9052ca7b4e55057c9d5424b3ad3b4deecc17bdde83e23c18aa5`.
- Review contract : `1201a11ddb6b2d57b28a0f8ab20ce58f87a78e02be555c0c5248edbf525f8b1d`.
- Pricing : `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`.
- Manifest du run V4.2 : `41a26ccb50dac41ac2a548729f5d2cdc2f26d6a1262ed24ee5558e958f019983`.
- Verdict source : `CALIBRATION_COMPLETE`.
- Release threshold source : `NONE`.
- Autorisation V4.2 : `CONSUMED`; état effectif `live_provider_recalibration_authorized = false`.

Les artefacts V4.1/V4.2 ont été lus sans modification. Les sept fichiers V4.2 déjà non suivis étaient présents avant V4.3 et ont été préservés.

## Validation ciblée

Commande exécutée avec fakes locaux et cache pytest désactivé :

```text
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .tmp/pytest-v4-3-metric-analysis tests/unit/test_anthropic_evaluation_scorer.py tests/integration/test_anthropic_score_evaluator_integration.py tests/unit/test_pedagogical_calibration_call_plan.py tests/unit/test_pedagogical_calibration_v4_2.py tests/architecture/test_openai_review_anthropic_scorer_fitness.py tests/calibration/pedagogical/test_anchor_corpus_v4.py
```

Résultat : `70 passed in 10.45s`.

Aucun script d'analyse n'a été ajouté. Ruff, mypy et compileall ne sont donc pas applicables aux seuls fichiers Markdown créés. La validation finale comprend aussi le contrôle du manifest, des fins de ligne/whitespaces et `git diff --check` sur le périmètre suivi.

## Garde-fous finaux

- `PROVIDER_CALLS = 0`
- `OPENAI_CALLS = 0`
- `ANTHROPIC_CALLS = 0`
- `CREDENTIAL_RESOLUTION = 0`
- `TRANSPORT_INVOCATIONS = 0`
- `RETRY = 0`
- `RERUN = 0`
- `RELEASE_THRESHOLD_ADOPTED = NONE`
- `COMMIT = NONE`
- `PUSH = NONE`
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`

## Suite proposée, non exécutée

Préparer un lot V5 strictement offline séparé. Toute nouvelle matrice live devra faire l'objet d'une baseline, d'un pricing, d'un plafond, d'une autorisation de transfert et d'une autorisation live nouveaux. Le présent handoff ne confère aucune de ces autorisations.
