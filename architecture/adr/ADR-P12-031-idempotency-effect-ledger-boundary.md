# ADR-P12-031 — Frontière d'idempotence et effect ledger

## Statut

Accepté pour la Phase 12.11-B.

## Contexte

La Phase 12.10 transporte des clés d'idempotence et classe les erreurs avant ou
après effet, mais ne réserve aucune intention et ne persiste aucun état de
déduplication. Un futur retry ne peut donc pas être rendu sûr tant qu'une
frontière atomique ne distingue pas intention, tentative et effet observé.

Cette frontière est technique. Elle ne décide ni permission, ni gate, ni
succès métier et ne constitue pas une source d'evidence.

## Décision

Créer `backend.agent_runtime.recovery` avec des modèles immutables, une policy
pure et un `EffectLedgerPort` provider-neutral.

### Effet et cycles de vie

Le ledger réutilise l'unique `EffectState` : `NONE`, `UNKNOWN`, `COMMITTED` et
`PARTIAL`. Aucun alias `FAILED_KNOWN`, `NOT_COMMITTED` ou `SUCCESS` n'est créé.
Un échec connu est un record finalisé, d'effet `NONE`, avec un code sûr.

`UNSEEN` est l'absence de record, jamais une valeur persistée. Le lifecycle est
fermé : `RESERVED`, `IN_PROGRESS`, `FINALIZED`, `ABANDONED`. B autorise seulement
`RESERVED -> IN_PROGRESS`, `RESERVED -> ABANDONED` et
`IN_PROGRESS -> FINALIZED`.

La reconciliation reste orthogonale avec `NOT_REQUIRED`, `PENDING`, `RESOLVED`
et `MANUAL_REQUIRED`. Un effet `UNKNOWN` n'est jamais implicitement résolu.
`PARTIAL` reste bloqué dans B sans sur-contraindre la future décision D.

### Identité et fingerprints

`IdempotencyIdentity` représente une intention stable : principal, run, step,
capability, route, cible, opération, fingerprint d'intention et fingerprint de
clé caller. `attempt` et `plan_version` sont exclus. Un step sémantiquement
stable peut ainsi conserver son identité après un replan valide.

Les deux fingerprints sont des SHA-256 hexadécimaux lowercase avec domain
separation. Les entrées sont typées, non vides et bornées. Le digest de la clé
caller sert d'identité technique ; il ne transforme pas une clé faible en
secret cryptographique. La clé et le payload bruts ne sont jamais stockés.

Le `record_id` est `effect:v1:<sha256>` sur l'identité complète. Le
`collision_key` est `effect-collision:v1:<sha256>` sur principal, run, step et
fingerprint de clé caller. Une même collision key avec capability, route, cible,
opération ou intention différente échoue fermée.

### Tentatives et record

`EffectAttemptRecord` distingue chaque tentative et conserve uniquement numéro,
timestamps, `EffectState`, références de résultat et code d'erreur sûr.
`EffectLedgerRecord` conserve l'identité, la version CAS, le lifecycle, l'effet,
le statut de reconciliation, les timestamps, l'expiration optionnelle et la
lignée immutable de tentatives. Il ne contient aucun payload, résultat brut,
chemin, prompt, contenu de document ou credential.

`IN_PROGRESS` porte conservativement `EffectState.UNKNOWN` et
`ReconciliationStatus.PENDING`. Cela n'affirme pas qu'un effet a eu lieu ; cela
empêche qu'un crash ou une expiration pendant l'appel soit interprété comme une
absence d'effet.

### Réservation atomique et CAS

`EffectLedgerPort.reserve` doit être atomique. Un seul caller obtient
`RESERVED_NEW`; les autres reçoivent une observation data-only. Le vocabulaire
ne contient aucune disposition d'autorité.

- `RESERVED` ou `IN_PROGRESS` actif : `DUPLICATE_ACTIVE` ;
- `FINALIZED` avec `NONE` ou `COMMITTED` : `DUPLICATE_FINALIZED` ;
- `FINALIZED` avec `UNKNOWN` ou `PARTIAL` : `RECONCILIATION_REQUIRED` ;
- identité incompatible sous la même collision key : `COLLISION` ;
- `ABANDONED` reste bloqué ; aucune nouvelle réservation implicite.

Chaque replacement exige la version courante et produit exactement
`current.version + 1`. Un conflit est explicite et le port n'effectue aucun
retry interne.

Une réservation `RESERVED` expirée peut seulement devenir `ABANDONED` par CAS
explicite. Un record `IN_PROGRESS` expiré reste potentiellement `UNKNOWN` et
demande une future reconciliation ; il ne redevient jamais UNSEEN.

## Frontières

B ne livre aucun store DB/filesystem/in-memory de production, transaction
générique, retry, replay, backoff, snapshot, accounting, circuit breaker,
probe ou moteur de reconciliation. Le fake concurrent avec lock reste sous
`tests/support`.

`IdempotencyPolicy` ne dépend pas de ToolCallPolicy, UseCaseRouter, GateEngine,
PlanExecutor ou OrchestrationCoordinator. Un record n'accorde jamais ALLOW,
REQUEST, DELEGATE ou APPROVED.

## Conséquences

Les lots ultérieurs disposent d'une identité stable, d'une lignée de tentatives
et d'une frontière CAS pour construire snapshots, reconciliation et retry sans
dupliquer les effets. Ils devront toujours revalider permission, gate, budget et
circuit avant toute reprise.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
