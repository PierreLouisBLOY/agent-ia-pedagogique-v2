# Phase 12.14-E — Baseline du runner et du lifecycle offline

## 1. Parent D

E prolonge ADR-P12-049, ADR-P12-050 et
[ADR-P12-051](../../architecture/adr/ADR-P12-051-agentic-evaluation-scoring-rubric-semantics.md)
sans les modifier. La décision E est
[ADR-P12-052](../../architecture/adr/ADR-P12-052-agentic-evaluation-runner-lifecycle.md).

Parent Git D : `ea01fd98db7e2dd41c7f1ab9f397752a6859c774`.

## 2. Frontière du runner

`EvaluationRunner` orchestre des `EvaluationCase` et `EvaluationSuite` offline.
Pytest reste le collecteur et runner de régression. E n'importe ni production
runtime, recovery, infrastructure, provider ou qualité métier et n'accorde
aucune autorité.

## 3. Ports input, fixture et target

| Port | Rôle |
| --- | --- |
| `EvaluationInputFactoryPort` | construit un input opaque frais par répétition |
| `EvaluationFixtureFactoryPort` | crée puis nettoie un handle frais |
| `EvaluationTargetExecutorPort` | appelle un adapter offline/G sous deadline |
| `EvaluationClockPort` | fournit des secondes déterministes injectées |

Les inputs et fixtures sont des Protocols markers. Le core n'en possède aucun
payload et ne les sérialise pas.

## 4. Modèle de répétition

`EvaluationRepetitionContext` contient seulement version, case ID et index.
Les index sont ordonnés de 1 à `repeat_count`. Il n'existe aucun run ID généré,
UUID, clock globale ou « last result wins ».

## 5. Décision du modèle de résultat

`RepetitionEvaluationResult` compose un `CaseExecutionResult`, le verdict hard,
les assertion/score/rubric results, un reason code fermé et un flag infra.

`CaseEvaluationResult.repetition_results=()` préserve B/C/D. Pour un résultat
E, `execution_results` reflète exactement les répétitions et les anciens champs
plats C/D restent vides. `SuiteEvaluationResult` est réutilisé sans wrapper.

## 6. État frais et lifecycle

Chaque répétition effectue : fixture create, input build, target execute,
snapshot immutable, cleanup, assertions, scoring. Les factories sont rappelées
à chaque index ; aucune instance mutable ou observation source n'est partagée.

Le cleanup est exécuté en `finally` après toute création réussie, même si input
ou target échoue. Une erreur cleanup rend la répétition `ERROR` et ne déclenche
aucun retry.

## 7. Snapshot d'observation

`TargetExecutionOutcome` contient uniquement statut, snapshot canonique,
duration optionnelle et reason code. Le snapshot contient au plus 64 couples
ref/valeur C, ordonnés et uniques. Aucun output, prompt, exception ou objet
runtime brut n'est conservé.

Une source locale en mémoire est créée après cleanup pour les évaluateurs C/D,
puis abandonnée avec la répétition.

## 8. Timeout

Le budget commence juste avant `target.execute`. `EvaluationDeadline` est passé
au target, qui coopère et peut retourner `TIMEOUT`. Après retour,
`current_second >= expires_at_second` est aussi expiré.

Le core ne préempte pas et n'utilise ni sleep, thread, process, signal ou async.
Un timeout devient `CaseExecutionStatus.ERROR / EVALUATION_TIMEOUT`, sans retry.

## 9. Assertions et scoring

Les assertion refs sont résolues par `EvaluationAssertionCatalog` et évaluées
par le vrai `AssertionEvaluator` à chaque répétition. L'invariant evaluator est
injecté.

`EvaluationCaseScoringPlan` lie criteria et rubrics D. Le vrai
`ScoreEvaluator` évalue chaque criterion exactement une fois et le vrai
`RubricAggregator` agrège. E ne moyenne pas les répétitions et ne choisit ni la
meilleure ni la dernière.

## 10. Précédence du case

```text
ERROR > FAIL > INCONCLUSIVE > PASS
ALL_REPETITIONS_MUST_PASS_FOR_CASE_PASS
```

Assertion FAIL/ERROR/INCONCLUSIVE détermine le verdict hard. Un score bas,
haut ou inconclus ne le change pas. Une panne de scorer/rubric est une erreur
d'infrastructure d'orchestration.

## 11. Ordre et précédence de suite

Les cases sont séquentiels dans l'ordre déclaré. La suite utilise la même
précédence. `SKIPPED` exige que tous les cases soient skipped ; un mélange
PASS/SKIPPED est inconclusif.

## 12. Policy d'infrastructure

`CONTINUE` poursuit après input, fixture, target, clock, assertion/scorer
internal error ou cleanup error. `ABORT_SUITE` arrête avant les cases suivants.

Un FAIL hard, un score faible ou un score inconclus ne constitue pas une erreur
d'infrastructure et ne déclenche pas l'abort.

## 13. Cases après abort et skip explicite

Chaque case non exécuté après abort reçoit une exécution et répétition
`SKIPPED / SUITE_ABORTED`. Un skip caller-configured produit
`CASE_EXPLICITLY_SKIPPED`. Aucun port, evaluator ou scorer n'est appelé.

Les tags ne provoquent jamais de skip implicite.

## 14. Failure containment et confidentialité

La taxonomie fermée couvre configuration absente, fixture, input, target,
timeout, clock, assertion, scoring, skip et abort. Les exceptions synthétiques
peuvent contenir des textes adversariaux dans les tests, mais aucun message,
path, prompt ou valeur brute n'entre dans les résultats.

## 15. Déterminisme et absence de retry/replay

Les tests prouvent les appels exactement N, les instances fraîches, le cleanup
N fois, l'ordre des cases/répétitions et l'appel target unique par répétition.
Une exception target n'est jamais rappelée pour « faire passer » le case.

```text
EVALUATION_REPETITION_IS_NOT_RUNTIME_RETRY
EVALUATION_REPETITION_IS_NOT_RECOVERY_REPLAY
```

Le runner ne réutilise aucun `RetryPolicy`, `ReplayGuard` ou
`RecoveryCoordinator`.

## 16. Frontières différées

| Scope | Owner futur |
| --- | --- |
| JSON/Markdown/JUnit, comparison, artifacts | F |
| adapters/projections runtime et effets réels | G |
| scénarios pédagogiques STMG/BTS | 12.15 |
| providers, modèles, coûts et calibration | 12.16 |

E ne commence aucun de ces scopes.

```text
RATIONALIZATION = RUNNER_COMPOSES_EXISTING_ASSERTION_AND_SCORING_OWNERS
```
