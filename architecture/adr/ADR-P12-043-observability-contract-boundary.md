# ADR-P12-043 — Frontière des contrats d'observabilité

## Statut

Accepté pour la Phase 12.13-B.

## Contexte

La baseline 12.12 fournit déjà des faits de workflow, sécurité, erreur, runtime
et recovery. Elle ne fournit aucun contrat de log, trace, span ou série métrique,
aucun port de livraison et aucun backend d'observabilité. La Phase 12.13-B doit
établir cette frontière sans instrumenter le runtime et sans transformer une
observation en autorité.

L'audit final donne la rationalisation suivante :

| Primitive | Owner | Sémantique | Réutilisation observability candidate | Séparation | Raison |
| --- | --- | --- | --- | --- | --- |
| `WorkflowEvent` | contracts/events | fait de lifecycle workflow | future source de log | oui | statut, résumé et lifecycle propriétaires |
| `SecurityEvent` | contracts/security | fait sécurité minimisé | future source de log ou événement de span | oui | restriction descriptive, jamais backend |
| `ErrorEnvelope` | contracts/errors | erreur d'un attempt | future source de codes/attributs minimisés | oui | message, détails et refs ne sont pas exportables par défaut |
| `ContractMeta.trace_flags` | contracts/common | mapping legacy opaque | donnée de compatibilité seulement | oui | aucune sémantique trace canonique existante |
| `CorrelationId` | Shared Kernel | corrélation fonctionnelle | attribut log/span | oui | ce n'est pas une identité de trace technique |
| `ToolCallResult.metrics` | contracts/tools | mapping résultat Tool | future extraction allowlistée | oui | contenu opaque et potentiellement provider |
| `AgentResult.metrics` | contracts/invocation | mapping résultat Agent | future extraction allowlistée | oui | contenu opaque par invocation |
| `StepState.metrics` | runtime/state | snapshot runtime | future source contrôlée | oui | état runtime, pas série exportable |
| `RetrievalSearchResult.metrics` | agents/evidence | résultat technique d'un canal | future extraction contrôlée | oui | owner retrieval |
| `EvidenceSet.retrieval_metrics` | contracts/evidence | couverture technique Evidence | future extraction contrôlée | oui | métriques fonctionnelles Evidence |
| `BudgetState` | recovery | accounting versionné | future observation dérivée | oui | participe à l'admissibilité recovery |
| `ExecutionDirective` | runtime/execution | contrôle de cycle | futur attribut log/span | oui | autorité runtime existante |

Les critères de consolidation — sémantique, invariants, autorité et lifecycle —
ne sont satisfaits par aucune de ces primitives.

## Décision

### Contrats provider-neutral

Les nouveaux contrats data-only vivent dans :

```text
backend/agent_runtime/contracts/observability/
```

Ils comprennent :

- `TraceId`, `SpanId`, `TraceContext` et `SamplingDecision` ;
- `ObservationCode`, `LogLevel` et `StructuredLogRecord` ;
- `SpanKind`, `SpanStatus` et `SpanRecord` ;
- `MetricName`, `MetricUnit`, `MetricKind`, `MetricLabelSpec`,
  `MetricDescriptor` et `MetricPoint`.

Les records versionnés réutilisent `ContractSchemaVersion`. Aucun système de
versioning telemetry parallèle et aucune nouvelle famille C-01..C-19 ne sont
créés. `TraceId`, `SpanId`, `TraceContext` et les petits vocabulaires restent
des value objects composés par les records versionnés.

### Trace et corrélation

`CorrelationId` reste la corrélation fonctionnelle. `TraceId` et `SpanId`
décrivent la lignée technique d'observabilité. Ils peuvent coexister dans un
record, mais ne sont ni convertibles ni substituables implicitement.

```text
correlation_id
  + trace_id
      + span_id
          + parent_span_id?
```

`TraceContext` ne contient ni baggage, ni trace state, ni mapping libre. Les
identifiants sont opaques, bornés et sans sémantique d'autorité.

`SamplingDecision` contient exactement `DROP`, `RECORD_ONLY` et
`RECORD_AND_SAMPLE`. Elle ne change que la production ou la livraison future
d'observations. Elle ne modifie jamais execution, sécurité, budget, retry,
replay, gate ou effet.

### Coexistence de trace_flags

La stratégie canonique est l'option A :

```text
trace_flags = legacy opaque compatibility data
TraceContext = explicit canonical observability context
```

`ContractMeta` n'importe pas `TraceContext` et n'est pas modifié. Aucune clé de
`trace_flags` n'est interprétée comme `trace_id`, `span_id`, parent ou sampling.
Aucune conversion automatique n'existe. Une migration future exigera un contrat
et un lot explicites.

### Logs et spans

`StructuredLogRecord` est identifié par un `ObservationCode` fermé. Il ne
contient aucun champ `message`. Les attributs sont bornés, récursivement figés et
soumis aux contrôles de valeur 12.12-F ainsi qu'à une interdiction locale des
clés invitant au contenu brut.

`SpanRecord` représente seulement un span terminé. Ses deux timestamps sont
fournis par le caller, en UTC, et la durée ne peut être négative. `SpanStatus.OK`
est un état technique d'observation ; il ne valide aucun fait métier.

`WorkflowEvent`, `SecurityEvent` et `ErrorEnvelope` n'héritent d'aucun record
d'observabilité. Les mappers éventuels sont différés à C/D.

### Métriques et cardinalité

Un `MetricDescriptor` fixe nom, kind, unité, description fermée et au plus huit
labels. Chaque `MetricLabelSpec` fixe non seulement la clé mais l'ensemble fermé
de ses valeurs. Un `MetricPoint` doit fournir exactement ces labels et une valeur
numérique finie.

Les clés dynamiques suivantes sont refusées structurellement : corrélation, run,
step, invocation, délégation, record, trace/span, artefact, Evidence, URL et
chemin. Ces identifiants pourront rester des attributs de logs/spans, jamais des
labels métriques.

### Ports

Trois Protocols distincts vivent dans :

```text
backend/agent_runtime/observability/ports.py
```

- `LogSinkPort.emit(record)` ;
- `TraceSinkPort.emit(record)` ;
- `MetricSinkPort.record(point)`.

La baseline est synchrone, une unité par appel, best-effort, sans résultat de
décision, durabilité, retry, buffering ou backpressure. Aucune implémentation de
production ou in-memory n'est fournie.

## Sécurité des attributs

La frontière réutilise `freeze_agent_safe_mapping` et
`StructuredDataLimits`. Elle ne crée pas un second moteur de safe mapping. Un
profil plus strict borne profondeur, clés, séquences, chaînes et nombre total de
nœuds. Une validation locale refuse prompts, documents, excerpts, contenus,
payloads, outputs, réponses provider, messages/détails d'erreur, stack traces,
clés d'idempotence, chemins privés, secrets et raisonnement privé.

Les refs textuelles doivent être des identifiants opaques. Les URLs et chemins
ne sont pas admis comme refs d'observation.

## Autorité et panne

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
SAMPLING_DECISION_AFFECTS_OBSERVABILITY_ONLY
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

Les ports ne retournent aucune disposition. B n'implémente pas encore
l'isolation des exceptions, le buffering ou les exporters ; ces responsabilités
restent en F/G. Un futur échec de sink ne pourra jamais devenir une permission,
une interdiction métier, une gate, une délégation ou un fait recovery/effect.

## Frontières différées

- C : mapping et logging structuré ;
- D : propagation et tracing ;
- E : catalogue et agrégation metrics ;
- F : exporters, buffering, backpressure et isolation de panne ;
- G : intégration runtime/recovery réelle.

B ne modifie aucun executor, guard, runner, router, coordinator ou controller.
Aucune dépendance runtime n'est ajoutée.

## Conséquences

Les signaux d'observabilité disposent désormais de contrats provider-neutral et
de ports séparés. Le coût assumé est une frontière explicite supplémentaire et
une coexistence temporaire avec `trace_flags`, préférable à une interprétation
silencieuse de données legacy.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
