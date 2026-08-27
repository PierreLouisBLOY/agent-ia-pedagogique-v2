# Phase 12.14-D — Baseline du scoring et des rubrics offline

## 1. Parent C

D prolonge ADR-P12-049 et
[ADR-P12-050](../../architecture/adr/ADR-P12-050-agentic-evaluation-assertion-semantics.md)
sans les modifier. Sa décision canonique est
[ADR-P12-051](../../architecture/adr/ADR-P12-051-agentic-evaluation-scoring-rubric-semantics.md).

Parent Git C : `b3985626f547def824d29bb797ac746b6ef47190`.

## 2. Score et assertion

```text
AssertionResult = normative hard check
ScoreResult     = soft graded measurement
SCORE_IS_MEASUREMENT_NOT_AUTHORITY
```

Le score ne produit ni verdict, validation métier, Gate, SecurityDecision ou
RecoveryDecision. Une acceptance par seuil devra devenir un critère hard
explicite chez son owner.

## 3. Représentation numérique

`NormalizedScore` est une fraction exacte réduite dans `[0,1]`. Numérateur et
dénominateur sont des entiers bornés à 128 chiffres ; le dénominateur est
strictement positif. La réduction par PGCD ne perd aucune information.

Le core D n'utilise aucun float, NaN, Inf, contexte Decimal ou arrondi. Les
comparaisons et agrégations utilisent l'arithmétique rationnelle stdlib exacte.

## 4. NormalizedScore

- `0/1` représente le minimum ;
- `1/1` représente le maximum ;
- les fractions équivalentes ont une représentation canonique identique ;
- les produits croisés fournissent un ordre exact ;
- tout dépassement de borne est refusé ou rendu indisponible sans arrondi.

Ce score n'est ni une note `/20`, ni un grade, ni un niveau pédagogique.

## 5. Frontière scorer

`EvaluationScorerPort.score(scorer_ref, observations)` reçoit un tuple ordonné
de valeurs d'observation C et retourne `ScorerOutcome`. La source C et le scorer
sont injectés dans `ScoreEvaluator`; aucune I/O ou résolution globale n'existe.

`EvaluationScorerRef`, `EvaluationRubricRef` et `EvaluationCriterionRef` sont
des identités caller-supplied sûres et bornées.

## 6. Status

`ScoreStatus` contient exactement `SCORED`, `INCONCLUSIVE`, `ERROR`. Il n'est
pas un verdict et ne contient ni PASS, FAIL ou SKIPPED.

## 7. ScoreResult

`ScoreResult` porte version, criterion ref, scorer ref, status, score optionnel
et reason code fermé. Un résultat `SCORED` exige un score et aucune reason. Les
deux autres statuts interdisent le score et exigent une reason.

Aucune observation, actual/expected, exception, message, payload, prompt ou
configuration libre n'est conservée.

## 8. Criterion

`EvaluationScoringCriterionSpec` contient :

```text
schema_version
criterion_ref
scorer_ref
observation_refs
weight
```

La spec frozen/slotted accepte 1 à 16 observation refs ordonnées et uniques.
Elle ne contient ni callable, import path, provider/model, prompt, mapping
arbitraire ou seuil de verdict.

## 9. Rubric

`EvaluationRubric` contient une version, une rubric ref et 1 à 32 criteria
ordonnés. Les criterion refs sont uniques et leurs versions correspondent à la
rubric. La limite 32 borne la configuration et le calcul exact.

## 10. Poids

Chaque poids est un `NormalizedScore` strictement positif. La somme doit être
exactement `1/1`. Un poids nul et une somme différente sont rejetés. Il n'existe
aucune normalisation ou correction silencieuse.

## 11. Agrégation

`RubricAggregator` calcule exactement :

```text
Σ(weight × score)
```

Les résultats sont remis dans l'ordre canonique de la rubric sans dépendre de
l'ordre d'un dict. La sortie est un `RubricScoreResult` distinct contenant le
score agrégé optionnel et les résultats de criteria ordonnés.

## 12. Missing, error et inconclusive

```text
ALL_REQUIRED_CRITERIA_MUST_BE_SCORED_FOR_AGGREGATE_SCORE
ERROR > INCONCLUSIVE > SCORED
```

Un criterion manquant, dupliqué, inattendu ou lié au mauvais scorer produit
`ERROR`. Un criterion `ERROR` rend l'agrégat `ERROR`; sinon un criterion
`INCONCLUSIVE` rend l'agrégat `INCONCLUSIVE`. Aucun score partiel n'est publié
et les poids ne sont jamais renormalisés.

## 13. Hard assertion precedence

Un case `PASS` avec score bas est valide. Un case `FAIL` avec score élevé est
valide. Un case `PASS` avec assertion non-PASS reste invalide selon C.

```text
HARD_ASSERTION_FAILURE_CANNOT_BE_HIDDEN_BY_SCORE
HARD_INVARIANT_FAILURE_CANNOT_BE_HIDDEN_BY_WEIGHTED_SCORE
```

## 14. Confidentialité

Les sources/scorers de test peuvent recevoir des chaînes synthétiques
adversariales bornées. `ScoreResult` et `RubricScoreResult` ne les copient
jamais. Aucun vrai secret ou chemin privé réel n'est introduit.

## 15. Déterminisme

Les mêmes scores et rubric donnent le même agrégat exact. L'ordre de sortie est
celui de la rubric. Les tests couvrent fractions non réduites, bornes 0/1,
valeurs invalides, grandes composantes, poids incorrects, ordre inversé,
statuts mixtes et indépendance au contexte Decimal global.

## 16. Architecture et audit des overlaps

| Concept | Owner | Décision D |
| --- | --- | --- |
| retrieval channel/fusion scores | Evidence/retrieval | distinct, projection future explicite |
| Evidence coverage | Evidence | distinct |
| Review coverage/confidence | Review | distinct |
| circuit-breaker thresholds | recovery | policy, jamais score D |
| metric values | observability | distinct |
| quality_evaluation | futur domaine métier | scaffold intact |

```text
EVALUATION_SCORE_DOES_NOT_ALIAS_EXISTING_OWNER_SCORE
```

Le graphe B/C reste inchangé : backend n'importe jamais le harness; le seul
import backend du harness reste `backend.shared_kernel._value_safety`. Aucun
pytest, tests, runtime, infrastructure, provider ou quality_evaluation n'entre
dans le core.

## 17. Intégration au résultat de case

Option A ajoute à `CaseEvaluationResult` :

```text
score_results: tuple[ScoreResult, ...] = ()
rubric_results: tuple[RubricScoreResult, ...] = ()
```

Les defaults préservent B/C. Les criterion/rubric refs sont uniques et bornées.
La valeur d'un score n'influence jamais le verdict. Un case SKIPPED ne porte
aucun résultat de score.

## 18. Décisions ordinales et binaires

```text
ORDINAL_SCORING_DEFERRED_UNTIL_REAL_USE_CASE
BINARY_NORMATIVE_CHECK = ASSERTION
SOFT_GRADED_MEASUREMENT = SCORE
```

Aucun contrat ordinal ou `BinaryScore` spéculatif n'est créé.

## 19. Frontières

| Scope | Propriétaire futur |
| --- | --- |
| case/suite runner, fixtures, répétitions, timeouts | E |
| JSON/Markdown/JUnit et artifacts | F |
| projections runtime et adapters d'owner scores | G |
| scénarios/barèmes STMG/BTS | 12.15 |
| providers, modèles, judge, prix et calibration | 12.16 |

D ne commence aucun de ces scopes.

```text
RATIONALIZATION = SOFT_SCORING_DISTINCT_FROM_HARD_ASSERTIONS
```
