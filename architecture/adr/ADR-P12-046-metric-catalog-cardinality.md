# ADR-P12-046 — Catalogue métrique et cardinalité bornée

## Statut

Accepté pour la Phase 12.13-E.

## Contexte

La Phase 12.13-B fournit les contrats provider-neutral `MetricDescriptor` et
`MetricPoint`, mais aucun catalogue, aucune politique de cardinalité et aucun
mapper de faits existants. Les lots C et D ont établi des mappings purs pour les
logs et la propagation explicite de `TraceContext`. E doit définir les
observations numériques sans installer d'exporter, appeler `MetricSinkPort` ou
instrumenter le runtime et la recovery.

## Audit des propriétaires numériques

| Surface | Owner et sémantique | Faits numériques sûrs | Risque | Décision E |
| --- | --- | --- | --- | --- |
| `BudgetSpec` | contrat de limites déclaratives | plafonds optionnels | confondre limite et consommation | aucun point ; reste une policy input |
| `BudgetState` | recovery, comptabilité canonique d'un run | tokens, coût, durée active, steps, retries, tool calls, complétude | `run_id` et clés step très cardinaux | gauges dérivées, sans ID ni ventilation par step |
| `ToolCallResult.metrics` | mapping opaque fourni par un résultat Tool | aucune clé canonique | noms dynamiques, fournisseur, contenu | aucun export par défaut |
| `AgentResult.metrics` | mapping opaque fourni par un résultat Agent | aucune clé canonique | noms dynamiques, invocation/agent | aucun export par défaut |
| `StepState.metrics` / `StepExecutionResult.metrics` | snapshot runtime opaque | aucune clé canonique | step ID, double comptage | aucun export par défaut |
| `WorkflowEvent.metrics` | mapping event opaque | aucune clé canonique | clés libres et double owner | aucun export par défaut |
| `RetrievalSearchResult` | résultat borné d'un canal | longueur de `candidates`, canal fermé | candidate/source/locator très cardinaux | histogramme du nombre de candidats par canal |
| `RetrievalSearchResult.metrics` | mapping adaptateur opaque | aucune clé garantie | fournisseur et clés libres | aucun export par défaut |
| `EvidenceSet` | résultat canonique Evidence | longueur de `evidence_items` | evidence IDs et provenance | histogramme du nombre matérialisé |
| `EvidenceSet.retrieval_metrics` | résumé actuellement structuré comme mapping | clés connues au call site mais contrat ouvert | dérive de schéma, canaux ou refs | différé ; ne pas parser implicitement |
| `ExecutionCycleResult` | runtime cycle | directives et événements structurés | run/step IDs | mapper les directives, pas les IDs ni collections opaques |
| `ExecutionDirective` | décision runtime fermée | une occurrence par code | reason/step très cardinaux | compteur par code fermé |
| `SecurityEvent` | sécurité, fait immuable | une occurrence, type et sévérité fermés | IDs, reason, refs, metadata | compteur type × sévérité ; boundary différée |
| `ErrorEnvelope` | contrat d'erreur structuré | une occurrence, catégorie/source/sévérité fermées | error code, message, details, step | compteur sur les trois enums fermés |
| `CoordinationDecision` | orchestration, décision canonique | une occurrence par action | reason codes et affected steps | candidat différé pour éviter le double comptage runtime |
| `RecoveryDecisionResult` | recovery coordinator | une occurrence par `RecoveryAction` | snapshot, run, plan et step | compteur par action fermée |
| `RetryDecision` | retry policy | une occurrence par disposition | reason codes, attempt, schedule | compteur par disposition fermée |
| `EffectReconciliationResult` | reconciliation owner | une occurrence par disposition | record ID et versions | compteur par disposition fermée |
| circuit breaker | recovery, état/version/compteurs | status et compteurs structurés | target/binding/circuit IDs ; stale gauge series | candidat différé à F/G |
| snapshot/checkpoint | recovery, état crash-safe | séquence/version/attempt | identités persistées et confusion avec autorité | aucun point E ; candidat d'instrumentation G |

## Rationalisation

Chaque fait conserve son propriétaire. `MetricPoint` est uniquement une
projection dérivée et ne remplace ni `BudgetState`, ni une décision de retry,
replay, reconciliation, gate ou sécurité.

Les mappings `metrics` historiques ne partagent ni schéma fermé ni owner
commun. Les consolider créerait un registre dynamique et donnerait une
sémantique canonique à des données opaques. Le verdict est :

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
DO_NOT_EXPORT_OPAQUE_METRIC_MAPPINGS_BY_DEFAULT
METRIC_POINT_IS_NEVER_A_DECISION_FACT
```

## Décision

### Catalogue canonique

`metric_catalog.py` contient un enum `MetricCode`, un tuple immuable de
`MetricDescriptor` et un lookup en `MappingProxyType`. Aucun descripteur ne
peut être construit depuis une entrée runtime. Les familles retenues sont :

- six snapshots de consommation Budget ;
- événements security et erreurs structurées ;
- directives runtime ;
- volumes de retrieval et Evidence ;
- décisions recovery, retry et reconciliation.

Les noms, kinds, unités, description codes et labels sont donc exhaustifs et
versionnés dans le source. Aucun `UP_DOWN_COUNTER` n'est justifié en E.

### Labels et bornes

Les labels sont exclusivement issus des enums source fermés : complétude,
event type, sévérité, catégorie/source d'erreur, directive, canal, action et
disposition. Les IDs, refs, URL, chemins, codes d'erreur/reason libres, outil,
use case, contenu et fournisseur sont interdits.

L'identité d'une série est exactement :

```text
descriptor.name + labels canoniques triés
```

Le temps et `TraceContext` en sont exclus. La borne théorique d'un descripteur
est le produit des tailles de ses allowlists. Chaque descripteur doit rester à
256 séries au plus et le catalogue complet à 512 séries au plus. Ces deux
limites sont testées ; aucune registry mutable ne compte des séries au runtime.

### Points et valeurs

`metric_policy.py` compose les points par kind et refuse une valeur négative
pour un counter avec un code d'erreur fermé. Les validations B continuent de
refuser booléens, valeurs non numériques/non finies, labels incomplets ou hors
allowlist.

Les consommations `BudgetState` sont des gauges : ce sont des snapshots
cumulatifs détenus par Budget, pas des deltas à sommer à chaque observation.
La complétude tokens/coût reste visible via un label fermé. Aucun step ID ni
run ID n'est copié.

Les comptes de candidats et d'items sont des histogram observations brutes.
E ne définit pas de buckets ni d'accumulateur : leurs choix dépendent du
backend/exporter de F. Ajouter un agrégateur local en E créerait un second
owner, un état mutable et une sémantique de flush prématurée.

### Mappers purs

Chaque mapper reçoit un fait typé, `observed_at` explicite et un
`TraceContext | None`, puis retourne un tuple immuable de `MetricPoint`. Il ne
lit aucune clock, n'effectue aucune I/O et n'appelle aucun sink. Les mappings
opaques ne sont jamais parcourus. La minimisation précède toute redaction : les
champs sensibles ou cardinaux ne sont simplement pas lus.

`TraceContext` est un exemplar optionnel seulement. Il n'est jamais un label et
sa `SamplingDecision` ne contrôle jamais l'existence d'un point :

```text
TRACE_SAMPLING_DOES_NOT_CONTROL_METRIC_COLLECTION
```

## Autorité et neutralité d'échec

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
METRICS_NEVER_CREATE_RECOVERY_OR_BUSINESS_FACTS
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

Un échec de construction reste une erreur locale pure. E ne crée ni
`SecurityEvent`, ni retry, ni mutation Budget/recovery, ni fallback d'autorité.
La future livraison F décidera comment isoler et abandonner une observation
invalide sans modifier l'outcome source.

## Conséquences

Le catalogue est inspectable, déterministe et possède une borne statique. Le
coût assumé est que les métriques opaques Tool/Agent/Step/Workflow et plusieurs
candidats recovery restent invisibles jusqu'à l'existence d'un contrat fermé et
d'un besoin explicite.

## Frontières différées

- F : exporters, buckets/aggregation backend, buffering, backpressure, flush et
  isolation des pannes ;
- G : instrumentation réelle du runtime/recovery et appels aux sinks.

E ne modifie aucun owner source, executor, router, coordinator, contrat de
sécurité ou policy de recovery. Aucune dépendance externe n'est ajoutée.
