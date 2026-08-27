# ADR-P12-045 — Propagation explicite de TraceContext

## Statut

Accepté pour la Phase 12.13-D.

## Contexte

Les baselines 12.13-B/C fournissent les identités et records d'observabilité,
ainsi que des mappers de logs, sans définir la création ou la propagation d'une
trace. Le runtime contient par ailleurs deux mappings historiques :
`ContractMeta.trace_flags` et `DelegationEnvelope.trace_context`. Leur nom ou
leur contenu ne suffit pas à leur donner la sémantique du `TraceContext` typé B.

D doit établir la lignée canonique tout en restant provider-neutral, pure et
sans instrumentation. Les frontières runtime, routing, recovery, sécurité et
gate ne doivent acquérir ni dépendance observability ni nouvelle autorité.

## Audit trace-like

| Surface | Type actuel | Sémantique et owner | Usage runtime | Legacy | Rôle canonique D | Risque de migration |
| --- | --- | --- | --- | --- | --- | --- |
| `ContractMeta.trace_flags` | `Mapping[str, object]` | metadata contract opaque | copié sans parsing par Tool/Application/Gate routers | oui | aucun ; compatibilité seulement | élevé si interprété |
| `DelegationEnvelope.trace_context` | `Mapping[str, object]` | contexte historique de délégation | aucun call site production ; tests contractuels | oui | aucun ; reste opaque | rupture v1 si retapé/renommé |
| `TraceContext` | value object typé | observability contracts | logs/spans/metrics seulement | non | contexte canonique | faible avec passage explicite |
| `StructuredLogRecord.trace_context` | `TraceContext | None` | record de log B | attachment explicite par C | non | corrélation technique optionnelle | faible |
| `SpanRecord.trace_context` | `TraceContext` | span terminé B | aucune émission runtime | non | lignée obligatoire du span | faible |
| `MetricPoint.trace_context` | `TraceContext | None` | exemplar technique B | aucune agrégation E | non | association optionnelle, jamais label | faible |
| `AgentInvocation` | aucun champ trace typé | invocation attempt contract | routing agent | non | sidecar futur G | élevé si champ ajouté maintenant |
| `DelegationResult` | aucun champ trace | résultat corrélé | sécurité handoff | non | ne modifie jamais la trace | élevé si owner du contexte |
| `ValidatedAgentHandoff` | aucun champ trace | preuve sécurité structurelle | frontière AG-01/spécialiste | non | ne modifie jamais la trace | élevé si authority coupling |
| `WorkflowEvent.meta` | `ContractMeta` | lifecycle workflow | événements existants | indirect | aucun parsing ; log C reçoit un contexte séparé | élevé si conversion |
| Tool request/result | `ContractMeta` + payload/output | appel Tool | routers Tool | indirect | contexte technique sidecar futur G | critique si injecté dans arguments/output |
| Application request/result | `ContractMeta` + payload/outcome | appel inbound Application | router Application | indirect | contexte technique sidecar futur G | critique si injecté dans payload/effect |
| resolved routing inputs | request/invocation + policy facts | décision technique de routing | runtime routing | non | aucune modification D | élevé si trace devient policy fact |
| `RecoveryExecutionContext` | route/binding/idempotence/effect | contrôle recovery | recovery coordinator | non | sidecar futur G | critique si trace change l'effet |
| checkpoint/snapshot/replay | état durable et revalidation | crash/retry authority | recovery | non | aucun champ D | critique si identité de trace devient recovery identity |

## Rationalisation

| Primitive | Owner | Sémantique | Legacy/current | Rôle canonique | Consolider | Décision |
| --- | --- | --- | --- | --- | --- | --- |
| `ContractMeta.trace_flags` | common contracts | mapping opaque | legacy | compatibilité uniquement | non | conserver sans parsing |
| `DelegationEnvelope.trace_context` | planning contracts | mapping historique | legacy | compatibilité uniquement | non | conserver sans parsing |
| `TraceContext` | observability contracts | lignée technique typée | courant | contexte trace canonique | oui, en lui-même | passage explicite |
| log/span/metric trace context | records observability | association à une observation | courant | composer `TraceContext` | non | ne pas déplacer l'owner |
| `CorrelationId` | Shared Kernel | regroupement fonctionnel | courant | coexister top-level | non | aucune conversion |
| invocation/delegation IDs | runtime contracts | identités métier/techniques d'appel | courant | attributs éventuels, jamais TraceId | non | aucune dérivation |

Le verdict est :

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Décision

### TraceContext canonique

`TraceContext` B reste l'unique contexte typé. `CorrelationId`, `TraceId` et
`SpanId` restent trois identités distinctes :

```text
CorrelationId = regroupement fonctionnel ou métier
TraceId = arbre technique d'un logical run
SpanId = opération technique unique dans cet arbre
```

Il n'existe aucune conversion, substitution ou dérivation entre ces identités.
Les IDs sont opaques, caller-supplied, non secrets et ne proviennent jamais de
contenu, de payload, d'un chemin ou d'une entrée utilisateur.

### Scope root

Le scope canonique est une trace par logical run :

```text
TRACE_ID_STABLE_FOR_LOGICAL_RUN
```

Une corrélation peut couvrir plusieurs runs et n'est donc pas le root technique.
Un cycle, step, route, appel ou attempt reçoit un span enfant. Un crash ou
restart du même run conserve le TraceId seulement si le caller a restauré ce
contexte de façon explicite ; D ne le stocke pas.

### Policy pure

`TraceContextPolicy` construit :

- un root avec `trace_id`, `span_id` et `sampling_decision` fournis ;
- un child avec le TraceId du parent, le SpanId parent exact et un nouveau
  `child_span_id` fourni.

La policy ne génère aucun ID, n'accède à aucune clock et ne conserve aucun état.
Elle expose aussi les vérifications locales `same_trace` et `is_direct_child`.
Elle ne prétend pas prouver l'unicité globale des SpanId.

### Sampling

```text
CHILD_SAMPLING_INHERITS_PARENT_EXACTLY
```

`DROP`, `RECORD_ONLY` et `RECORD_AND_SAMPLE` se propagent à l'identique. Cette
décision ne gouverne que la production future de spans. Elle ne peut modifier
logs critiques, metrics, execution, sécurité, gate, budget, retry, replay ou
état d'effet.

### Compatibilité des mappings legacy

```text
NO_IMPLICIT_CONVERSION_FROM_TRACE_FLAGS
NO_IMPLICIT_CONVERSION_FROM_DELEGATION_TRACE_CONTEXT
```

`ContractMeta.trace_flags` reste inchangé. Même des clés `trace_id`, `span_id`
ou `sampled` n'ont aucune sémantique canonique.

La décision pour `DelegationEnvelope.trace_context` est l'option C : sidecar
observability distinct. Le mapping public v1 reste inchangé et opaque. Il n'est
ni retapé, ni renommé, ni copié vers `TraceContext`. Une future intégration G
transportera le `TraceContext` typé comme argument technique explicite à côté de
la délégation, sans l'injecter dans celle-ci.

Cette décision évite une rupture de contrat, un cycle d'import des planning
contracts vers observability et un duplicate owner.

### Propagation par surface

- Agent : AG-01 calcule explicitement le child context de l'invocation avec un
  SpanId fourni ; `DelegationResult` et `AgentResult` ne peuvent pas le changer.
- Tool : le child context voyage hors de `ToolCallRequest.arguments`, comme
  sidecar technique futur G.
- Application : le child context voyage hors de `UseCaseRequest.payload` et de
  `requested_effect`, comme sidecar futur G.
- Gate : un contexte peut décrire un span d'observation mais n'est jamais une
  requirement, un fait ou un critère d'approbation.
- Routing : la trace n'est jamais un `PolicyFact` et ne modifie aucune route.

D n'ajoute aucun de ces sidecars aux surfaces runtime ; il en fixe seulement la
sémantique pour G.

### Retry, recovery et crash

```text
TRACE_ID_STABLE_FOR_LOGICAL_RUN
NEW_SPAN_ID_PER_ATTEMPT
SPAN_ID_NEVER_REUSED_FOR_NEW_ATTEMPT
ATTEMPT_IS_ATTRIBUTE_NOT_TRACE_ID
```

La policy garantit la relation locale parent/enfant. Le caller G devra fournir
un SpanId différent pour chaque nouvelle tentative. D n'ajoute ni registry
global, ni Span store, ni champ trace aux checkpoints/snapshots. Une reprise ne
change aucun invariant d'idempotence, budget, circuit breaker, reconciliation,
replay ou recovery de 12.11.

### Catalogue et span terminé

Un catalogue `SpanCode` distinct de `StructuredLogCode` est créé, car un span
décrit une opération et non un événement de log. Ses codes fermés sont :

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

Ils sont convertis explicitement en `ObservationCode`, value object commun.

`completed_span` compose uniquement un `SpanRecord` B terminé à partir de tous
ses timestamps et champs fournis. Aucun `SpanStart`, clock, sink ou I/O n'est
introduit. `SpanStatus.OK` reste technique et ne signifie ni validation domaine,
ni approbation de gate.

### Privacy et autorité

La factory s'appuie sur la validation B de `SpanRecord`, qui réutilise
`freeze_observability_attributes`. Prompt, payload, output, message/details
d'erreur, Evidence content, réponse provider, secret et chemin privé restent
interdits. TraceId et SpanId ne sont jamais labels métriques.

Aucun contrat D ne contient permission, gate fact, capability, owner, target,
policy facts, effect state ou retry decision.

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
SAMPLING_DECISION_AFFECTS_OBSERVABILITY_ONLY
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

## Conséquences

La propagation devient explicite, déterministe et testable sans global tracer.
Le coût est que G devra passer le contexte séparément à chaque frontière, choix
préférable à une mutation de payload ou à l'interprétation magique des mappings
legacy.

## Frontières différées

- E : catalogue et agrégation metrics ;
- F : exporters, buffering, backpressure et isolation de panne ;
- G : instrumentation réelle, émission vers les sinks et sidecars runtime.

D ne modifie aucun executor, router, coordinator, recovery owner, request
payload ou contrat de sécurité. Aucune dépendance externe n'est ajoutée.
