# Baseline Phase 12.11-E — Replay, retry et backoff

## Périmètre livré

Le lot E descend directement du commit D
`cba8f084a76ce720d0b51d0b80fc377e2538cf6a` sur
`phase12/12-11-recovery-idempotency`.

Il livre uniquement :

```text
ReplayPreconditions + ReplayGuard + ReplayGuardDecision
+ RetryPolicyRequest + RetryPolicy + RetryDecision
+ DeterministicBackoffPolicy + RetrySchedule/not_before
```

Ces composants classifient et planifient une éventuelle prochaine tentative.
Ils n'exécutent ni retry ni replay, ne dorment pas, ne mutent aucun état et ne
disposent d'aucun port I/O.

## Définitions canoniques

- `retry` : nouvelle tentative de la même opération avec la même
  `IdempotencyIdentity` exacte ;
- `replay` : reprise soumise à une réévaluation des faits trusted ;
- `replan` : changement d'identité, de capability, route, cible, opération,
  intention ou plan.

La décision E n'accorde aucune autorité métier et ne remplace ni permissions,
ni gates, ni budgets, ni circuit breaker.

## ReplayGuard

La garde exige une égalité complète avec l'identité stockée. Elle consomme des
statuts typés de réévaluation pour permission, gate, budget, deadline et
snapshot. Ces statuts sont des faits fournis par les frontières propriétaires,
pas des calculs locaux ni des booléens libres.

Matrice ledger/effect :

```text
RESERVED                         -> BLOCKED
IN_PROGRESS / UNKNOWN            -> RECONCILE_FIRST
ABANDONED                        -> BLOCKED
FINALIZED / UNKNOWN / PENDING    -> RECONCILE_FIRST
FINALIZED / UNKNOWN / MANUAL     -> MANUAL_REQUIRED
FINALIZED / PARTIAL / PENDING    -> RECONCILE_FIRST
FINALIZED / PARTIAL / RESOLVED   -> BLOCKED
FINALIZED / PARTIAL / MANUAL     -> MANUAL_REQUIRED
FINALIZED / COMMITTED            -> BLOCKED
FINALIZED / NONE / closed        -> évaluation des faits trusted
```

Une identité ou un plan différent produit `REPLAN_REQUIRED`. Permission/gate
invalides, budget dépassé/inconnu, deadline expirée et snapshot stale produisent
`BLOCKED`. Seul le chemin sans anomalie produit `ELIGIBLE`.

Les décisions exposent uniquement disposition, reason codes fermés,
record/version et `requires_circuit_check=True`. Aucun payload, scope, gate,
secret ou résultat provider n'est transporté.

## RetryPolicy

La policy relit les coordonnées exactes de l'erreur et du ledger. Elle utilise
le compteur versionné `BudgetState.retries_by_step[step_id]`; aucun
`current_retry_count` caller-controlled n'existe.

Un retry est possible seulement pour un effet courant `NONE`, une garde
`ELIGIBLE`, une erreur réellement retryable des catégories `TRANSIENT`,
`PROVIDER` ou `TOOL`, et `recommended_action=RETRY`.

Règles fermes :

```text
DOMAIN / PERMISSION / GATE / BUDGET / CANCELLED -> STOP
UNKNOWN                                         -> RECONCILE_FIRST
PARTIAL                                         -> STOP ou ESCALATE
COMMITTED                                       -> NO_RETRY
REPLAN / ESCALATE / STOP / INSPECT              -> disposition conservatrice
```

Les limites envelope, step du budget et step de la policy runtime sont toutes
évaluées dans leur scope d'origine. Une limite à zéro interdit immédiatement
le retry. Un usage inconnu échoue fermé. La policy ne consomme aucune unité de
budget et ne modifie aucun record.

Un résultat `RETRY` fournit `next_attempt`, le `RetrySchedule` et
`not_before`. Toute autre disposition omet ces valeurs.

## Backoff

Le baseline est exponentiel, déterministe, entier, plafonné et sans jitter :

```text
initial_delay_seconds = 1
multiplier = 2
max_delay_seconds = 60
```

L'ordinal de retry commence à 1. Les mêmes inputs produisent le même schedule.
Le cap est exact. `not_before > deadline` produit
`BACKOFF_EXCEEDS_DEADLINE`; `not_before == deadline` reste admissible.

Ce composant calcule un timestamp. Il ne contient aucun sleep, timer, boucle,
thread, tâche asynchrone ou scheduler. Le jitter et la calibration des valeurs
sont explicitement différés à la Phase 12.16.

## Chaînage avec la reconciliation D

Une observation D `NOT_COMMITTED` transforme le record en
`FINALIZED/NONE/RESOLVED`. Le ReplayGuard peut alors l'évaluer puis la
RetryPolicy peut planifier une tentative si les autres faits sont valides.

Une observation `COMMITTED` bloque toujours le replay et le retry. Une
observation `PARTIAL` reste bloquante, même lorsque la reconciliation est
`RESOLVED`.

## Circuit breaker et intégration différés

E ne contient aucun `CircuitBreaker`. Chaque décision de replay et retry porte
un `requires_circuit_check=True` fixe et non contrôlable par le caller. La
Phase 12.11-F évaluera cette condition. La Phase 12.11-G adaptera ensuite le
runtime, sans que E modifie aujourd'hui `PlanExecutor`, `RunState` ou
`StepState`.

E n'ajoute aucun executor, coordinator, adapter provider, store, queue,
compensation, restore snapshot, retry automatique ou exécution de replay. Les
dépendances runtime restent `[]`.

## Rationalisation

La policy historique de `PlanExecutor` reste volontairement inchangée : elle
produit une directive runtime, alors que la frontière E est une classification
pure, indépendante et réutilisable. La déplacer dans E aurait anticipé
l'intégration G et élargi le lot.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Suite

Le prochain lot autorisé après clôture de E est 12.11-F : circuit breaker. Aucun
travail F ou G n'est inclus ici.
