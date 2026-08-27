# Phase 12.13 — Baseline métriques et cardinalité

## Portée du lot E

Le lot E établit le catalogue métrique canonique et les projections pures de
faits existants. Il ne livre ni exporter, ni buckets backend, ni buffer, ni
backpressure, ni instrumentation runtime/recovery et n'appelle jamais
`MetricSinkPort`.

Décision canonique :

- [ADR-P12-046](../../architecture/adr/ADR-P12-046-metric-catalog-cardinality.md)

## Baseline Git d'entrée

```text
branch = phase12/12-13-observability
HEAD = d0a225aaf873da0a991f0befc152f686b844d2fd
origin/phase12/12-13-observability = d0a225aaf873da0a991f0befc152f686b844d2fd
main = 4aa90f7455c483d1870742976c3c2abe863bb12a
origin/main = 4aa90f7455c483d1870742976c3c2abe863bb12a
merge-base(main, HEAD) = 4aa90f7455c483d1870742976c3c2abe863bb12a
main...HEAD = 0 3
worktree = clean
```

## Owners et minimisation

Les owners restent inchangés : Budget possède la consommation, Security les
événements, ErrorEnvelope les erreurs, Runtime les directives, Evidence les
résultats matérialisés et Recovery ses décisions. Les `MetricPoint` ne sont que
des observations dérivées.

Les mappings suivants restent opaques et ne sont pas exportés par défaut :

```text
ToolCallResult.metrics
AgentResult.metrics
StepState.metrics
StepExecutionResult.metrics
WorkflowEvent.metrics
RetrievalSearchResult.metrics
EvidenceSet.retrieval_metrics
```

Ils ne sont ni itérés, ni convertis en noms, ni copiés dans des labels. Les
facts sûrs de retrieval/Evidence sont extraits des champs typés et fermés :
`RetrievalSearchResult.channel`, longueur de `candidates` et longueur de
`EvidenceSet.evidence_items`.

## Catalogue canonique

| MetricCode | Kind | Unité | Labels | Borne |
| --- | --- | --- | --- | ---: |
| `BUDGET_CONSUMED_TOKENS` | gauge | tokens | completeness | 3 |
| `BUDGET_CONSUMED_COST` | gauge | currency_units | completeness | 3 |
| `BUDGET_ACTIVE_RUNTIME` | gauge | s | — | 1 |
| `BUDGET_STEPS_STARTED` | gauge | items | — | 1 |
| `BUDGET_RETRIES` | gauge | items | — | 1 |
| `BUDGET_TOOL_CALLS` | gauge | items | — | 1 |
| `SECURITY_EVENTS` | counter | events | event_type × severity | 44 |
| `ERRORS` | counter | errors | category × source × severity | 192 |
| `RUNTIME_DIRECTIVES` | counter | directives | directive | 12 |
| `RETRIEVAL_RESULT_CANDIDATES` | histogram | items | channel | 5 |
| `EVIDENCE_MATERIALIZED_ITEMS` | histogram | items | — | 1 |
| `RECOVERY_DECISIONS` | counter | decisions | action | 10 |
| `RETRY_DECISIONS` | counter | decisions | disposition | 6 |
| `RECONCILIATIONS` | counter | decisions | disposition | 5 |

Le catalogue contient 14 descripteurs et possède une borne totale théorique de
285 séries. La borne par descripteur est 256 ; la borne catalogue est 512.

```text
series identity = descriptor.name + labels triés
observed_at exclu
TraceContext exclu
```

Tous les labels sont des allowlists exactes issues d'enums fermés. Sont
notamment interdits : run/step/correlation/trace/span/invocation/delegation/
record IDs, refs d'artefact ou d'Evidence, URL, chemins, tool/use case IDs,
error/reason codes libres et toute donnée provider ou utilisateur.

## Sémantique des points

- Les Budget totals sont des gauges de snapshot, jamais des counters à sommer.
- Les occurrences security/error/directive/recovery/retry/reconciliation sont
  des counters de delta non négatif.
- Les volumes retrieval/Evidence sont des histogram observations brutes.
- Aucun `UP_DOWN_COUNTER` n'est justifié.
- Les counters négatifs sont refusés par `MetricPointErrorCode.NEGATIVE_COUNTER`.
- Les labels manquants, supplémentaires ou hors allowlist et les valeurs non
  finies restent refusés par les contrats B.

Les buckets et l'agrégation temporelle sont volontairement différés à F : E ne
crée aucun état mutable, accumulator ou sémantique de flush.

## Trace exemplar et sampling

Chaque mapper reçoit `observed_at` et `TraceContext | None` explicitement. Le
contexte est attaché comme exemplar optionnel, jamais comme label. Un contexte
avec `SamplingDecision.DROP` produit exactement les mêmes points qu'un contexte
sampled :

```text
TRACE_SAMPLING_DOES_NOT_CONTROL_METRIC_COLLECTION
```

## Invariants de frontière

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
METRICS_NEVER_CREATE_RECOVERY_OR_BUSINESS_FACTS
METRIC_POINT_IS_NEVER_A_DECISION_FACT
DO_NOT_EXPORT_OPAQUE_METRIC_MAPPINGS_BY_DEFAULT
MINIMIZATION_BEFORE_REDACTION
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

Les packages runtime, recovery, routing, tool et gate n'importent pas
observability. Aucun owner ne lit `MetricPoint`. Aucune dépendance runtime n'est
ajoutée.

## Frontières F et G

- F possède exporters, protocol translation, aggregation/buckets backend,
  buffering, backpressure, flush et isolation des échecs de livraison.
- G possède l'instrumentation réelle, le placement des observations, les
  sidecars de trace et les appels aux sinks.

## Validation normative

Depuis le venv Python 3.12 du dépôt :

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m compileall backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy backend
git diff --check
```

Les tests E couvrent l'unicité et l'immutabilité du catalogue, les bornes de
cardinalité, les labels fermés, les factories par kind, l'identité de série,
les mappers Budget/security/error/runtime/retrieval/Evidence/retry, l'absence
d'export des mappings opaques, le sampling Trace et les frontières
d'autorité/privacy/instrumentation.

Résultats exécutés avant livraison :

```text
tests E ciblés = 15 passed
régression observabilité B/C/D/E = 160 passed
régression Budget/recovery/retrieval/Evidence/security = 490 passed
suite globale = 3460 passed
Python = 3.12.13
compileall backend = PASS
ruff check . = PASS
mypy backend = PASS (607 source files)
git diff --check = PASS
project.dependencies = []
```

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
NEXT_GATE = 12.13-F_READY
```
