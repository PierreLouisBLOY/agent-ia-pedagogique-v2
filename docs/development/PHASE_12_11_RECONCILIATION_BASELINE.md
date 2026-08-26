# Baseline Phase 12.11-D — Reconciliation des effets

## Périmètre livré

Le lot D descend directement du commit C
`390e378e981d3bfd4636d3167452785fe5491c48` sur
`phase12/12-11-recovery-idempotency`.

Il livre uniquement :

```text
ToolEffectProbePort et ApplicationEffectProbePort
+ requêtes de probe typées
+ ReconciliationObservation
+ EffectReconciliationPolicy
+ EffectReconciliationEngine
+ mise à jour CAS de l'EffectLedgerRecord
```

Il ne livre aucun adapter concret, retry, replay, polling, backoff, circuit,
compensation, restauration snapshot ou intégration runtime.

## Routes supportées

La route `UTILITY` appelle exclusivement `ToolEffectProbePort`. La route
`APPLICATION` appelle exclusivement `ApplicationEffectProbePort`. Les routes
`AGENT` et `RUNTIME` échouent fermées sans appeler de probe.

Il n'existe aucun generic provider probe. Les deux requêtes sont distinctes et
nomment respectivement `tool_id` et `use_case_id`. Tous leurs champs sont
dérivés du ledger ; le caller ne fournit que `record_id` et `expected_version`.

## Observation technique

Le vocabulaire du probe est distinct de `EffectState` :

```text
COMMITTED
NOT_COMMITTED
PARTIAL
STILL_UNKNOWN
MANUAL_REQUIRED
```

L'observation contient l'identité exacte du record/version/attempt, des
références opaques, un timestamp et un code fermé optionnel. Tout mismatch
échoue avant CAS. Elle ne contient ni payload, résultat provider brut, clé,
scope, gate, credential, URL ou path.

Mapping canonique :

```text
COMMITTED       -> EffectState.COMMITTED / RESOLVED
NOT_COMMITTED   -> EffectState.NONE      / RESOLVED
PARTIAL         -> EffectState.PARTIAL   / RESOLVED
STILL_UNKNOWN   -> EffectState.UNKNOWN   / PENDING
MANUAL_REQUIRED -> effet UNKNOWN/PARTIAL préservé / MANUAL_REQUIRED
```

`PARTIAL/RESOLVED` signifie seulement que la portée partielle est techniquement
confirmée. Le record reste replay-blocking pour la Phase E.

## Éligibilité

`FINALIZED/NONE` et `FINALIZED/COMMITTED` ne demandent aucun probe.
`FINALIZED/UNKNOWN/PENDING` et `FINALIZED/PARTIAL/PENDING` sont éligibles.
`PARTIAL/RESOLVED` n'est pas reprobe automatiquement. `MANUAL_REQUIRED` reste
manuel.

`RESERVED` et `ABANDONED` sont non éligibles. Un `IN_PROGRESS` actif retourne
`RECORD_STILL_ACTIVE`. Un `IN_PROGRESS` expiré est réconciliable et son attempt
orpheline est fermée ; il ne redevient jamais absent ou abandonné.

La reconciliation d'un record finalisé ne crée aucun attempt. Les références
existantes sont conservées, puis les nouvelles sont fusionnées dans un ordre
stable sans doublon.

## Pipeline et CAS

Chaque `reconcile()` exécute au maximum :

```text
1 ledger.get
+ 1 probe typé si éligible
+ 1 compare_and_set si l'observation est valide
```

Une requête stale échoue avant probe. Une exception du probe produit
`PROBE_FAILED`, sans mutation ni retry. Une course CAS après le probe produit
`LEDGER_VERSION_CONFLICT`, sans second probe et sans écraser le record gagnant.

La policy est pure et distincte du moteur I/O. Le fake ledger B est réutilisé
avec un validateur CAS injectable uniquement sous `tests/support` ; aucun second
ledger ou store production n'est créé.

## Relations avec les contrats existants

`ApplicationFailure` conserve ses catégories canoniques.
`AF_COMMIT_OUTCOME_UNKNOWN` et `AF_ROLLBACK_FAILED` signalent déjà
`reconciliation_required=True`. La future intégration G utilisera ce signal,
mais D ne modifie pas le contrat et ne tente aucun rollback métier.

`ToolCallResult` et `UseCaseResult` restent data-only. Leurs outputs historiques
ne prouvent pas le commit ; seul un probe trusted futur observe la cible.

Un snapshot C ne déclenche aucune restauration. Son `EffectLedgerSnapshotRef`
peut fournir record/version, mais le ledger courant est toujours relu. Une
version snapshot stale échoue avant probe.

## Autorité et sécurité

Une observation `COMMITTED` confirme techniquement l'effet ciblé. Elle ne
signifie ni succès métier, ni validation, ni promotion, ni evidence, ni droit
de replay. Les résultats de D ne contiennent aucune disposition d'autorité.

Aucun provider, SDK, réseau, DB/ORM, filesystem, subprocess, réflexion,
sérialisation dynamique, polling, sleep, retry/replay ou store mutable de
production n'est introduit. Les dépendances runtime restent `[]`.

## Rationalisation

Les transitions B couvrent la création/finalisation initiale, mais pas une mise
à jour `FINALIZED -> FINALIZED`. La policy D conserve donc ses invariants
propres. Le port et le fake CAS B sont réutilisés ; aucune abstraction de probe
Tool/Application n'est généralisée.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Suite

Le prochain lot autorisé après clôture de D est 12.11-E : `ReplayGuard`, retry
et backoff. Aucun travail E n'est inclus ici.
