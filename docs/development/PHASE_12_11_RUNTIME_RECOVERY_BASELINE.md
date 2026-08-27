# Baseline Phase 12.11-G — Runtime recovery

## Baseline

Le lot G descend directement de F
`be16d44c19db30295a326c39c3d5d7ed36350b8f` sur
`phase12/12-11-recovery-idempotency`.

Il compose les frontières B à F autour du runtime 12.10. `PlanExecutor` reste
inchangé et cycle-only. Aucun retry n'est exécuté dans le même appel public.

## Composants

```text
RecoveryRuntimeResolverPort + RecoveryReferenceResolverPort
RecoveryPreLaunchGuard + RecoveryAwareStepRunner
RecoveryCheckpoint
RecoveryCoordinator + RecoveryRuntimeController
RecoveryCycleResult
RetryFailureFacts
```

Les wrappers conservent un seul `RoutingPreLaunchGuard` et un seul
`RoutingStepRunner`. Le controller appelle une fois `PlanExecutor`, une fois
`OrchestrationCoordinator`, une fois `RecoveryCoordinator` et sauvegarde au
plus un snapshot par cycle.

## Périmètre idempotent

| Route | Cibles baseline | Ledger | Succès |
|---|---|---:|---|
| Utility | T02/T03 | oui, clé caller obligatoire | COMMITTED |
| Application | A02/A03 | oui, clé caller obligatoire | COMMITTED |
| Application | R01/R02/R03/A01 | non | hors ledger |
| Agent | baseline | non, aucune clé synthétique | hors ledger |
| Runtime/GATE/JOIN/DECISION | toutes | non | comportement 12.10 |

L'identité est reconstruite depuis request + descriptor + représentation
canonique trusted. La clé brute est seulement hashée et n'est jamais persistée.

## Lifecycle effect

```text
initial       : reserve -> RESERVED -> IN_PROGRESS -> FINALIZED
retry NONE    : FINALIZED/NONE -> RESERVED -> IN_PROGRESS -> FINALIZED
crash no call : RESERVED expiré -> ABANDONED -> RESERVED explicite
exception     : IN_PROGRESS -> FINALIZED/UNKNOWN/PENDING
```

`RetryFailureFacts` conserve seulement code/catégorie/retryable/action/source.
Le message, details, payload, stack, clé brute et réponse provider restent hors
ledger.

`COMMITTED` interdit le replay mais ne devient jamais SUCCEEDED sans receipt
terminal trusted. La baseline choisit `RESULT_RECOVERY_REQUIRED`.

## Checkpoint, backoff et budget

Un retry sûr produit un checkpoint unique avec record/version, next attempt,
ordinal et `not_before`. Le step passe à PENDING sans modifier son
`attempt_count`. Avant `not_before`, le prelaunch retourne
`CONDITION_REQUIRED`; aucun sleep n'existe.

Le retry budget est consommé au lancement de la nouvelle tentative par un CAS
lié à `attempt - 1`. Le compteur attendu avant lancement est `attempt - 2`.
Tout conflit, usage inconnu, limite atteinte ou deadline expirée bloque.

## Circuit interlock

Le prelaunch inspecte sans écriture. Le runner refait le check et acquiert la
lease half-open exacte. OPEN/BUSY bloque, aucun fallback n'est choisi. Un
changement de binding crée un circuit distinct sans changer l'identité de
l'intention.

## Revalidation

Chaque retry repasse par :

```text
RoutingPreLaunchGuard 12.10
BudgetAccountingPolicy.evaluate
deadline effective
assess_snapshot_freshness
ReplayGuard
RetryPolicy
CircuitBreakerEngine
```

Aucun bool caller-controlled ne peut déclarer permission, gate, budget,
snapshot ou circuit valide.

## Matrice crash/recovery

| Scénario | Résultat G |
|---|---|
| crash avant effet, réservation active | wait/blocked |
| réservation expirée | ABANDONED dans un cycle explicite |
| ABANDONED exact, revalidé | RESUME sans retry consommé |
| crash pendant effet / IN_PROGRESS | RECONCILE |
| exception après appel | UNKNOWN puis RECONCILE |
| probe NOT_COMMITTED | NONE/RESOLVED puis pipeline retry |
| probe COMMITTED | RESULT_RECOVERY_REQUIRED, jamais replay |
| PARTIAL | MANUAL_REQUIRED, jamais retry automatique |
| STILL_UNKNOWN | RECONCILE, jamais retry |
| MANUAL_REQUIRED | MANUAL_REQUIRED |
| résultat ledger avant snapshot | ledger courant gagne |
| snapshot ledger/budget/circuit stale | STOP/block |
| gate expirée ou permission révoquée | STOP/block |
| budget épuisé/inconnu | STOP/block |
| circuit OPEN/BUSY | CONDITION_REQUIRED/no call |
| backoff pending | CONDITION_REQUIRED/no attempt |

## Snapshot membership

Le snapshot capture toutes les références recovery connues du run. Une ref
ledger ou circuit connue ne disparaît pas et sa version ne régresse pas. Une
ref courante absente rend le snapshot stale. Le checkpoint et `not_before`
survivent exactement à un restart.

## Races résiduelles

- prelaunch→runner : le runner refait le circuit check, donc changement = blocage ;
- budget→circuit : le retry lancé peut consommer son unité puis être bloqué ;
- lease→ledger : aucun call si ledger bloque, la lease expire sans faux succès ;
- call→ledger finalize : aucun second call, UNKNOWN/reconciliation ;
- ledger finalize→circuit outcome : ledger connu conservé, conflit remonté ;
- snapshot save : un seul CAS, aucun retry automatique.

## Non-objectifs

Aucun store production, DB, filesystem métier, réseau, provider, queue, worker,
timer, polling, fallback, compensation ou retry loop n'est livré. Aucun agent
métier n'est modifié.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
NEXT_GATE = 12.11-H_READY
```
