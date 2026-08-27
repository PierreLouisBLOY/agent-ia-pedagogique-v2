# Phase 12.13-B — Baseline des contrats d'observabilité

## 1. Objet

Ce lot établit la frontière provider-neutral :

```text
OBSERVABILITY_CONTRACTS_TRACE_LOG_SPAN_METRIC_SINK_PORTS
```

Il ne contient aucune instrumentation runtime/recovery, aucun exporter et
aucune dépendance telemetry externe.

## 2. Baseline et branche

```text
baseline = main@4aa90f7455c483d1870742976c3c2abe863bb12a
branch = phase12/12-13-observability
```

La branche est créée directement depuis la baseline canonique 12.12.

## 3. Matrice de rationalisation

| Primitive | Owner | Sémantique | Réutilisation candidate | Séparée | Raison |
| --- | --- | --- | --- | --- | --- |
| `WorkflowEvent` | events contracts | lifecycle workflow | source future de log | oui | statut et lifecycle propres |
| `SecurityEvent` | security contracts | fait sécurité minimal | source future de log/span event | oui | data-only, sans backend |
| `ErrorEnvelope` | error contracts | erreur par attempt | codes/attributs minimisés | oui | message/détails non exportés |
| `trace_flags` | `ContractMeta` | compatibilité opaque | aucune conversion | oui | sémantique non définie |
| `CorrelationId` | Shared Kernel | corrélation fonctionnelle | attribut log/span | oui | distinct de TraceId |
| Tool/Agent metrics | result contracts | données de résultat | extraction future allowlistée | oui | mappings opaques |
| Step metrics | runtime state | snapshot technique | extraction future | oui | pas une série métrique |
| Retrieval/Evidence metrics | AG-02/Evidence | couverture technique | extraction future | oui | owner spécialisé |
| `BudgetState` | recovery | accounting versionné | observation dérivée future | oui | admissibilité recovery |
| `ExecutionDirective` | runtime | contrôle de cycle | attribut futur | oui | autorité runtime existante |

## 4. Taxonomie créée

### Trace

```text
TraceId
SpanId
TraceContext(trace_id, span_id, parent_span_id?, sampling_decision)
SamplingDecision = DROP | RECORD_ONLY | RECORD_AND_SAMPLE
```

Il n'existe aucun baggage ou trace state. `CorrelationId` et `TraceId` peuvent
coexister mais ne sont jamais substitués.

### Logging

```text
StructuredLogRecord
LogLevel = DEBUG | INFO | WARNING | ERROR | CRITICAL
ObservationCode
```

Le record ne contient aucun message libre. Il porte uniquement identité,
timestamp, niveau, code, corrélation, coordonnées runtime optionnelles, contexte
de trace optionnel, refs opaques et attributs sûrs.

### Spans

```text
SpanKind = INTERNAL | RUNTIME | AGENT | TOOL | APPLICATION | GATE | RECOVERY
SpanStatus = UNSET | OK | ERROR | CANCELLED
SpanRecord = completed span only
```

Les timestamps sont caller-supplied, UTC, sans clock ni I/O. `OK` n'est jamais
une validation métier.

### Métriques

```text
MetricKind = COUNTER | UP_DOWN_COUNTER | GAUGE | HISTOGRAM
MetricName
MetricUnit
MetricLabelSpec
MetricDescriptor
MetricPoint
```

Le descriptor fixe les clés et toutes les valeurs de labels autorisées. Le
point exige exactement ce schéma et une valeur numérique finie.

## 5. Règles de cardinalité

Sont interdits comme labels : `correlation_id`, `run_id`, `step_id`,
`invocation_id`, `delegation_id`, `record_id`, `trace_id`, `span_id`, refs
artefact/Evidence, URL et chemins.

Les labels admis sont des valeurs fermées courtes, définies par chaque
`MetricLabelSpec`. Un descriptor accepte au plus huit dimensions, chacune au
plus 64 valeurs.

## 6. Safe attributes

Les attributs réutilisent les contrôles 12.12-F et appliquent un profil borné :

```text
depth = 8
mapping keys = 32
sequence items = 64
string length = 512
total nodes = 512
refs = 16
```

Prompts, documents, excerpts, contenu, payloads, outputs, données provider,
messages/détails d'erreur, secrets, stack traces, clés d'idempotence, chemins
privés et raisonnement privé sont refusés.

## 7. trace_flags

Décision canonique : coexistence temporaire option A.

```text
trace_flags = legacy opaque compatibility data
TraceContext = explicit canonical observability context
NO_IMPLICIT_CONVERSION
```

`ContractMeta` reste inchangé et ne dépend pas du package observability.

## 8. Ports

Les trois ports synchrones et provider-neutral sont :

```text
LogSinkPort.emit(StructuredLogRecord) -> None
TraceSinkPort.emit(SpanRecord) -> None
MetricSinkPort.record(MetricPoint) -> None
```

Ils expriment une livraison unitaire best-effort, sans garantie durable, retry,
buffer, backpressure ou résultat d'autorité. Aucune implémentation de production
n'existe en B.

## 9. Frontières et invariants

```text
WorkflowEvent != StructuredLogRecord
SecurityEvent != StructuredLogRecord
ErrorEnvelope != StructuredLogRecord
CorrelationId != TraceId
OBSERVABILITY_NEVER_CREATES_AUTHORITY
SAMPLING_DECISION_AFFECTS_OBSERVABILITY_ONLY
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

Le package contracts ne dépend ni d'infrastructure ni d'un SDK. Les ports
restent sous `backend/agent_runtime/observability/`. Les futurs backends vivront
hors des contracts et seront décidés en F.

## 10. Scopes différés

- C : logging et mappers ;
- D : tracing et propagation ;
- E : métriques ;
- F : exporters et failure isolation ;
- G : instrumentation runtime/recovery.

## 11. Dépendances

```text
[project].dependencies == []
```

Aucun package runtime, SDK provider, OpenTelemetry, Prometheus, structlog ou
backend logging n'est ajouté.

## 12. Validation

Les validations exécutées pour le lot donnent :

```text
new B tests = 71 PASS
targeted + security/common/events + architecture = 855 PASS
global = 3371 PASS
```

Le gate inclut également Python 3.12, Ruff, mypy, compileall et
`git diff --check`. Les résultats terminaux exacts sont consignés dans le
rapport de clôture B.

## 13. Statut de rationalisation

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
