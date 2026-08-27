# Phase 12.14-C — Baseline des assertions et invariants offline

## 1. Parent B

Ce lot étend la baseline B définie par
[ADR-P12-049](../../architecture/adr/ADR-P12-049-agentic-evaluation-harness-boundary.md)
sans la modifier. La décision C canonique est
[ADR-P12-050](../../architecture/adr/ADR-P12-050-agentic-evaluation-assertion-semantics.md).

Parent Git B : `19ed05555159217ab13cb02291d85b22378b7dd4`.

```text
12.14-C = ASSERTION_CONTRACTS
        + BOUNDED_OFFLINE_OBSERVATION_VALUES
        + PURE_ASSERTION_EVALUATION
        + INVARIANT_BOUNDARY
```

## 2. Taxonomie

`AssertionKind` est fermé à huit valeurs : `EXACT`, `STRUCTURAL`, `COUNT`,
`SEQUENCE`, `MEMBERSHIP`, `RANGE`, `FORBIDDEN_CONTENT`, `INVARIANT`.

Chaque kind possède une spec frozen/slotted dédiée. Toutes contiennent
`assertion_ref`, `schema_version` et seulement leurs refs/paramètres bornés.
Il n'existe aucun `PREDICATE`, callable, mapping libre, metadata, expression ou
import path.

## 3. Modèle d'observation

Les valeurs persistables dans le core sont limitées à :

| Type | Contenu |
| --- | --- |
| `ObservationScalar` | None, bool, int, Decimal ou str avec kind explicite |
| `ObservationSequence` | tuple ordonné de valeurs canoniques |
| `ObservationField` | code sûr et valeur canonique |
| `ObservationObject` | tuple ordonné de champs aux codes uniques |

Il n'existe ni mapping arbitraire, ni réflexion de dataclass/runtime. `bool` et
`int` restent distincts. Les floats sont exclus ; les Decimal sont finis.

## 4. Limites offline

| Limite | Valeur |
| --- | ---: |
| profondeur maximale | 8 |
| longueur d'une séquence | 64 |
| champs d'un objet | 32 |
| longueur d'une chaîne | 4 096 |
| nœuds totaux | 512 |
| chiffres d'un Decimal | 128 |
| valeur absolue de l'exposant Decimal | 128 |

Les entiers sont bornés à 128 chiffres. Ces limites ne dépendent pas de la
policy runtime.

## 5. Source et catalogue

`EvaluationObservationSourcePort.resolve(ref)` fournit explicitement une valeur
canonique offline. La source est injectée ; le core n'offre aucune I/O ou source
globale. Une ref est résolue au plus une fois par assertion.

`EvaluationAssertionCatalog` contient un tuple ordonné de 512 specs au maximum,
impose les refs uniques et résout de manière déterministe. Il est une
configuration offline immutable, jamais une authority registry.

## 6. Sémantique de l'évaluateur

| Kind | Règle |
| --- | --- |
| EXACT | même type canonique et même valeur profonde |
| STRUCTURAL | même kind, longueurs, ordre/codes de champs et formes imbriquées ; valeurs scalaires ignorées |
| COUNT | taille exacte d'une séquence ou d'un objet seulement |
| SEQUENCE | deux séquences, ordre significatif, égalité canonique profonde |
| MEMBERSHIP | subject séquence, membre comparé par égalité canonique profonde |
| RANGE | int/Decimal, bornes résolues, inclusivité explicite |
| FORBIDDEN_CONTENT | substring littérale, sensible à la casse ou Unicode casefold |
| INVARIANT | délégation du code à une boundary injectée |

`AssertionEvaluator` reçoit une spec, résout ses refs, évalue et retourne un
résultat. Il n'exécute aucun case/suite, répétition, timeout ou retry et ne fait
aucune I/O. Des inputs identiques et le même ordre de source produisent le même
résultat et le même ordre d'appels.

## 7. Reason codes

La taxonomie fermée distingue : mismatches exact, structure, count, sequence,
membership et range ; contenu interdit trouvé ; invariant failed ou
inconclusive ; observation absente, invalide ou non résolue ; configuration
invalide ; invariant absent ou en erreur. Aucun message brut ne complète ces
codes.

## 8. Frontière invariant

`InvariantEvaluatorPort.evaluate(code, observation)` retourne un
`InvariantCheckResult` borné à `PASS`, `FAIL` ou `INCONCLUSIVE`. Le code
`EvaluationInvariantCode` est sûr et opaque. Les futurs adapters observent les
projections des owners canoniques sans reproduire leurs décisions de security,
recovery, Gate ou autorité.

Une exception du checker est contenue en `ERROR / INVARIANT_EVALUATION_ERROR` ;
un invariant inconnu devient `ERROR / INVARIANT_NOT_FOUND`.

## 9. Confidentialité des valeurs

Les valeurs attendues sont résolues par refs et ne résident pas dans les specs.
`AssertionResult` ne contient jamais actual, expected, diff, texte, pattern,
position, extrait, payload, path ou exception.

Les chaînes d'observation acceptent des fixtures adversariales synthétiques
bornées afin de tester `FORBIDDEN_CONTENT`. Elles ne sont ni exportées ni
classifiées comme identités. Les tests n'embarquent aucun secret réel.

## 10. Intégration résultat

Option A est retenue : `CaseEvaluationResult.assertion_results` est un tuple
optionnel par défaut vide, compatible avec les constructions B. Les refs y sont
uniques et bornées par la limite d'assertions d'un case. Un case `PASS` refuse
toute assertion non-PASS ; un case `SKIPPED` refuse tout résultat d'assertion.

`AssertionResult` reste minimal : version, assertion ref, kind, verdict et
reason code fermé. Il est non autoritaire et ne peut devenir implicitement une
`GateDecision`.

## 11. Assertion dure et score futur

Les assertions C sont normatives. D possédera les évaluations graduées :

```text
ASSERTION_FAIL_CANNOT_BE_HIDDEN_BY_SCORE
HARD_INVARIANT_FAILURE_CANNOT_BE_HIDDEN_BY_WEIGHTED_SCORE
```

C ne définit ni point, poids, seuil, rubric, judge model ou score binaire.

## 12. Failure containment

Les erreurs de résolution et de checker sont converties en `AssertionResult`
`ERROR` avec code fermé. Le core ne copie, ne journalise et ne relance pas les
exceptions ; il ne crée aucun SecurityEvent, retry ou mutation runtime.

## 13. Graphe de dépendances

```text
evaluation_harness/assertions -> evaluation_harness/contracts
evaluation_harness            -> stdlib
evaluation_harness            -> backend.shared_kernel._value_safety
tests                          -> evaluation_harness + tests/support
backend                        -X-> evaluation_harness
```

Le allowlist backend de B reste inchangé. Aucun import vers pytest, tests,
agent_runtime, infrastructure ou quality_evaluation n'est permis.

## 14. Frontières C/D/E/F/G

| Lot | Responsabilité |
| --- | --- |
| C | specs, observations, évaluateur pur, invariant boundary |
| D | scores, rubrics, pondération, agrégation |
| E | runner, fixtures, répétitions, timeout, isolation |
| F | reporting, sérialisation, comparison, artifacts |
| G | projections runtime, adapters source/invariants |

Pytest reste le runner et le corpus existant reste intact. Aucun scénario
pédagogique 12.15, fournisseur ou calibration 12.16 n'est ajouté.

## 15. Réutilisation future

| Primitive C | Réutilisation prévue |
| --- | --- |
| specs + catalog | E/G pour relier les refs B |
| observation algebra | G pour les projections runtime bornées |
| source port | adapters G et fixtures de tests |
| invariant port | adapters observant les owners canoniques |
| AssertionResult | E pour composer le résultat de case |
| hard assertion rule | D pour bloquer tout masquage par score |

```text
RATIONALIZATION = ASSERTION_SEMANTICS_REUSE_EXISTING_TEST_OWNERS
```
