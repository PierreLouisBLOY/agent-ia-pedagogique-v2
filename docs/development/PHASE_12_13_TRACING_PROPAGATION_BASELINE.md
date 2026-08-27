# Phase 12.13-D — Baseline tracing et propagation

## 1. Objet

Ce lot établit la sémantique provider-neutral de lignée et de propagation :

```text
EXPLICIT_TRACE_CONTEXT_ROOT_CHILD_LINEAGE_COMPLETED_SPAN
```

D contient uniquement des policies, catalogues et factories purs. Il n'appelle
aucun sink, n'instrumente aucun runtime/recovery et n'ajoute aucun backend ou
dépendance.

## 2. Baseline Git

```text
parent C = 686e22e5c43d168974d67551316cdc06440afa49
main = origin/main = 4aa90f7455c483d1870742976c3c2abe863bb12a
branch = phase12/12-13-observability
```

D doit être un enfant direct de C. Main reste inchangé.

## 3. Audit trace-like

| Surface | Type | Owner et sémantique courante | Runtime | Legacy | Rôle D | Migration |
| --- | --- | --- | --- | --- | --- | --- |
| `ContractMeta.trace_flags` | mapping | common metadata opaque | copié par routers/gate | oui | aucun | conserver, ne jamais parser |
| `DelegationEnvelope.trace_context` | mapping | planning delegation opaque | aucun call site production | oui | aucun | option C sidecar distinct |
| `TraceContext` | value object typé | observability contracts | records B/C | non | contexte canonique | passage explicite |
| log trace context | optionnel typé | structured log | mapper C | non | attachment explicite | inchangé |
| span trace context | requis typé | span terminé | non émis | non | lignée span | inchangé |
| metric trace context | optionnel typé | exemplar technique | non agrégé | non | jamais label | E différée |
| `AgentInvocation` | aucun trace field | attempt Agent | routing | non | sidecar futur | ne pas modifier D |
| `DelegationResult` | aucun trace field | résultat Agent | handoff | non | ne change pas le contexte | ne pas modifier D |
| `ValidatedAgentHandoff` | aucun trace field | preuve sécurité | boundary security | non | aucun owner trace | ne pas modifier D |
| `WorkflowEvent.meta` | `ContractMeta` | lifecycle workflow | events | indirect | aucun parsing | contexte C séparé |
| Tool request/result | meta + arguments/output | appel Tool | router Tool | indirect | sidecar futur | jamais dans payload |
| Application request/result | meta + payload/outcome | inbound Application | router Application | indirect | sidecar futur | jamais dans payload/effect |
| resolved routing inputs | request + policy facts | résolution runtime | routing | non | aucun | trace non autoritaire |
| `RecoveryExecutionContext` | route/binding/effect | recovery execution | coordinator | non | sidecar futur | aucun champ D |
| checkpoints/snapshots/replay | état crash-safe | recovery authority | durable/replay | non | aucun | ne pas coupler à trace |

## 4. Rationalisation

| Primitive | Owner | Sémantique | Legacy/current | Rôle canonique | Consolidation | Décision |
| --- | --- | --- | --- | --- | --- | --- |
| `trace_flags` | common contracts | mapping opaque | legacy | compatibilité | non | aucune conversion |
| delegation `trace_context` | planning contracts | mapping opaque | legacy | compatibilité | non | sidecar typé séparé |
| `TraceContext` | observability | arbre technique | current | contexte canonique | oui, en lui-même | explicit passing |
| record trace contexts | observability records | association observation | current | composer le contexte | non | owners conservés |
| `CorrelationId` | Shared Kernel | groupe fonctionnel | current | top-level distinct | non | aucune conversion |
| invocation/delegation IDs | runtime contracts | identité d'appel | current | attribut éventuel | non | jamais TraceId/SpanId |

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## 5. Scope du root

Le choix canonique est :

```text
TRACE_ID_STABLE_FOR_LOGICAL_RUN
```

Une corrélation peut regrouper plusieurs runs ; elle ne devient pas TraceId. Les
cycles, steps, routes, appels et attempts deviennent de futurs spans enfants.
Un crash/restart garde le TraceId du logical run uniquement si G restaure et
passe explicitement le contexte ; D ne fournit aucun store.

## 6. TraceContextPolicy

```text
root(trace_id, span_id, sampling_decision) -> TraceContext
child(parent, child_span_id) -> TraceContext
same_trace(first, second) -> bool
is_direct_child(parent, child) -> bool
```

Tous les IDs sont fournis par le caller. La policy ne contient aucun état,
clock, random, UUID, ContextVar, threadlocal ou global tracer.

Un child satisfait exactement :

```text
child.trace_id == parent.trace_id
child.parent_span_id == parent.span_id
child.span_id == child_span_id
child.span_id != parent.span_id
```

`same_trace` et `is_direct_child` prouvent uniquement une relation locale. Il
n'existe aucun registry global et D ne prétend pas garantir l'unicité globale
des SpanId.

## 7. Sampling

```text
CHILD_SAMPLING_INHERITS_PARENT_EXACTLY
DROP -> DROP
RECORD_ONLY -> RECORD_ONLY
RECORD_AND_SAMPLE -> RECORD_AND_SAMPLE
```

Le sampling ne gouverne que la production future de spans. Il n'affecte jamais
execution, logs critiques, metrics, sécurité, gate, budget, retry/replay ou état
d'effet.

## 8. Trace continuity et retry

```text
TRACE_ID_STABLE_FOR_LOGICAL_RUN
NEW_SPAN_ID_PER_ATTEMPT
SPAN_ID_NEVER_REUSED_FOR_NEW_ATTEMPT
ATTEMPT_IS_ATTRIBUTE_NOT_TRACE_ID
```

Le caller de G devra fournir un nouveau SpanId à chaque attempt. L'attribut
`attempt` peut être placé dans un span minimisé ; il ne fabrique aucune identité.
Les checkpoints, snapshots et modèles replay restent inchangés.

## 9. Catalogue de spans

`SpanCode` est distinct de `StructuredLogCode` et utilise `ObservationCode`
comme value object fermé commun :

```text
RUNTIME.CYCLE
RUNTIME.STEP
ROUTING.PRELAUNCH
AGENT.INVOCATION
TOOL.CALL
APPLICATION.CALL
GATE.EVALUATION
RECOVERY.CYCLE
RECOVERY.RECONCILIATION
RECOVERY.RETRY
```

Ces dix opérations correspondent aux seules surfaces utiles à la future
instrumentation G.

## 10. Factory de span

`completed_span` exige : contexte, code fermé, kind, status, timestamps début et
fin, corrélation et les coordonnées/attributs optionnels. Elle compose le
`SpanRecord` B avec la version canonique.

La factory :

- ne lit aucune clock ;
- ne génère aucun ID ;
- n'appelle aucun sink ;
- ne conserve aucun état ;
- réutilise les contrôles B via `SpanRecord` et
  `freeze_observability_attributes` ;
- ne crée aucun record in-progress ou `SpanStart`.

`SpanStatus.OK` reste un statut technique. Il ne signifie ni domain validated,
ni gate approved.

## 11. trace_flags

```text
trace_flags = legacy opaque compatibility data
NO_IMPLICIT_CONVERSION_FROM_TRACE_FLAGS
```

Même les mappings contenant `trace_id`, `span_id` ou `sampled` ne deviennent
jamais `TraceContext`. `ContractMeta` reste inchangé et n'importe pas
observability.

## 12. DelegationEnvelope

La décision est l'option C : sidecar observability distinct.

```text
DelegationEnvelope.trace_context = legacy Mapping[str, object]
canonical TraceContext = explicit typed sidecar for future G
NO_IMPLICIT_CONVERSION_FROM_DELEGATION_TRACE_CONTEXT
```

Le champ v1 legacy n'est ni renommé ni retapé. D n'ajoute aucun champ typé à
`DelegationEnvelope`, `AgentInvocation`, `DelegationResult` ou
`ValidatedAgentHandoff`. Cela préserve la compatibilité et évite un cycle
d'import ou un duplicate owner.

## 13. Propagation Agent

AG-01 crée le futur child invocation context en appelant `child` avec un SpanId
fourni. Ce `TraceContext` voyage à côté de la délégation. Il conserve le TraceId
et référence exactement le span parent.

`AgentResult`, `DelegationResult` et le handoff sécurité ne peuvent ni remplacer
ni modifier ce contexte.

## 14. Propagation Tool et Application

Le contexte technique doit voyager comme sidecar explicite futur G :

```text
ToolCallRequest.arguments does not carry tracing
UseCaseRequest.payload does not carry tracing
UseCaseRequest.requested_effect does not carry tracing
```

D ne modifie aucun request/result ou resolved routing input.

## 15. Gate et autorité

Un futur span `GATE.EVALUATION` observe une opération. `TraceContext` ne devient
jamais gate requirement, gate fact ou approval criterion. Il n'est jamais un
`PolicyFact` et ne modifie aucune route.

Les nouveaux helpers ne contiennent permission, capability, owner, target,
effect state, policy fact ou retry decision.

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
SAMPLING_DECISION_AFFECTS_OBSERVABILITY_ONLY
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

## 16. Privacy

TraceId et SpanId sont opaques, bornés, non secrets et caller-supplied. Ils ne
sont dérivés ni d'une entrée utilisateur, ni d'un payload, secret ou chemin et
ne sont jamais des labels métriques.

Les attributs de span refusent prompts, payloads, outputs, messages/details
d'erreur, Evidence content, réponses provider, secrets, stack traces et chemins
privés via les protections B/12.12-F.

## 17. Architecture

```text
backend/agent_runtime/observability/trace_policy.py
backend/agent_runtime/observability/span_catalog.py
backend/agent_runtime/observability/span_factory.py
```

Le package n'importe ni infrastructure, ni exporter, ni sink, ni owner
d'autorité. Aucun executor, router, coordinator, controller ou module recovery
n'importe observability en D.

## 18. Tests du lot

Les tests D couvrent :

- root context et IDs caller-supplied ;
- child lineage exacte ;
- héritage des trois décisions de sampling ;
- continuité locale et attempts distincts ;
- non-conversion de `trace_flags` et du champ delegation legacy ;
- sidecar Agent typé ;
- absence de trace dans les payloads Tool/Application ;
- catalogue fermé et distinct du catalogue de logs ;
- factory déterministe de span terminé ;
- privacy, immutabilité et absence d'autorité ;
- fitness architecture, absence de global tracer et de dépendance.

Les nombres de PASS sont consignés seulement après exécution dans le rapport de
clôture D.

## 19. Frontières différées

- E : metrics catalog et agrégation ;
- F : exporters, buffering, backpressure et failure isolation ;
- G : instrumentation runtime/recovery, sidecars effectifs et appels sinks.

## 20. Dépendances

```text
[project].dependencies == []
```

Aucun SDK provider, OpenTelemetry, backend ou package runtime n'est ajouté.
