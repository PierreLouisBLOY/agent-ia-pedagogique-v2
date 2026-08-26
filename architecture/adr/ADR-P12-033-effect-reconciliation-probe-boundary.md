# ADR-P12-033 — Frontière de reconciliation des effets

## Statut

Accepté pour la Phase 12.11-D.

## Contexte

La Phase 12.11-B conserve les effets `UNKNOWN` et `PARTIAL` dans un ledger
versionné. La Phase 12.11-C permet à un snapshot d'en référencer une version,
mais ne résout aucun effet. Une future reprise ne peut pas relancer sûrement une
opération tant qu'une observation technique trusted n'a pas été confrontée au
record courant.

La reconciliation observe l'effet ciblé et met à jour le ledger. Elle ne
relance jamais l'opération, n'accorde aucune permission et ne constitue ni une
validation métier, ni une promotion, ni une evidence.

## Décision

Créer deux probes distincts, des requêtes et observations minimales, une policy
pure et un `EffectReconciliationEngine`. Le moteur effectue au plus un appel de
probe et un CAS par cycle explicite de reconciliation.

### Routes et probes

Seules les routes d'effets concrets sont supportées :

```text
CapabilityExecutionRoute.UTILITY     -> ToolEffectProbePort
CapabilityExecutionRoute.APPLICATION -> ApplicationEffectProbePort
```

`AGENT`, `RUNTIME` et toute route future échouent fermées. Aucun probe
universel ou adapter concret n'est créé.

`ToolEffectProbeRequest` nomme le `tool_id` et
`ApplicationEffectProbeRequest` le `use_case_id`. Les deux transportent
uniquement record/version/attempt, principal, run, step, capability, cible,
opération, fingerprint d'intention et références déjà connues. La cible est
toujours dérivée de `IdempotencyIdentity` ; le caller ne peut pas la remplacer.

Aucune requête ne contient payload, clé d'idempotence brute, permission scope,
gate, credential, URL provider ou chemin absolu.

### Observation distincte de l'effet

`ReconciliationObservationDisposition` est distinct de l'unique `EffectState` :

```text
COMMITTED
NOT_COMMITTED
PARTIAL
STILL_UNKNOWN
MANUAL_REQUIRED
```

`NOT_COMMITTED` est une observation qui devient `EffectState.NONE`.
`STILL_UNKNOWN` conserve `EffectState.UNKNOWN`. `MANUAL_REQUIRED` décrit la
suite de la reconciliation et ne crée aucun nouvel état d'effet.

`ReconciliationObservation` contient uniquement l'identité du record, sa
version, l'attempt, la disposition, des `ContractRef`, un `Instant` et un code
fermé optionnel. Elle ne transporte aucune réponse brute. Le moteur vérifie
exactement record ID, version et attempt avant de préparer un remplacement.

### Éligibilité

Les records `FINALIZED/NONE` et `FINALIZED/COMMITTED` sont connus et ne
déclenchent aucun probe. `FINALIZED/UNKNOWN/PENDING` et
`FINALIZED/PARTIAL/PENDING` sont éligibles. Un `PARTIAL/RESOLVED` n'est pas
reprobé automatiquement et reste non replayable. `MANUAL_REQUIRED` ne provoque
aucun probe automatique.

`RESERVED` et `ABANDONED` ne représentent aucun effet à réconcilier. Ils ne
sont jamais rouverts par D.

Un `IN_PROGRESS` dont la lease reste active retourne `RECORD_STILL_ACTIVE`
avant tout probe. Une lease expirée rend le record éligible, sans le faire
redevenir `UNSEEN` ou `ABANDONED`.

### Mapping et transitions

Le mapping est fermé :

```text
COMMITTED       -> COMMITTED / RESOLVED
NOT_COMMITTED   -> NONE      / RESOLVED
PARTIAL         -> PARTIAL   / RESOLVED
STILL_UNKNOWN   -> UNKNOWN   / PENDING
MANUAL_REQUIRED -> UNKNOWN ou PARTIAL préservé / MANUAL_REQUIRED
```

Pour un record `IN_PROGRESS` expiré, l'attempt active est fermée à
`observed_at`, le lifecycle devient `FINALIZED` et aucun nouvel attempt n'est
créé. Pour un record déjà `FINALIZED`, le timestamp de fin de l'attempt reste
inchangé ; seuls l'effet, le statut, les références et la version évoluent.

Les références observées sont ajoutées après les références existantes, avec
ordre stable et déduplication. Une référence connue n'est jamais supprimée.

### Policy, moteur et CAS

`EffectReconciliationPolicy` décide l'éligibilité, revalide l'observation,
applique le mapping et vérifie la transition. Elle n'appelle ni probe ni ledger.

Le pipeline du moteur est strict :

```text
request -> ledger.get -> version exacte -> eligibility
        -> probe typé unique -> anti-forgery -> replacement
        -> compare_and_set unique -> résultat data-only
```

Une version stale est rejetée avant le probe. Une exception de probe devient
`PROBE_FAILED` sans CAS ni nouvel appel. Une course après le probe devient
`LEDGER_VERSION_CONFLICT` ; le record plus récent n'est pas écrasé et le moteur
ne reprobe pas.

Les résultats `NOT_REQUIRED`, `RECONCILED`, `STILL_UNKNOWN`,
`MANUAL_REQUIRED` et `NOT_ELIGIBLE` ne comportent aucune décision de retry ou
replay. La Phase E devra décider séparément de leur admissibilité.

### ApplicationFailure, ToolCallResult et UseCaseResult

Les failures `AF_COMMIT_OUTCOME_UNKNOWN` et `AF_ROLLBACK_FAILED` exposent déjà
`reconciliation_required=True`. D ne modifie pas `ApplicationFailure`. La future
intégration G transformera ces signaux en ledger `UNKNOWN`, puis demandera une
reconciliation Application.

Un ancien `ToolCallResult.output` ou `UseCaseResult.outcome` n'est jamais traité
comme preuve de commit. Seul un futur adapter trusted du probe pourra observer
la cible technique. D ne corrige, ne compense et ne rollback aucun métier.

### Snapshots

D ne restaure aucun `StateSnapshot`. Une référence snapshot `record_id/version`
sert seulement à formuler une requête future. Le moteur relit toujours le
ledger courant ; une version snapshot stale produit `VERSION_MISMATCH` avant le
probe et ne peut écraser l'état courant.

## Frontières

D n'ajoute aucun adapter provider, réseau, DB, filesystem, polling, sleep,
retry, replay, backoff, circuit breaker, compensation, store ou intégration
runtime. `PlanExecutor`, les routers et `OrchestrationCoordinator` restent
inchangés.

## Conséquences

La Phase E pourra raisonner sur un effet techniquement réconcilié sans confondre
observation, autorité métier et droit de replay. `UNKNOWN/PENDING`,
`MANUAL_REQUIRED` et tout `PARTIAL`, même résolu, restent bloquants par défaut.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
