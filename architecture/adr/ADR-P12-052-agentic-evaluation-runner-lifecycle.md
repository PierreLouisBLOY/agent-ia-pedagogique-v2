# ADR-P12-052 — Cycle de vie du runner d'évaluation offline

## Statut

Accepté pour la Phase 12.14-E.

## Contexte

ADR-P12-049 fournit les cases, suites et résultats structurels. ADR-P12-050
possède les assertions hard et ADR-P12-051 le scoring soft. E doit orchestrer
ces owners par répétition sans devenir un runtime de production, un remplaçant
de pytest ou un moteur de recovery.

Les contrats B/C/D ne permettent pas d'attribuer sans ambiguïté une assertion
ou un score lorsque `repeat_count > 1`.

## Rationalisation du modèle de résultat

| Contrat existant | Sémantique manquante | Décision E | Compatibilité |
| --- | --- | --- | --- |
| `CaseExecutionResult` | assertions/scores par répétition | reste un fait d'exécution minimal | inchangé |
| `AssertionResult` | index de répétition | composé dans `RepetitionEvaluationResult` | inchangé |
| `ScoreResult` / `RubricScoreResult` | index de répétition | composés dans `RepetitionEvaluationResult` | inchangés |
| `CaseEvaluationResult` | composition des répétitions | ajout de `repetition_results=()` | defaults B/C/D préservés |
| `SuiteEvaluationResult` | calcul par runner | réutilisé directement | inchangé |

`RepetitionEvaluationResult` est l'owner minimal d'une répétition : un
`CaseExecutionResult`, son verdict hard, ses résultats C/D, un reason code et
le flag d'erreur d'infrastructure. Il n'est pas un second résultat de case.

Lorsqu'un `CaseEvaluationResult` E contient des répétitions, ses anciens champs
plats assertion/score/rubric restent vides. Ses `execution_results` doivent être
exactement ceux des répétitions. Cette redondance contrôlée préserve la forme B
et interdit deux sources de vérité.

## Décision

### Frontière runner

`EvaluationRunner` est un orchestrateur séquentiel offline. Il reçoit des cases
et suites déclaratives et retourne leurs contrats de résultat existants. Il ne
collecte pas les tests, n'offre pas de CLI pytest, n'importe aucun runtime et ne
prend aucune décision Tool, Gate, security ou recovery.

```text
EVALUATION_RUNNER_ORCHESTRATES_EXISTING_OWNERS
EVALUATION_RUNNER_DOES_NOT_BECOME_RUNTIME
```

### Input, fixture et target

Les frontières injectées sont :

```text
EvaluationInputFactoryPort.build(ref, context) -> PreparedEvaluationInput
EvaluationFixtureFactoryPort.create(ref, context) -> EvaluationFixtureHandle
EvaluationFixtureFactoryPort.cleanup(handle, context) -> None
EvaluationTargetExecutorPort.execute(...) -> TargetExecutionOutcome
```

`PreparedEvaluationInput` et `EvaluationFixtureHandle` sont des Protocols
markers non sérialisables. Le core ne possède ni n'inspecte leurs payloads ; les
adapters tests/G en possèdent les types concrets. Les refs inconnues sont
signalées par des exceptions boundary dédiées puis converties en codes fermés.

### Répétition et état frais

`EvaluationRepetitionContext` contient uniquement version, case ID et index
caller-dérivé. Aucun UUID ou temps n'est généré. Pour chaque index de 1 à
`repeat_count`, le runner crée une nouvelle fixture et un nouvel input puis
appelle le target exactement une fois.

```text
EACH_REPETITION_STARTS_FROM_FRESH_TEST_STATE
EVALUATION_REPETITION_IS_NOT_RUNTIME_RETRY
EVALUATION_REPETITION_IS_NOT_RECOVERY_REPLAY
NO_SILENT_RETRY_TO_MAKE_EVALUATION_PASS
```

Une répétition suivante existe uniquement parce qu'elle est déclarée. Aucun
état fixture/input, cache d'observation ou résultat n'est partagé.

### Lifecycle et observations

Le lifecycle baseline est :

```text
fixture create
-> input build
-> target execute
-> immutable observation snapshot captured
-> fixture cleanup
-> assertions C
-> scoring D
```

Le cleanup s'exécute en `finally` dès qu'une fixture valide a été créée, y
compris après erreur input/target. Les observations sont une
`EvaluationObservationSnapshot` immutable : au plus 64 entrées ordonnées, refs
uniques et valeurs canoniques C déjà bornées. Après cleanup, une source locale
éphémère les expose à C/D. Aucun objet runtime brut n'est requis.

Un échec cleanup est une erreur d'infrastructure et prend la priorité sur le
résultat en cours : l'isolation n'est alors pas prouvée. Aucun retry cleanup
n'est effectué.

### Timeout coopératif

`EvaluationClockPort` fournit des secondes entières non négatives. Le runner
construit `EvaluationDeadline(started_at_second, expires_at_second)` juste avant
l'exécution target. Un timeout absent produit une deadline sans expiration.

Le target reçoit ce budget et peut retourner `TIMEOUT`. Après son retour, le
runner vérifie également la clock : `current >= deadline` signifie expiré. Le
core ne promet aucune préemption et n'utilise ni sleep, thread, process, signal
ou cancellation async.

Un timeout produit une exécution `ERROR / EVALUATION_TIMEOUT`, sans assertion,
score ou retry implicite.

### Assertions et scores par répétition

Le runner résout les `assertion_refs` via l'`EvaluationAssertionCatalog` puis
instancie le vrai `AssertionEvaluator` avec la source snapshot et
l'`InvariantEvaluatorPort` injecté. Les assertions sont évaluées dans l'ordre,
à chaque répétition.

`EvaluationCaseScoringPlan` contient les criteria et rubrics D ordonnés. Chaque
criterion est évalué exactement une fois avec le vrai `ScoreEvaluator`; les
rubrics utilisent le vrai `RubricAggregator`. Aucun cache global/cross-criterion
ou moyenne inter-répétitions n'est créé.

Un score faible ou inconclus ne modifie pas le verdict hard. Une erreur
d'exécution du scorer/rubric est une erreur d'infrastructure du runner, et non
une interprétation de la valeur graduée.

### Précédences

Pour une répétition hard :

```text
assertion ERROR          -> ERROR (infrastructure)
scorer/rubric ERROR      -> ERROR (infrastructure)
assertion FAIL           -> FAIL
assertion INCONCLUSIVE   -> INCONCLUSIVE
all assertions PASS      -> PASS
```

Les scores `SCORED` ou `INCONCLUSIVE` ne changent pas cette décision. Pour un
case :

```text
ERROR > FAIL > INCONCLUSIVE > PASS
ALL_REPETITIONS_MUST_PASS_FOR_CASE_PASS
```

`SKIPPED` existe uniquement pour un skip explicite ou une suite abortée. Il
n'est jamais produit à partir d'une erreur.

### Orchestration de suite

Les cases sont exécutés strictement dans l'ordre de `EvaluationSuite.cases`,
sans concurrence. `CONTINUE` poursuit après une erreur d'infrastructure.
`ABORT_SUITE` arrête avant le prochain case uniquement sur une erreur
d'infrastructure ; un FAIL hard ou score faible ne déclenche pas l'abort.

Chaque case restant reçoit un `CaseExecutionResult(SKIPPED)` et un
`RepetitionEvaluationResult(SKIPPED / SUITE_ABORTED)`, sans aucun appel de
fixture, input, target, assertion ou scorer.

La suite réutilise `SuiteEvaluationResult`, conserve l'ordre et applique la
même précédence. Un mélange PASS/SKIPPED est `INCONCLUSIVE`; une suite est
`SKIPPED` uniquement si tous ses cases le sont.

### Failure containment et taxonomie

Les erreurs injectées sont converties en `EvaluationRunnerReasonCode` fermé :
configuration, fixture setup/cleanup, input, target, timeout, clock, assertion,
scoring, skip ou abort. Aucun `repr`, `str`, objet d'exception ou contenu brut
n'entre dans un résultat, log, événement sécurité ou retry recovery.

### Invariants

```text
EVALUATION_RUNNER_NEVER_CREATES_RUNTIME_AUTHORITY
EVALUATION_RUNNER_NEVER_BYPASSES_SECURITY_GATE_OR_RECOVERY
EVALUATION_REPLAY_DOES_NOT_REINVOKE_REAL_EXTERNAL_EFFECT_BY_DEFAULT
NO_GLOBAL_MUTABLE_FIXTURE_REGISTRY
NO_GLOBAL_MUTABLE_TARGET_REGISTRY
NO_UNBOUNDED_CONCURRENCY
NO_UNBOUNDED_EXECUTION_LOOP
NO_RAW_EXCEPTION_IN_RESULT
```

## Frontières différées

- F : reporting, sérialisation, comparaison et artifacts ;
- G : adapters vers les owners runtime et protection des effets réels ;
- 12.15 : scénarios pédagogiques E2E ;
- 12.16 : providers, judge models, calibration et statistiques.

E ne produit aucun fichier, rapport, baseline diff, provider adapter, barème ou
scénario pédagogique.

## Conséquences

Le harness peut exécuter déterministement les cases B et composer C/D avec une
traçabilité complète par répétition. Le timeout reste volontairement
coopératif ; les adapters futurs doivent respecter la deadline et l'isolation.

```text
RATIONALIZATION = RUNNER_COMPOSES_EXISTING_ASSERTION_AND_SCORING_OWNERS
```
