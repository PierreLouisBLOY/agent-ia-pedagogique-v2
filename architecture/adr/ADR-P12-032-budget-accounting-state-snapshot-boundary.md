# ADR-P12-032 — Frontière de budget technique et StateSnapshot

## Statut

Accepté pour la Phase 12.11-C.

## Contexte

La Phase 12.11-B établit l'identité idempotente et le ledger d'effets, mais ne
matérialise ni la consommation technique d'un run, ni un checkpoint cohérent
pour une future reprise. Sans modèles versionnés, un futur recovery pourrait
réinitialiser des compteurs, ignorer une mesure inconnue ou écraser un état plus
récent.

Ces informations restent techniques. Elles ne sont ni une permission, ni une
décision de gate, ni une preuve de vérité métier.

## Décision

Étendre `backend.agent_runtime.recovery` avec des modèles immutables, deux
policies pures et deux ports abstraits : `BudgetStatePort` et
`StateSnapshotStorePort`. Aucun store ou moteur de reprise de production n'est
créé.

### Plafonds effectifs et scopes

`EffectiveBudgetLimits` conserve séparément les dimensions run/enveloppe et
step. Le resolver reçoit le `BudgetSpec` du plan, un `BudgetSpec` de scope
optionnel et l'unique `AgentRuntimePolicy`.

Les mappings sont les suivants :

- `max_tokens`, `max_cost`, `max_runtime_seconds`, `deadline`, `max_steps` et
  `max_tool_calls` des budgets plan/scope s'appliquent à l'enveloppe du run ;
- `AgentRuntimePolicy.max_steps_per_run` intersecte uniquement `max_steps` ;
- `default_cost_budget` intersecte uniquement le coût ;
- `run_deadline_default_seconds` reste un plafond de runtime actif ;
- `max_tool_calls_per_step` reste distinct de `max_tool_calls_per_run` ;
- `max_retries` d'enveloppe reste distinct de `max_retries_per_step`.

Une intersection par `min` n'est réalisée qu'entre limites de même dimension
et scope. `None` n'ajoute aucune limite. Les budgets attachés à `StepSpec` ne
sont pas absorbés par ce resolver run-level ; l'intégration G devra les traiter
dans leur propre scope.

### Complétude et accounting

`BudgetMetricCompleteness` distingue `COMPLETE`, `PARTIAL` et `UNKNOWN`. Une
observation manquante porte `None/UNKNOWN`, jamais zéro. Si un cap existe et
que la consommation connue ne suffit pas à prouver le dépassement, le résultat
est `USAGE_UNKNOWN`. Une borne inférieure déjà supérieure au cap produit
`LIMIT_EXCEEDED`, même si la mesure reste partielle.

`BudgetState` conserve des compteurs non négatifs, un coût et un runtime actifs
en `Decimal`, des mappings immutables par step, les complétudes et une version
CAS. Le total tool calls et le total retries sont dérivés des mappings pour
éviter toute divergence. `attempt_count=1` correspond à l'exécution initiale ;
les retries consommés valent `max(0, attempt_count - 1)`. C n'intègre pas
automatiquement `StepState`.

`BudgetUsageDelta` ne contient que des incréments non négatifs. La
`BudgetAccountingPolicy` applique un delta, incrémente exactement la version,
préserve les compteurs et évalue toutes les dimensions. Ses dispositions sont
`WITHIN_LIMIT`, `LIMIT_EXCEEDED` et `USAGE_UNKNOWN` ; aucune n'accorde
l'autorité d'exécuter.

La deadline absolue et le runtime actif restent distincts. C ne calcule pas les
pauses de gate et ne modifie pas le scheduler. L'intégration G alimentera le
runtime actif depuis les événements canoniques.

### BudgetStatePort

Le port expose `get` et `compare_and_set`. La version attendue est obligatoire,
le remplacement doit produire `current.version + 1` et ne peut diminuer aucun
compteur ni restaurer artificiellement une complétude. Il n'effectue aucun
retry interne. Le seul store mémoire avec lock appartient aux tests.

### Fingerprint et références ledger

`PlanFingerprint` calcule un SHA-256 lowercase avec domain separation à partir
d'octets canoniques fournis par le caller. C ne sérialise pas génériquement un
`Plan`. Le fingerprint lie le checkpoint à une représentation exacte sans
remplacer `PlanValidator` et sans constituer une signature d'autorité.

`EffectLedgerSnapshotRef` contient uniquement `record_id` et `version`. Il ne
copie pas `EffectState`. Un futur restore devra relire le ledger courant ; une
version plus récente rend la référence du snapshot stale et ne peut jamais être
écrasée par elle.

### StateSnapshot et monotonicité

`StateSnapshot` réutilise l'unique `RunState`, `BudgetState`,
`ContractSchemaVersion` et `Instant`. Il contient run/plan/version/fingerprint,
la séquence, les références ledger et le timestamp de capture. Son identifiant
opaque `snapshot:v1:<sha256>` dérive de run, plan, version, fingerprint et
séquence.

Le modèle refuse les incohérences de run, plan, version, budget, références
dupliquées et timestamps. `RunState.context_snapshot_ref` n'est pas réutilisé :
il référence un contexte, pas ce checkpoint complet.

`SnapshotSequencePolicy` impose une création en séquence 1, puis exactement
`previous + 1`, avec timestamp non décroissant. Une replanification doit faire
évoluer ensemble plan version et fingerprint. Les versions budget et ledger ne
peuvent pas régresser, et une référence ledger antérieure ne peut disparaître.

`assess_snapshot_freshness` signale `STALE_BUDGET`, `STALE_LEDGER` et
`PLAN_MISMATCH` sans restaurer ni muter aucun état. Le port de snapshot expose
`load_latest` et un `save` CAS par séquence attendue.

## Frontières d'autorité

`RunState` décrit l'état technique du runtime, `StateSnapshot` un checkpoint,
et l'EffectLedger l'observation technique d'effets. Application/Domain reste la
vérité métier. Un run snapshoté `SUCCEEDED` ne prouve aucun commit métier si le
ledger courant indique `UNKNOWN`.

Tout futur restore devra revalider ledger, gates, permission scope, budget et
circuit. C ne livre aucun état circuit, restore runtime, reconciliation, probe,
retry, replay, backoff, I/O ou store concret.

## Conséquences

Les lots D à G pourront comparer des checkpoints à des états techniques plus
récents sans perte monotone. L'intégration devra toutefois repasser par les
policies d'autorité 12.10 avant toute exécution ou reprise.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
