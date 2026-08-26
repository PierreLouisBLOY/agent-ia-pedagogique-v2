# ADR-P12-034 — Frontière de replay, retry et backoff

## Statut

Accepté pour la Phase 12.11-E.

## Contexte

Les Phases B à D fournissent une identité d'idempotence exacte, un ledger
versionné, des budgets/snapshots et une reconciliation technique. Elles ne
décident pas si une nouvelle tentative du même effet est admissible. Une
reprise sûre doit distinguer trois notions :

- un `retry` répète exactement la même `IdempotencyIdentity` ;
- un `replay` réévalue une reprise à partir de faits trusted ;
- un `replan` est requis dès que l'identité, la cible, la route, l'opération ou
  le plan change.

Cette décision doit être disponible avant l'intégration runtime G, sans lancer
l'effet, sans modifier `RunState`/`StepState` et sans anticiper le circuit
breaker F.

## Décision

Créer trois policies pures sous `backend/agent_runtime/recovery/` :

```text
ReplayGuard
+ RetryPolicy
+ DeterministicBackoffPolicy
```

Elles reçoivent des objets immuables et retournent uniquement des décisions
data-only. Elles ne disposent d'aucun port, adapter, clock implicite, timer,
thread, tâche asynchrone, boucle de retry ou autorité d'exécution.

### ReplayGuard

`ReplayPreconditions` transporte l'identité demandée et des faits trusted déjà
réévalués : permission, gate, budget, deadline et fraîcheur snapshot. La garde
ne calcule ni permission ni gate et n'accepte aucun booléen caller-controlled
de type `can_replay`.

Les dispositions sont fermées :

```text
ELIGIBLE
RECONCILE_FIRST
REPLAN_REQUIRED
BLOCKED
MANUAL_REQUIRED
```

L'identité doit être strictement égale au record. Tout mismatch produit
`REPLAN_REQUIRED`. `RESERVED` et `ABANDONED` sont bloqués ; `IN_PROGRESS`
demande une reconciliation. Un effet `UNKNOWN` ou `PARTIAL/PENDING` demande
d'abord une reconciliation, et `MANUAL_REQUIRED` reste manuel.
`COMMITTED` et tout `PARTIAL` résolu restent non replayables. Seul un record
`FINALIZED/NONE` avec une reconciliation close peut atteindre l'évaluation des
faits trusted.

Une permission ou gate invalide, un budget dépassé ou inconnu, une deadline
expirée ou un snapshot stale bloque. Un plan mismatch requiert un replan. Les
reason codes sont fermés, ordonnés et dédupliqués.

### RetryPolicy

`RetryPolicyRequest` contient l'`ErrorEnvelope`, le record courant, le
`BudgetState`, le `BudgetCheckResult`, la décision de replay, la policy runtime
et un `Instant` explicite. Aucun compteur libre n'est accepté : le nombre de
retries vient exclusivement de `BudgetState.retries_by_step`, et sa cohérence
avec la lignée d'attempts est vérifiée.

Les dispositions sont :

```text
RETRY
NO_RETRY
RECONCILE_FIRST
REPLAN
STOP
ESCALATE
```

`DOMAIN`, `PERMISSION`, `GATE`, `BUDGET` et `CANCELLED` ne sont jamais
retryables, même si un producer marque l'erreur `retryable=True`. Le baseline
autorise uniquement les catégories techniques `TRANSIENT`, `PROVIDER` et
`TOOL`, avec `recommended_action=RETRY`.

`UNKNOWN` impose `RECONCILE_FIRST`, `PARTIAL` impose stop ou escalade, et
`COMMITTED` produit toujours `NO_RETRY`. Un effet `NONE` ne peut produire
`RETRY` que si la garde est `ELIGIBLE`, les coordonnées record/version/attempt
sont exactes, le budget est connu et dans les limites, chaque limite de retry
laisse une tentative disponible et le backoff tient avant la deadline.

Les scopes restent distincts :

- `max_retries_per_envelope` borne le total du `BudgetState` ;
- `max_retries_per_step` du budget borne le step ;
- `AgentRuntimePolicy.max_retries_per_step` borne aussi le step, avec la limite
  la plus restrictive.

La policy ne consomme pas le budget et ne crée pas un nouvel attempt. Elle
retourne seulement `next_attempt=record.attempt+1` et un schedule potentiel.

### Backoff déterministe

Le baseline utilise un backoff exponentiel entier, borné et sans jitter :

```text
delay(n) = min(initial_delay * multiplier^(n-1), max_delay)
not_before = now + delay(n)
```

L'ordinal commence à 1. Le résultat `RetrySchedule` contient l'ordinal, le
délai et `not_before`. Le composant ne dort jamais et ne planifie aucune tâche.
Un `not_before` strictement postérieur à la deadline refuse le retry ;
l'égalité reste admissible. Les valeurs par défaut sont 1 seconde, facteur 2,
cap 60 secondes. Le jitter et la calibration provider sont différés à la
Phase 12.16.

### Frontière avec le circuit breaker F

E n'implémente aucun circuit breaker et n'accepte aucun état de circuit fourni
par le caller. `ReplayGuardDecision` et `RetryDecision` portent un champ fixe,
non initialisable par le caller :

```text
requires_circuit_check = True
```

Ainsi, une décision E ne peut pas être interprétée comme une autorisation
d'exécution complète. F devra encore décider le circuit, et G composera ensuite
les deux frontières.

## Frontières

E n'ajoute et ne modifie aucun executor, router, coordinator, store, queue,
adapter provider, permission, gate, scheduler, sleep, polling, replay effectif,
retry automatique, compensation ou état runtime. `PlanExecutor` et sa policy
historique restent inchangés ; leur adaptation appartient à G.

Aucune donnée sensible, payload, clé d'idempotence brute, scope, gate, secret,
credential, URL provider ou chemin absolu n'entre dans les décisions.

## Conséquences

La reprise dispose maintenant d'une classification pure et déterministe. Le
runtime pourra demander une décision sans acquérir une autorité métier ni
provoquer un effet. Le futur circuit breaker reste structurellement obligatoire
avant toute exécution.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
