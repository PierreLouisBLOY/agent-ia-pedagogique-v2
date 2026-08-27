# Phase 12.13-C — Baseline du logging structuré

## 1. Objet

Ce lot construit les mappers purs de logs structurés sur les contrats B :

```text
PURE_SOURCE_MAPPERS_CLOSED_CODES_ALLOWLIST_FIRST_MINIMIZATION
```

Il ne contient aucune émission réelle, instrumentation runtime/recovery,
implémentation de sink, dépendance externe ou modification d'autorité.

## 2. Baseline et branche

```text
parent B = 8227e7612e1884bef9f557e7f86e34255ce56e0a
main = origin/main = 4aa90f7455c483d1870742976c3c2abe863bb12a
branch = phase12/12-13-observability
```

C doit rester un enfant direct de B. Main demeure inchangé.

## 3. Taxonomie des sources

| Source | Owner | Lifecycle | Mapping C | Raison |
| --- | --- | --- | --- | --- |
| `WorkflowEvent` | contracts/events | lifecycle workflow | direct | faits fermés de workflow |
| `SecurityEvent` | contracts/security | fait sécurité | direct | faits sécurité déjà minimisés |
| `ErrorEnvelope` | contracts/errors | erreur d'attempt | direct | allowlist sans message/details |
| `ExecutionDirective` | runtime/execution | contrôle runtime | direct | codes fermés, sans exécution |
| `PreLaunchDecision` | runtime/execution | autorité de lancement | non | mapper ses SecurityEvents séparément |
| `CoordinationDecision` | orchestration | décision de coordination | non | state et autorité, différés à G |
| `RecoveryDecisionResult` | recovery | décision recovery | non | snapshot/budget/effet, différés à G |
| `ToolCallResult` | contracts/tools | résultat Tool | non | output et metrics opaques |
| `UseCaseResult` | contracts/application | résultat métier | non | outcome/contenu/événements opaques |
| `AgentResult` | contracts/invocation | résultat Agent | non | payload/warnings/metrics opaques |
| `RunState` | runtime/state | snapshot run | non | état complet, différé à G |
| `StepState` | runtime/state | snapshot step | non | état complet, différé à G |

Les mappers directs ne deviennent jamais owners de la source. Une erreur portée
par un result peut être donnée séparément au mapper `ErrorEnvelope`; le result
complet n'est pas sérialisé.

## 4. Package et API

```text
backend/agent_runtime/observability/log_catalog.py
backend/agent_runtime/observability/log_mapper.py
```

API publique :

```text
StructuredLogCode
structured_log_from_workflow_event
structured_log_from_security_event
structured_log_from_error_envelope
structured_log_from_execution_directive
workflow_log_level / security_log_level / error_log_level / directive_log_level
```

Les mappers n'ont aucun clock, I/O, sink, backend, UUID, random ou état global.
Un appel avec la même source et les mêmes arguments explicites produit le même
record.

## 5. Catalogue fermé

Le catalogue contient uniquement les familles réellement mappées :

```text
WorkflowEventType          -> WORKFLOW.<EVENT_TYPE>
SecurityEventType          -> SECURITY.<EVENT_TYPE>
ErrorEnvelope              -> ERROR.ENVELOPE
ExecutionDirectiveCode     -> RUNTIME.<DIRECTIVE_CODE>
```

Toutes les correspondances sont exhaustives et écrites explicitement. Le code
d'erreur source reste un attribut ; il ne fabrique jamais un code de catalogue.

## 6. Mapping WorkflowEvent

| Destination | Source |
| --- | --- |
| schema | `meta.schema_version` |
| timestamp | `meta.created_at` |
| corrélation/run/step | `meta` |
| code | mapping fermé de `event_type` |
| niveau | mapping fermé de `meta.status` |
| attributs | `event_type`, `workflow_status`, `ref_count` |

`summary`, `metrics`, `event_id`, les refs brutes et `trace_flags` sont exclus.

## 7. Mapping SecurityEvent

Le mapper réutilise schema, `occurred_at`, corrélation, run et step de la source.
Il projette seulement :

```text
event_type
severity
boundary
reason_code
ref_count
```

`metadata`, content label détaillé, `event_id` et refs brutes sont exclus. Aucun
échec de logging ne crée un nouveau `SecurityEvent`, ce qui interdit toute boucle
SecurityEvent vers log failure vers SecurityEvent.

## 8. Mapping ErrorEnvelope

Le caller fournit `correlation_id`, `run_id`, `occurred_at` et `record_id`. Le
step provient de l'enveloppe. Les attributs sont :

```text
error_code
category
source
retryable
severity
effect_state
recommended_action
attempt
related_ref_count
```

`message`, `details` et les refs elles-mêmes ne franchissent jamais le mapper.

## 9. Mapping ExecutionDirective

Le caller fournit `correlation_id`, `run_id`, `occurred_at`, `record_id` et,
optionnellement, `TraceContext`. Le step reste une coordonnée top-level.

```text
attributes = directive_code + reason_code if present
```

Le mapper observe le contrôle sans le modifier, l'exécuter ni produire une
disposition.

## 10. Niveaux

| Vocabulaire source | Niveau |
| --- | --- |
| workflow planned/running/waiting/succeeded | INFO |
| workflow replanning/partial/cancelled/escalated | WARNING |
| workflow failed | ERROR |
| security low/medium/high/critical | INFO/WARNING/ERROR/CRITICAL |
| error info/warning/error/critical | INFO/WARNING/ERROR/CRITICAL |
| directive continue | DEBUG |
| directive waiting/condition | INFO |
| directive denial/retry/replan/escalation/partial/reconciliation | WARNING |
| directive stopped/deadlines | ERROR |

`SecuritySeverity`, `ErrorSeverity` et `LogLevel` restent distincts. Aucun alias
d'enum et aucune heuristique string-based ne sont introduits.

## 11. Minimisation et safe attributes

```text
MINIMIZATION_BEFORE_REDACTION
```

Les champs sont sélectionnés littéralement avant la création du record. Aucune
utilisation de `source.__dict__`, `asdict`, dump JSON, `repr(exception)` ou copie
d'un mapping opaque n'existe.

`StructuredLogRecord` réutilise ensuite `freeze_observability_attributes`, les
limites B et la value safety 12.12-F. Les attributs sont récursivement immutables.
C n'ajoute aucun moteur concurrent de redaction.

Les identifiants top-level ne sont pas dupliqués dans les attributs. Les refs
sont réduites à des comptes afin de ne jamais exporter un chemin, une URL ou une
référence privée.

## 12. TraceContext et trace_flags

`TraceContext` est uniquement attaché lorsqu'il est fourni explicitement. C ne
le génère pas, ne crée pas de child span et ne définit aucune propagation.

```text
trace_flags = legacy opaque compatibility data
TraceContext = explicit input only
NO_IMPLICIT_CONVERSION
```

## 13. Autorité et immutabilité

Les records B sont frozen/slotted et leurs attributs figés. Les mappers ne
modifient ni source ni state et ne retiennent aucun mapping source opaque.

Ils n'importent ou n'appellent aucun `ToolCallPolicy`, `UseCaseRouter`,
`GateEngine`, `RecoveryCoordinator`, sink ou port d'infrastructure. Ils ne
retournent aucune disposition.

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

## 14. Tests du lot

Les tests C couvrent :

- mapping workflow et exclusion adversariale de summary/metrics/trace_flags ;
- mapping sécurité et exclusion de metadata détaillée ;
- mapping erreur et exclusion de message/details/refs ;
- mapping directive et niveaux exhaustifs ;
- catalogue unique et exhaustif ;
- déterminisme, immutabilité et attachement explicite de trace ;
- fitness d'architecture, absence d'autorité, de sérialisation dynamique,
  d'exporter et d'instrumentation.

Les résultats chiffrés sont consignés après exécution dans le rapport terminal
du lot et ne sont jamais déclarés avant leur exécution réelle.

## 15. Frontières différées

- D : tracing et propagation ;
- E : metrics catalog et agrégation ;
- F : exporters, buffering, backpressure et failure isolation ;
- G : instrumentation runtime/routing/recovery.

## 16. Dépendances

```text
[project].dependencies == []
```

Aucun SDK, framework, provider, backend logging ou package runtime n'est ajouté.

## 17. Rationalisation

Les owners et lifecycles des sources diffèrent de ceux des observations. Une
consolidation créerait soit une fuite de données, soit une confusion d'autorité.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
