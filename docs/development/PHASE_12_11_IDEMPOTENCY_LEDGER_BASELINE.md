# Baseline Phase 12.11-B — Idempotence et effect ledger

## Périmètre livré

Le lot B descend de `main@c708037e5efd5602a64604c70126e8f376d063d5`
sur `phase12/12-11-recovery-idempotency`.

Il livre uniquement :

```text
IdempotencyIdentity et fingerprints
+ EffectLedger lifecycle/reconciliation models
+ EffectAttemptRecord et EffectLedgerRecord
+ IdempotencyPolicy data-only
+ EffectLedgerPort atomique/CAS
```

Il ne livre aucun store de production, retry, replay, reconciliation engine,
snapshot, accounting, backoff, circuit breaker ou intégration runtime.

## Invariants canoniques

L'idempotence empêche une duplication d'effet ; elle ne crée aucune permission.
Le ledger n'est ni une vérité métier, ni une evidence, ni une décision de gate.

L'unique `EffectState` existant est réutilisé. `UNSEEN` signifie absence de
record. Le lifecycle persistant est `RESERVED`, `IN_PROGRESS`, `FINALIZED` et
`ABANDONED`. Le statut de reconciliation séparé est `NOT_REQUIRED`, `PENDING`,
`RESOLVED` et `MANUAL_REQUIRED`.

Transitions B :

```text
absent -> RESERVED
RESERVED -> IN_PROGRESS
RESERVED -> ABANDONED
IN_PROGRESS -> FINALIZED
```

Aucun record finalisé ou abandonné n'est rouvert par B.

## Identité et minimisation

`IdempotencyIdentity` contient principal, run, step, capability, route, target,
operation et les deux fingerprints. Elle ne contient ni attempt, plan version,
payload, provider, import path ou URL.

Les fingerprints sont des SHA-256 lowercase avec domain separation et entrée
bornée. Le caller key digest n'est pas un secret vault. Le record ne conserve
jamais la clé ou l'intention brute.

Le `record_id` dérive de l'identité complète. Le `collision_key` dérive de
principal + run + step + caller key fingerprint, puis compare capability, route,
target, operation et intent fingerprint. Les collisions échouent fermées.

## Record et tentatives

Le record versionné conserve uniquement états techniques, timestamps,
expiration optionnelle, références et codes sûrs. Les tentatives sont contiguës,
commencent à un et ne changent pas l'identité.

`IN_PROGRESS` est conservativement `UNKNOWN/PENDING`. `FINALIZED` signifie fin
de la tentative technique, jamais commit métier. `UNKNOWN` et `PARTIAL` restent
bloqués pour reconciliation. `NONE` peut représenter un échec connu.

## Réservation et CAS

Le port expose `reserve`, `get` et `compare_and_set`. L'implémentation future
doit garantir une réservation atomique et une unicité par collision key. Le
résultat distingue nouvelle réservation, duplicate actif/finalisé, collision,
expiration, abandon et besoin de reconciliation, sans vocabulaire d'autorité.

CAS exige la version courante et produit `version + 1`. Aucun retry interne ou
transaction générique n'est exposé.

Une réservation non démarrée peut être abandonnée explicitement après
expiration. Un `IN_PROGRESS` expiré ne redevient jamais absent ou abandonné ; il
reste potentiellement UNKNOWN.

## Concurrence et frontières

Le fake test-only utilise un lock pour prouver que deux callers concurrents
obtiennent exactement une réservation nouvelle. Aucun store in-memory de
production n'existe.

Le package recovery ne dépend d'aucun provider, réseau, DB, filesystem,
subprocess, thread, ToolCallPolicy, UseCaseRouter, GateEngine, PlanExecutor ou
OrchestrationCoordinator. Les dépendances runtime du projet restent `[]`.

## Rationalisation

Les fingerprints AG-04 sont liés aux snapshots de review et n'ont ni la même
identité, ni le même lifecycle, ni la même frontière d'autorité. Aucun helper
CAS, ledger ou structure d'idempotence partageable n'existait.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Suite

Le prochain lot autorisé après validation et clôture de B est 12.11-C :
`BudgetState`, accounting technique, `StateSnapshot` et store abstrait. Aucun
travail C n'est inclus ici.
