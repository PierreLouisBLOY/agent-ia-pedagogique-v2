# Baseline Phase 12.11-F — Circuit breaker

## Périmètre livré

Le lot F descend directement du commit E
`cf899415a97aaa314d752725c4287a92a5f71c16` sur
`phase12/12-11-recovery-idempotency`.

Il livre uniquement :

```text
CircuitBreakerKey et circuit_id
+ config et état CLOSED/OPEN/HALF_OPEN
+ failure-window policy
+ CircuitProbeLease atomique
+ CircuitBreakerStorePort
+ CircuitBreakerEngine
+ CircuitBreakerSnapshotRef et fraîcheur STALE_CIRCUIT
```

Il ne livre aucun appel de dépendance, retry/replay effectif, fallback, provider
selection, adapter, store concret, timer, polling ou intégration runtime.

## Clé et routes

La clé est le triplet exact :

```text
CapabilityExecutionRoute + target_id + binding_id
```

Le `binding_id` est opaque et provient d'une composition trusted. Il distingue
deux implémentations/adapters/providers d'une même cible sans exposer leur URL,
import path ou credential. `UTILITY`, `APPLICATION` et `AGENT` sont supportées ;
`RUNTIME` est refusée.

Le circuit n'est pas global par capability. La capability n'entre pas dans la
clé. Le circuit ID est un SHA-256 séparé par domaine sous la forme
`circuit:v1:<digest>`.

## Configuration

La composition doit injecter explicitement :

```text
failure_threshold
failure_window_seconds
open_duration_seconds
half_open_lease_seconds
half_open_success_threshold
```

Toutes les valeurs sont strictement positives. F ne définit aucune valeur
production ni aucun profil provider-specific. Les exemples chiffrés des tests
ne sont pas canoniques ; la calibration reste à la Phase 12.16.

## Classification des failures

Comptées :

```text
TRANSIENT, PROVIDER, TOOL
```

Non comptées :

```text
DOMAIN, PERMISSION, GATE, BUDGET, CANCELLED,
VALIDATION, QUALITY, CONFLICT, UNKNOWN
```

La policy stocke uniquement des `Instant` dans la fenêtre courante, plafonnés
au seuil. Aucune `ErrorEnvelope` complète n'entre dans l'état.

## États

`CLOSED` n'a aucun timestamp open, lease ou succès half-open. Une failure
technique comptée est ajoutée après pruning ; le seuil atteint produit `OPEN`.

`OPEN` possède `opened_at` et `open_until`, sans lease. Un check avant la fin du
cooldown retourne `OPEN_BLOCKED`. La frontière exacte `now == open_until` rend
possible la transition atomique vers half-open ; elle ne ferme jamais
implicitement le circuit.

`HALF_OPEN` autorise un seul probe concurrent. Une lease active retourne
`HALF_OPEN_BUSY`. Une lease absente ou expirée peut être remplacée par un CAS
explicite. L'expiration seule ne modifie aucun compteur et ne signifie jamais
succès.

## Lease et outcomes

`CircuitProbeLease` lie exactement :

```text
circuit + state version + run + step + attempt + acquired/expires
```

Son identifiant est opaque, déterministe et non secret. Un outcome half-open
doit présenter la lease exacte et active. Les mauvais circuit, version, run,
step, attempt ou lease échouent fermés.

Les succès sont séquentiels. Le seuil atteint ferme le circuit et efface
l'historique/lease/compteurs. Une failure technique rouvre immédiatement. Une
failure non technique libère la lease mais ne déclare pas la dépendance malade.

## Absence d'état et CAS

La stratégie retenue est : absence = `CLOSED` conceptuel. Un check ou succès
absent ne crée aucun état. La première failure technique comptée appelle
`create()` atomiquement.

Chaque opération du moteur réalise au maximum :

```text
1 get + 0/1 create
ou
1 get + 0/1 compare_and_set
```

Une course produit explicitement `CIRCUIT_ALREADY_EXISTS` ou
`VERSION_CONFLICT`. Aucun second get, retry CAS ou loop n'est effectué.

## Interlock E

Une décision `RetryDecision.RETRY` ou un replay E éligible reste bloqué si F
retourne `OPEN_BLOCKED`. `CLOSED` indique seulement que l'étage circuit est
satisfait. `HALF_OPEN_PROBE_GRANTED` fournit un candidat unique mais ne lance
pas le probe.

F ne modifie pas les décisions E et ne remplace pas les permissions, gates,
budgets, deadlines ou contrôles snapshot. G composera ces résultats avant toute
exécution.

## Fallback

F ne choisit aucun fallback. Un circuit open ne permet pas de substituer un
provider. Un autre `binding_id` constitue une autre clé et impose une nouvelle
résolution et une nouvelle autorisation complète.

## Snapshots

`CircuitBreakerSnapshotRef` contient seulement `circuit_id` et `version`.
`StateSnapshot.circuit_breaker_refs` est un tuple optionnel par défaut vide,
avec IDs uniques et versions positives.

Une référence présente dans deux snapshots successifs ne peut pas régresser.
Le membership complet du scope circuit n'étant pas représenté, sa persistance
n'est pas imposée en F et reste à traiter en G.

`STALE_CIRCUIT` signale une version snapshot antérieure à l'état courant. Le
snapshot ne stocke aucun status, historique, lease ou config et ne restaure
jamais le circuit. Un restore ne peut donc ni fermer ni réinitialiser un circuit
`OPEN` plus récent.

## Sécurité et frontières

Il n'existe aucun reset manuel, force close/open, compteur caller-controlled,
fallback automatique, provider override, payload, clé d'idempotence brute,
credential ou store mutable production.

F ne contient aucun sleep, polling, tâche asynchrone, réseau, DB, filesystem,
subprocess ou exécution Tool/Application/Agent. `PlanExecutor`, coordinators,
routers, `RunState` et `StepState` restent inchangés.

## Rationalisation

Le CAS B, les références snapshot C, la discipline moteur D et l'interlock E
sont réutilisés conceptuellement sans fusionner leurs responsabilités. Le
circuit health, l'idempotence, les permissions et les poison tasks restent des
frontières distinctes.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Suite

Le prochain lot autorisé après clôture de F est 12.11-G : intégration
recovery/runtime. Aucun travail G n'est inclus ici.
