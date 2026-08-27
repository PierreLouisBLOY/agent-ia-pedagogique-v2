# ADR-P12-051 — Sémantique du scoring et des rubrics agentiques offline

## Statut

Accepté pour la Phase 12.14-D.

## Contexte

ADR-P12-049 établit la frontière du harness offline. ADR-P12-050 sépare les
assertions normatives du runtime et réserve à D la qualité graduée. D doit
mesurer cette qualité sans transformer un score en verdict, validation métier,
calibration fournisseur ou autorité.

Le dépôt possède déjà plusieurs nombres appelés scores, couvertures,
confiances, seuils ou métriques. Ils restent la propriété de leurs modules et
ne sont pas des scores génériques du harness.

## Audit des concepts existants

| Concept existant | Owner | Sémantique | Type réutilisable | Valeur réutilisable | Distinct de D |
| --- | --- | --- | --- | --- | --- |
| lexical/semantic/relational score | Evidence retrieval | signal technique par canal | non | adapter futur explicite seulement | oui |
| fusion score | retrieval coordinator | reciprocal-rank fusion et classement | non | adapter futur explicite seulement | oui |
| Evidence coverage | Evidence owner | complétude structurée propriétaire | non | projection G seulement | oui |
| Review coverage/confidence | Review owner | étendue et confiance de revue | non | projection G seulement | oui |
| circuit-breaker thresholds | recovery | policy d'ouverture/rétablissement | non | jamais comme score | oui |
| metric value | observability | mesure d'une série typée | non | observation explicite seulement | oui |
| quality_evaluation scaffold | futur domaine métier | qualité métier non implémentée | non | non | oui |

```text
EVALUATION_SCORE_DOES_NOT_ALIAS_EXISTING_OWNER_SCORE
```

## Décision

### Score gradué et non normatif

Une assertion C est un contrôle hard. Un score D est une mesure soft. Un score
faible ne change pas un case `PASS`; un score élevé ne masque pas un case
`FAIL`. Un seuil d'acceptance futur devra être exprimé explicitement comme
critère normatif par son owner.

`ScoreStatus` est fermé à `SCORED`, `INCONCLUSIVE`, `ERROR`. Aucun score n'est
`PASS`, `FAIL` ou `SKIPPED`.

### Représentation numérique

`NormalizedScore` est un rationnel exact `numerator / denominator` dans
`[0,1]`. Les deux composantes sont des entiers caller-supplied, positives ou
nulles selon leur rôle, et bornées à 128 chiffres. Le dénominateur est strictement
positif. La fraction est réduite par PGCD lors de la construction.

Les floats, NaN, Inf, le contexte Decimal global et tout arrondi sont absents.
Les comparaisons utilisent les produits croisés exacts. Une fraction agrégée
qui dépasserait les bornes devient explicitement `ERROR /
RUBRIC_AGGREGATION_UNAVAILABLE` ; elle n'est jamais arrondie.

```text
NO_GLOBAL_DECIMAL_CONTEXT_DEPENDENCE
NO_IMPLICIT_ROUNDING
```

### Identités et criterion

`EvaluationScorerRef`, `EvaluationRubricRef` et `EvaluationCriterionRef`
réutilisent le pattern d'identité sûre B. Aucun provider ou model ref n'est
introduit.

`EvaluationScoringCriterionSpec` contient version, criterion ref, scorer ref,
un tuple ordonné d'observation refs et un poids exact. Il est frozen/slotted,
limité à 16 observations, sans callable, import path, prompt, config, metadata,
provider params ou seuil PASS/FAIL.

### Scorer injecté

`EvaluationScorerPort.score(scorer_ref, observations)` retourne un
`ScorerOutcome`. Le port et la source d'observations C sont injectés dans
`ScoreEvaluator`. Il n'existe aucun registry global, import dynamique ou I/O
implicite.

Chaque observation est résolue au plus une fois par évaluation de criterion via
un cache local. Une source ou un scorer en erreur est contenu en `ScoreResult`
`ERROR` avec reason code fermé. Aucun texte d'exception n'est copié ou journalisé.

### Résultats

`ScoreResult` contient uniquement version, criterion ref, scorer ref, status,
score rationnel optionnel et reason code fermé. `SCORED` exige un score sans
reason; `INCONCLUSIVE` et `ERROR` interdisent le score et exigent une reason.

`RubricScoreResult` ajoute rubric ref et les criterion results ordonnés. Aucun
résultat ne porte observation, actual, expected, message, exception, payload,
prompt ou contenu libre.

### Rubric et poids

`EvaluationRubric` est frozen/slotted et contient 1 à 32 criteria ordonnés aux
refs uniques. Chaque poids est un `NormalizedScore` strictement positif. Leur
somme rationnelle doit être exactement 1. Un poids nul est interdit et aucune
normalisation implicite n'est effectuée.

La limite 32 borne la configuration, les résultats et le coût arithmétique tout
en couvrant les rubrics génériques attendues.

### Agrégation

`RubricAggregator` réordonne les résultats selon la rubric, valide refs, scorer
refs et versions, puis calcule exactement :

```text
aggregate = Σ(weight_i × score_i)
```

Tous les criteria requis doivent être `SCORED`. Un criterion manquant ou une
configuration dupliquée/inattendue produit `ERROR`. Un `ERROR` de criterion
prend priorité sur `INCONCLUSIVE`, qui prend priorité sur `SCORED`. Aucun
criterion n'est supprimé et aucun poids n'est renormalisé. Aucun score partiel
n'est publié.

### Intégration au case

Option A est retenue. `CaseEvaluationResult` reçoit, avec defaults vides
compatibles B/C :

```text
score_results: tuple[ScoreResult, ...] = ()
rubric_results: tuple[RubricScoreResult, ...] = ()
```

Les refs sont uniques et bornées. Aucun contrôle ne relie la valeur d'un score
au verdict du case. La règle C interdisant un case `PASS` avec assertion
non-PASS reste inchangée.

### Ordinal et binaire

```text
ORDINAL_SCORING_DEFERRED_UNTIL_REAL_USE_CASE
BINARY_NORMATIVE_CHECK = ASSERTION
SOFT_GRADED_MEASUREMENT = SCORE
```

Aucune abstraction ordinale spéculative ou `BinaryScore` n'est créée.

### Invariants d'autorité

```text
SCORE_IS_MEASUREMENT_NOT_AUTHORITY
SCORE_RESULT_NEVER_CREATES_AUTHORITY
SCORE_RESULT_NEVER_MUTATES_CASE_VERDICT
SCORE_RESULT_NEVER_OVERRIDES_ASSERTION_FAILURE
HARD_ASSERTION_FAILURE_CANNOT_BE_HIDDEN_BY_SCORE
HARD_INVARIANT_FAILURE_CANNOT_BE_HIDDEN_BY_WEIGHTED_SCORE
SCORE_RESULT_NEVER_COPIES_RAW_OBSERVATION_VALUE
SCORER_SPEC_NEVER_CONTAINS_ARBITRARY_CALLABLE
RUBRIC_NEVER_CONTAINS_ARBITRARY_METADATA
NO_GLOBAL_MUTABLE_SCORER_REGISTRY
NO_GLOBAL_MUTABLE_RUBRIC_REGISTRY
PRODUCTION_RUNTIME_MUST_NOT_DEPEND_ON_EVALUATION_HARNESS
```

## Frontières différées

- E : runner, cases, répétitions, fixtures, timeout et isolation ;
- F : reporting, sérialisation et artifacts ;
- G : projections runtime et adapters explicites vers les owner scores ;
- 12.15 : scénarios et barèmes pédagogiques ;
- 12.16 : providers, judge models, prix et calibration.

D n'ajoute aucun runner, reporter, adapter runtime/provider, grade scolaire ou
policy métier.

## Conséquences

Le harness dispose d'une mesure graduée exacte, provider-neutral et
non-autoritaire. Les owner scores existants restent distincts et ne peuvent
entrer que par une projection/scorer explicite future.

```text
RATIONALIZATION = SOFT_SCORING_DISTINCT_FROM_HARD_ASSERTIONS
```
