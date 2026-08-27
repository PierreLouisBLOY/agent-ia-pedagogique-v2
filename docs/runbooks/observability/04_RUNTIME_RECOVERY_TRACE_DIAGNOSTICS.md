# Observability — Diagnostics runtime, recovery et traces

## Objet

Ce runbook diagnostique les traces manquantes ou dupliquées et vérifie que
l'instrumentation du runtime/recovery reste non autoritaire, sans appel métier
supplémentaire ni modification des décisions recovery.

## Périmètre

Le périmètre couvre la composition des wrappers prelaunch, step, controller et
recovery, le contexte de trace explicite, le sampling, les providers d'ID/temps
observability et les projections logs/spans/métriques. Le runtime, les routes,
la sécurité et recovery conservent leurs owners canoniques.

## Call graph canonique

```text
schedule
-> prelaunch
-> route/effect
-> ExecutionCycleResult
-> coordination
-> recovery
-> snapshot
```

Chaque wrapper appelle son inner exactement une fois. L'instrumentation ne
rappelle aucune source pour reconstruire une observation.

## Invariants

```text
TRACE_ID_STABLE_FOR_LOGICAL_RUN
NEW_SPAN_ID_PER_ATTEMPT
CHILD_SAMPLING_INHERITS_PARENT_EXACTLY
ONE_SECURITY_EVENT_OBSERVATION_PER_RUNTIME_EVENT
OBSERVABILITY_CONFIGURATION_DOES_NOT_CHANGE_RUNTIME_OUTCOME
```

Le contexte de trace est un sidecar hors payload, `RunState`, snapshot, ledger,
budget et identité idempotente. Après crash/restart, la continuité n'existe que
si le root est restauré explicitement par le caller.

## Triggers et symptômes

- span attendu absent ou dupliqué ;
- TraceId différent au sein d'un même logical run ;
- SpanId réutilisé entre tentatives ;
- sampling enfant différent du parent ;
- `SecurityEvent` observé plusieurs fois ;
- appel Tool/Application/Agent, effect ou probe dupliqué ;
- résultat runtime/recovery différent selon la santé telemetry ;
- trace présente dans `RunState`, snapshot ou ledger.

## Données sûres à examiner

Examiner les IDs opaques du contrat trace, `SamplingDecision`, codes/kinds/
status fermés, timestamps observability, compteurs d'appels synthétiques, codes
d'événements et égalité structurelle des résultats. Ne pas examiner payload,
output, prompt, private reasoning, metadata security brute ou erreur brute.

## Règles de trace

```text
TRACE_ID_STABLE_FOR_LOGICAL_RUN
NEW_SPAN_ID_PER_ATTEMPT
CHILD_SAMPLING_INHERITS_PARENT_EXACTLY
```

Le root est caller-owned. Chaque enfant reprend exactement le TraceId et le
sampling du parent, reçoit un nouveau SpanId et référence le SpanId parent. Les
mappings legacy ne sont pas une source de contexte.

## Diagnostic d'un span manquant

Vérifier dans cet ordre :

1. `SamplingDecision` du parent ;
2. le provider d'IDs observability ;
3. la clock observability ;
4. la composition du wrapper attendu ;
5. le health du channel span ;
6. serializer, buffer et delivery.

Un provider d'ID ou une clock en exception abandonne l'observation mais ne doit
pas altérer le runtime. Il est interdit de rejouer un effet métier uniquement
pour reconstruire un span.

## Diagnostic d'un span dupliqué

Vérifier l'owner unique de chaque émission :

- prelaunch wrapper : `ROUTING.PRELAUNCH` et éventuelle gate prelaunch ;
- step wrapper : `RUNTIME.STEP` et route Tool/Application/Agent/Gate ;
- controller wrapper : cycle, `SecurityEvent` et directive ;
- recovery wrapper : cycle, décision recovery et spans retry/reconciliation
  seulement lorsqu'ils existent réellement.

Vérifier que la composition n'a pas instrumenté deux fois un même composant.
Il n'existe aucun ledger/replay telemetry : une observation perdue n'est pas
reconstruite après crash.

## SecurityEvent

```text
ONE_SECURITY_EVENT_OBSERVATION_PER_RUNTIME_EVENT
```

Le controller observe chaque élément de `ExecutionCycleResult.security_events`
une fois. Prelaunch, runner, delivery et recovery ne doivent pas synthétiser ou
réémettre le même événement.

## Sampling DROP

`DROP` supprime uniquement les spans. Logs, métriques, `SecurityEvent` et
résultat runtime/recovery restent inchangés. `RECORD_ONLY` et
`RECORD_AND_SAMPLE` produisent les spans locaux ; leur distinction future côté
exporter reste hors scope.

## Recovery

Les règles canoniques restent exactement :

```text
UNKNOWN -> reconcile before replay
PARTIAL -> never auto retry
COMMITTED -> never replay
NONE -> only potentially retryable
COMMITTED != SUCCEEDED without trusted terminal receipt
no synthetic idempotency identity
no retry loop
snapshot/budget/ledger/circuit monotone
recovery technical-only
```

Telemetry ne peut jamais déclencher un retry, modifier `EffectState`, écrire un
snapshot, modifier `BudgetState`, ou modifier `ReplayGuard`/`CircuitBreaker`.
Elle projette uniquement la décision déjà obtenue.

## Outcome equivalence

Comparer l'égalité structurelle complète du résultat dans quatre configurations
minimum :

- telemetry disabled ;
- telemetry healthy ;
- sinks/providers raising ;
- telemetry saturated.

Comparer `RecoveryCycleResult`, run state, steps lancés/terminés, directives,
security events, coordination, action recovery, budget, snapshot, retry et
reconciliation. Comparer aussi les call counts effect/probe.

## Procédure de diagnostic

1. Reproduire avec providers déterministes et données synthétiques.
2. Capturer le résultat sans observability comme baseline.
3. Rejouer les quatre configurations telemetry sans changer les entrées.
4. Comparer structure complète et call counts.
5. Pour une divergence de span, suivre l'ordre span manquant/dupliqué.
6. Pour une divergence recovery, arrêter l'analyse telemetry et vérifier les
   owners 12.11 sans modifier leurs décisions.
7. Confirmer qu'aucun état trace n'entre dans les objets persistables.

## Actions autorisées

- remplacer sink, ID provider ou clock injectés par des fakes déterministes ;
- désactiver un canal par composition ;
- inspecter codes, IDs opaques, sampling, timestamps et call counts ;
- exécuter les tests d'équivalence et d'architecture ;
- ouvrir un lot correctif séparé si la composition est erronée.

## Actions interdites

- rejouer un effet pour produire une trace ;
- rappeler route, policy, source ou recovery pour enrichir une observation ;
- persister le contexte dans `RunState`, snapshot, ledger ou idempotency ;
- déclencher retry/reconciliation depuis telemetry ;
- modifier budget, effect state, replay guard ou circuit breaker ;
- créer un ledger ou replay telemetry ;
- interpréter les mappings legacy comme contexte canonique.

## Tests de vérification

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_trace_context_policy.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_runtime_observability_wrappers.py
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_runtime_observability_integration.py
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_runtime_observability_recovery.py
.\.venv\Scripts\python.exe -m pytest -q tests/architecture/test_runtime_observability_integration_fitness.py
```

## Critères de retour à la normale

- TraceId stable pour le logical run et nouveau SpanId par tentative ;
- sampling enfant identique au parent ;
- owners uniques et aucun span/`SecurityEvent` dupliqué ;
- call counts métier/effect/probe identiques à la baseline ;
- résultats disabled/healthy/raising/saturated structurellement égaux ;
- aucun état trace dans runtime/recovery persistant.

## Critères d'escalade

STOP si un business output diffère selon telemetry, si un effet externe ou un
probe/recovery est doublé, si la trace pollue `RunState`/snapshot, si un
`SecurityEvent` est dupliqué, ou si telemetry modifie une règle recovery.

## Références techniques

- [ADR-P12-045](../../../architecture/adr/ADR-P12-045-trace-context-propagation.md)
- [ADR-P12-048](../../../architecture/adr/ADR-P12-048-runtime-recovery-observability-integration.md)
- [Baseline trace](../../development/PHASE_12_13_TRACING_PROPAGATION_BASELINE.md)
- [Baseline runtime](../../development/PHASE_12_13_RUNTIME_OBSERVABILITY_INTEGRATION_BASELINE.md)
- [Trace policy](../../../backend/agent_runtime/observability/trace_policy.py)
- [Runtime context](../../../backend/agent_runtime/observability/runtime_context.py)
- [Runtime emitter](../../../backend/agent_runtime/observability/runtime_emitter.py)
- [Runtime wrappers](../../../backend/agent_runtime/observability/runtime_wrappers.py)
