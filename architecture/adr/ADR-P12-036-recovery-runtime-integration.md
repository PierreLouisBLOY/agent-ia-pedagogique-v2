# ADR-P12-036 — Intégration runtime recovery déterministe

## Statut

Accepté pour la Phase 12.11-G.

## Contexte

Les lots B à F définissent séparément ledger idempotent, budget, snapshots,
réconciliation, replay/retry/backoff et circuit breaker. G doit les composer
avec le runtime 12.10 sans créer un second executor, une boucle de retry ou une
nouvelle autorité métier.

`PlanExecutor` expose déjà `PreLaunchGuard` et `StepRunner`, produit des
directives fermées et n'exécute qu'un cycle. `OrchestrationCoordinator` traduit
déjà ces directives en `RETRY_REQUIRED` ou `RECONCILIATION_REQUIRED`. Ces points
d'extension sont suffisants : `PlanExecutor` n'est pas modifié.

## Décision

L'intégration est placée autour du cycle :

```text
RecoveryRuntimeController
  -> PlanExecutor.execute_cycle (exactement une fois)
  -> OrchestrationCoordinator.coordinate (exactement une fois)
  -> RecoveryCoordinator.recover (exactement une fois)
  -> StateSnapshotStorePort.save (au plus une fois)
```

Le caller réinvoque explicitement un nouveau cycle. Aucun `while`, sleep,
polling, timer, worker, queue ou scheduler secondaire n'existe.

### Résolution trusted et identité

`RecoveryRuntimeResolverPort` possède trois méthodes distinctes pour tool,
Application et agent. Il retourne uniquement cible exacte, `binding_id` et TTL
de réservation. Il ne décide ni permission, ni gate, ni fallback.

Les wrappers reconstruisent l'identité depuis la requête canonique déjà résolue
par `RuntimeRoutingResolverPort` et les descriptors des registries. La
représentation JSON canonique est typée, récursive, à clés triées et séparée par
domaine via `IntentFingerprint`. Elle n'utilise jamais `repr`, `str(dict)` ou
une valeur fournie par un LLM. La clé caller est seulement transformée en
`IdempotencyKeyFingerprint` ; la clé brute n'entre dans aucun modèle persistant.

Le ledger s'applique uniquement à T02/T03 et A02/A03, dont les descriptors
exigent une clé. R01/R02/R03/A01 et les agents n'obtiennent aucune identité
synthétique. Un changement de binding change le circuit, pas l'identité de
l'intention. Un changement de route, cible, capability ou intention exige un
replan.

### Prélaunch et circuit

`RecoveryPreLaunchGuard` délègue d'abord au `RoutingPreLaunchGuard` canonique et
restitue exactement toute décision non-ALLOW. Il vérifie ensuite le checkpoint
et `not_before`, puis effectue un `CircuitBreakerEngine.inspect` read-only.

Le check read-only ne réserve pas le probe half-open. Le runner appelle ensuite
`CircuitBreakerEngine.check`, qui acquiert la lease par CAS exact au dernier
moment. La race entre les deux lectures est volontaire : un circuit devenu
OPEN/BUSY bloque sans appel. Ce choix évite une lease transmise par mémoire
cachée et empêche deux probes concurrents.

### Ordre du protected call

Pour un lancement recovery :

```text
checkpoint/backoff
-> consommation CAS du retry budget liée à next_attempt
-> circuit check / lease
-> réservation ledger
-> RESERVED -> IN_PROGRESS par CAS
-> un appel exact au RoutingStepRunner
-> finalisation ledger
-> enregistrement outcome circuit
```

Le budget est consommé lorsque `PlanExecutor` a observé le lancement de la
nouvelle tentative. Il exige que le compteur courant soit `attempt - 2`, puis
écrit `attempt - 1` par un seul CAS. Un conflit ou un usage inconnu bloque. Une
course ultérieure peut donc consommer une unité sans appeler la dépendance ;
cette unité reste attachée à la tentative déjà lancée et n'est jamais remise à
zéro ou consommée deux fois.

Le preflight circuit est répété atomiquement par le runner. Une lease half-open
est liée au run/step/attempt exact. Si le ledger bloque ensuite, aucun faux
succès circuit n'est écrit et la lease expire naturellement.

### Ledger, retry facts et succès

`RetryFailureFacts` est la projection persistée unique : code, catégorie,
retryable, action recommandée et source. Message, details, payload et stack ne
sont jamais conservés. La réconciliation préserve exactement cette projection.

Un résultat success T02/T03 ou A02/A03 est finalisé `COMMITTED` avant retour au
runtime. FAILED/CANCELLED/PARTIAL utilisent l'`EffectState` exact de
`ErrorEnvelope`. Une exception après start finalise `UNKNOWN/PENDING` avec un
code fermé avant d'être relancée.

Un conflit de finalisation après appel ne déclenche aucun second appel et laisse
le record `IN_PROGRESS/UNKNOWN`, donc réconciliation obligatoire. Un conflit
d'outcome circuit survient après la finalisation ledger et remonte un signal
fermé ; l'effet connu n'est ni effacé ni converti en NONE.

Une tentative retry explicite effectue `FINALIZED/NONE -> RESERVED ->
IN_PROGRESS` sur le même record et la même identité. Les attempts précédents
restent finalisés et contigus.

### Réservation abandonnée

Une réservation expirée est d'abord transformée `RESERVED -> ABANDONED` dans un
cycle recovery explicite. Une réactivation ultérieure exige : effect NONE,
attempt ledger zéro, identité/record/version exacts, autorité canonique ALLOW,
budget courant, snapshot courant et circuit non bloquant. Elle effectue ensuite
`ABANDONED -> RESERVED` par CAS, renouvelle seulement l'expiration et conserve
record, identité et attempt zéro. Aucun retry budget n'est consommé.

### Coordinator, replay et réconciliation

`RecoveryCoordinator` ne fusionne pas avec `OrchestrationCoordinator`. Pour
`RETRY_REQUIRED`, il relit le record exact, reconstruit `ErrorEnvelope` depuis
les facts sûrs, réévalue le guard 12.10, `BudgetAccountingPolicy`, deadline et
`assess_snapshot_freshness`, puis appelle l'unique `ReplayGuard` et l'unique
`RetryPolicy`.

Une décision RETRY ne lance rien : elle crée un checkpoint, remet seulement le
step concerné à PENDING, nettoie timestamps/résultats d'un effet NONE et garde
`attempt_count`. Le scheduler existant refera PENDING -> READY.

Pour `RECONCILIATION_REQUIRED`, le moteur D est appelé au plus une fois.
STILL_UNKNOWN reste à réconcilier, MANUAL/PARTIAL reste manuel, COMMITTED bloque
tout replay. NONE/RESOLVED peut seulement rejoindre le pipeline retry complet.

`COMMITTED` ne prouve jamais `StepRuntimeStatus.SUCCEEDED`. Sans receipt de
résultat terminal explicite, le résultat est `RESULT_RECOVERY_REQUIRED` et le
step n'est pas promu.

### Snapshot et checkpoint

`StateSnapshot` ajoute un `RecoveryCheckpoint` optionnel et minimal : action,
step, record/version, next attempt, ordinal, `not_before` et codes fermés. Il ne
contient ni erreur complète, scope, gate, payload ou status circuit.

`RecoveryReferenceResolverPort` fournit tous les records du run et tous les
circuits consultés/utilisés. Les références connues ne peuvent plus disparaître
entre deux snapshots et leurs versions ne régressent pas. Une référence
courante absente du snapshot est stale. Ledger, budget et circuit courants
gagnent toujours sur le snapshot.

Chaque récupération significative capture le RunState, BudgetState, les refs
exhaustives et le checkpoint avec sequence +1, puis fait un seul save CAS. Un
conflit termine le cycle sans overwrite ni retry CAS.

## Frontières de sécurité

L'intégration ne sélectionne aucun provider et n'expose aucun fallback. Elle ne
contient aucun adapter DB, réseau, filesystem, cache, queue ou background task.
GATE/JOIN/DECISION restent délégués au runner 12.10 sans ledger/circuit recovery.
L'agent peut être protégé par circuit, mais n'est jamais rejoué automatiquement
sans identité canonique, absente de la baseline.

Les fenêtres non atomiques circuit/ledger/budget sont traitées fail-closed. La
priorité est l'absence de double effet, pas la réparation cachée.

## Conséquences

Le runtime peut reprendre après crash et planifier un retry sans boucle, tout en
préservant les autorités, identities, attempts, budgets et versions existants.
Les stores concrets, timers, schedulers, providers et receipts de résultat
restent hors G.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
