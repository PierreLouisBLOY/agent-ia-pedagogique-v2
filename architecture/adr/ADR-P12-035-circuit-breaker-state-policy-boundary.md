# ADR-P12-035 — Frontière d'état et de policy du circuit breaker

## Statut

Accepté pour la Phase 12.11-F.

## Contexte

La Phase E produit des décisions de replay/retry qui exigent encore un contrôle
de circuit. Un circuit breaker mesure la santé d'une dépendance technique ; il
ne constitue ni une permission, ni une gate, ni une validation métier, ni une
sélection de provider ou de fallback.

La frontière doit empêcher les nouvelles tentatives vers une implémentation
défaillante et ne laisser passer qu'un seul probe half-open. Elle doit rester
indépendante du runtime jusqu'à l'intégration G.

## Décision

Créer sous `backend/agent_runtime/recovery/` :

```text
CircuitBreakerKey
+ CircuitBreakerPolicyConfig
+ CircuitBreakerState / CircuitProbeLease
+ CircuitBreakerPolicy
+ CircuitBreakerStorePort
+ CircuitBreakerEngine
```

Tous les modèles sont frozen/slotted. La policy est pure. Le moteur effectue au
maximum un `get`, puis un `create` ou un `compare_and_set` par opération
explicite. Il n'existe aucun retry CAS interne.

### Clé technique exacte

La clé contient uniquement :

```text
execution_route + target_id + binding_id
```

`binding_id` est un identifiant opaque fourni par la composition après
résolution de l'implémentation. Il n'est ni un nom choisi par un agent, ni une
URL, un import path, un secret ou un credential. Les identifiants utilisent un
alphabet sûr et borné.

`UTILITY`, `APPLICATION` et `AGENT` sont supportées. `RUNTIME` est refusée. Le
circuit n'est jamais indexé par `CapabilityId`. Deux bindings d'une même cible,
ou deux cibles d'un même binding, produisent des circuits distincts.

L'identifiant est opaque et déterministe :

```text
circuit:v1:<sha256>
```

Le hash est séparé par le domaine
`agent-runtime:circuit-breaker:v1` et encode route, cible et binding avec leurs
longueurs.

### Configuration

`CircuitBreakerPolicyConfig` exige explicitement cinq valeurs strictement
positives : seuil et fenêtre de failures, durée open, durée de lease half-open
et seuil de succès half-open. Aucun baseline chiffré production n'est inventé.
Les valeurs présentes dans les tests ne sont que des exemples locaux. Toute
calibration empirique ou provider-specific reste différée à 12.16.

### États et fenêtre de failures

Le vocabulaire exact est `CLOSED`, `OPEN`, `HALF_OPEN`.

`CircuitBreakerState` conserve circuit/key, version, historique borné de
timestamps, provenance open, lease éventuelle, succès half-open et timestamps
de création/mise à jour. Il ne contient aucune erreur complète, permission,
gate, payload, autorité d'exécution ou donnée provider.

À chaque failure comptée en `CLOSED`, la policy retire les timestamps antérieurs
à `now - failure_window_seconds`, ajoute `now`, puis limite l'historique au
`failure_threshold`. Elle ouvre lorsque le seuil est atteint.

Seules `TRANSIENT`, `PROVIDER` et `TOOL` sont comptées. `DOMAIN`, `PERMISSION`,
`GATE`, `BUDGET`, `CANCELLED`, `VALIDATION`, `QUALITY`, `CONFLICT` et `UNKNOWN`
ne constituent pas par défaut un signal statistique de panne technique.

### Absence d'état

L'absence est un `CLOSED` conceptuel et ne provoque aucune écriture lors d'un
check ou d'un succès. La première failure technique comptée crée l'état par
`create()` atomique. Une course de création échoue explicitement ; le moteur ne
relit pas et ne réessaie pas.

### OPEN et half-open lease

Avant `open_until`, le check retourne `OPEN_BLOCKED`. À
`now >= open_until`, `OPEN -> HALF_OPEN` et l'acquisition du premier lease sont
préparées puis persistées dans un unique CAS.

Une lease est liée au circuit, à la version résultante, au run, au step, à
l'attempt et à ses timestamps. Son ID déterministe et séparé par domaine est :

```text
circuit-lease:v1:<sha256>
```

Une lease active produit `HALF_OPEN_BUSY`. Une lease expirée ne prouve aucun
succès ; elle peut seulement être remplacée lors d'un nouveau CAS explicite.
La version incluse dans l'identité empêche la réutilisation après une transition
ou une réouverture.

### Outcomes half-open

Un succès exige la lease exacte, encore active. Il incrémente le compteur ; le
seuil atteint ferme le circuit, efface le lease, l'historique et les compteurs.
Sinon le circuit reste half-open sans lease pour permettre le prochain probe
séquentiel.

Une failure comptée rouvre immédiatement et recalcule `open_until`. Une failure
non comptée ne déclare pas la dépendance malade : elle consomme uniquement le
probe courant en libérant la lease, puis laisse le circuit half-open.

Le circuit `OPEN` n'accepte aucun outcome, car F n'exécute jamais la dépendance
dans cet état.

### Store et CAS

`CircuitBreakerStorePort` est distinct de `EffectLedgerPort`. Il expose `get`,
`create` atomique et `compare_and_set` versionné. Les clés, circuit IDs,
timestamps de création et versions sont immuables/monotones. F ne fournit aucun
store concret ; le store lock-based reste sous `tests/support`.

Les conflits `create`/CAS échouent fermés et terminent l'opération. Aucun loop,
sleep, polling ou background task n'existe.

### Interaction avec E et fallback

Un `CircuitCheckDecision.CLOSED` signifie seulement que le circuit n'ajoute pas
de blocage. `HALF_OPEN_PROBE_GRANTED` signifie seulement qu'un probe technique
unique est candidat. Les décisions E, les autorités 12.10, le budget, la
deadline et le snapshot courant restent obligatoires.

`OPEN_BLOCKED` ne choisit aucun fallback. Un changement de `binding_id` crée une
nouvelle clé et exige une nouvelle résolution et une nouvelle autorisation hors
F.

### Snapshots

`CircuitBreakerSnapshotRef` contient exclusivement `circuit_id` et `version`.
`StateSnapshot` ajoute un tuple backward-compatible de ces références.

Pour une référence présente dans deux snapshots successifs, la version ne peut
pas régresser. Le scope capturé ne possède pas encore de catalogue exhaustif de
circuits ; F n'impose donc pas la persistance du membership entre snapshots.
Cette garantie de complétude reste différée à G.

La fraîcheur signale `STALE_CIRCUIT` lorsqu'une référence est antérieure à
l'état courant. Le snapshot ne copie ni status, ni historique, ni lease, ni
configuration et ne restaure jamais le store. Un état courant `OPEN` gagne
toujours sur tout snapshot ancien ou implicite.

## Frontières de sécurité

F n'expose aucune opération reset, force-open ou force-close. Il n'accepte
aucun booléen caller-controlled de comptage, d'ouverture ou de passage du
circuit. Les erreurs sont classées par la policy. Les leases, outcomes et
versions doivent correspondre exactement.

F ne traite pas les poison tasks, ne sélectionne aucun provider, n'appelle
aucun tool/use case/agent, ne mute aucun `RunState`/`StepState` et ne modifie ni
`PlanExecutor`, ni coordinator, ni router. L'intégration appartient à G.

## Conséquences

La dernière décision technique pré-runtime est disponible sans créer une
autorité d'exécution. Une seule tentative half-open peut être persistée et tout
conflit concurrent reste visible et fail-closed.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
