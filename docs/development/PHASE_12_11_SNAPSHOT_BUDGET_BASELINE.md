# Baseline Phase 12.11-C — Budget technique et StateSnapshot

## Périmètre livré

Le lot C descend directement du commit B
`24d19c6f1420f847e68a55b1afacf1e84a022ef1` sur la branche
`phase12/12-11-recovery-idempotency`.

Il livre uniquement :

```text
EffectiveBudgetLimits et resolver pur
+ BudgetState, BudgetUsageDelta et BudgetAccountingPolicy
+ BudgetStatePort CAS
+ PlanFingerprint et EffectLedgerSnapshotRef
+ StateSnapshot, freshness et séquence monotone
+ StateSnapshotStorePort CAS
```

Il ne livre aucun store concret, restore runtime, moteur de reconciliation,
probe, retry, replay, backoff, circuit breaker ou intégration d'orchestration.

## Mapping des budgets

Les `BudgetSpec` du plan et du scope sont des enveloppes run-level dans le
resolver C. Leurs limites comparables sont intersectées sans élargissement.
Les plafonds techniques de `AgentRuntimePolicy` restent actifs.

```text
BudgetSpec.max_steps          -> max_steps_per_run
BudgetSpec.max_tool_calls     -> max_tool_calls_per_run
BudgetSpec.max_retries        -> max_retries_per_envelope
RuntimePolicy.max_tool_calls_per_step -> max_tool_calls_per_step
RuntimePolicy.max_retries_per_step    -> max_retries_per_step
```

Les dimensions run/enveloppe et step ne sont jamais fusionnées. Les budgets
attachés à `StepSpec` restent hors du resolver run-level. `None` signifie que la
source n'ajoute aucune limite. La deadline effective est la plus proche.

Le runtime actif est un compteur technique distinct de la deadline absolue. C
ne calcule pas les pauses de gate et ne modifie pas le scheduler.

## Usage et accounting

Tokens et coût ont une complétude explicite : `COMPLETE`, `PARTIAL` ou
`UNKNOWN`. Une métrique indisponible est `None/UNKNOWN`, jamais zéro. Un cap
configuré avec une consommation insuffisamment connue produit `USAGE_UNKNOWN`,
sauf si la borne déjà connue dépasse le cap.

`BudgetState` est immutable et versionné. Les compteurs, Decimal et mappings
par step sont non négatifs. Les totaux tool calls/retries sont dérivés. Un delta
ne peut qu'ajouter de la consommation ; le CAS interdit les versions stale,
les resets, les décréments et l'amélioration artificielle de complétude.

Attempt 1 est l'exécution initiale. Le nombre de retries consommés vaut
`max(0, attempt_count - 1)`, sans intégration automatique à `StepState` en C.

L'évaluation produit exclusivement :

```text
WITHIN_LIMIT
LIMIT_EXCEEDED
USAGE_UNKNOWN
```

`WITHIN_LIMIT` signifie seulement qu'aucune limite technique connue n'est
dépassée. Ce n'est jamais une permission d'exécuter.

## Snapshot technique

`PlanFingerprint` reçoit une représentation canonique du caller et n'invente
aucun serializer de `Plan`. `EffectLedgerSnapshotRef` conserve seulement
`record_id` et `version`, sans dupliquer l'état d'effet.

`StateSnapshot` capture l'exact `RunState`, l'immutable `BudgetState`, les
références ledger versionnées et la version canonique de contrat. Ses
cross-checks exigent des identités run/plan cohérentes, une séquence positive,
des références uniques et des timestamps non futurs.

L'identifiant est déterministe et opaque : `snapshot:v1:<sha256>`. La séquence
commence à 1, avance exactement de un et ne peut écraser un snapshot plus
récent. Une évolution de plan exige une évolution conjointe de version et de
fingerprint. Budget et ledger ne peuvent régresser ou perdre une référence.

L'évaluation de fraîcheur est pure. Elle peut signaler un budget ou ledger plus
récent et un plan différent, mais ne restaure rien. Au futur restore, l'état
budget/ledger plus récent gagne toujours et aucun compteur n'est remis à zéro.

`RunState.context_snapshot_ref` n'est pas ce modèle : il reste une référence de
contexte. Aucun état circuit n'est ajouté avant la Phase F.

## Ports et concurrence

`BudgetStatePort` expose `get` et `compare_and_set`. `StateSnapshotStorePort`
expose `load_latest` et `save` avec séquence précédente attendue. Aucun des deux
n'effectue de retry interne.

Les fakes test-only utilisent des locks pour prouver qu'une seule écriture CAS
concurrente réussit. Aucun store mémoire de production n'existe.

## Autorité et sécurité

Le snapshot et le budget restent des observations techniques. Ils n'accordent
ni permission, ni gate, ni promotion et ne prouvent aucun résultat métier. Une
future reprise devra revalider ledger, gate, scope, budget et circuit via leurs
frontières canoniques.

Aucun payload, secret, credential, clé d'idempotence brute, provider, réseau,
DB, filesystem, subprocess, pickle ou import dynamique n'est introduit. Les
dépendances runtime restent `[]`.

## Rationalisation

Les snapshots de contexte et de review existants n'ont ni la même sémantique,
ni les mêmes invariants, ni le même cycle de vie. Les patterns CAS de B sont
réutilisés conceptuellement, mais leurs erreurs et transitions restent propres
au ledger d'effets. Aucun helper budget/snapshot générique sûr n'existait.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Suite

Le prochain lot autorisé après clôture de C est 12.11-D : reconciliation et
probe ports. Aucun travail D n'est inclus ici.
