# ADR-P12-044 — Logging structuré et minimisation par source

## Statut

Accepté pour la Phase 12.13-C.

## Contexte

La baseline 12.13-B fournit `StructuredLogRecord`, ses value objects et le
`LogSinkPort`, sans produire de logs. La Phase 12.13-C doit définir comment des
faits existants deviennent des records provider-neutral, tout en conservant
leurs owners, sans sérialisation générique et sans instrumenter le runtime.

L'audit porte sur douze sources :

| Source | Owner et lifecycle | Source directe C | Champs sûrs candidats | Champs interdits ou différés |
| --- | --- | --- | --- | --- |
| `WorkflowEvent` | contracts/events, lifecycle workflow | oui | type, statut, coordonnées, compte de refs | summary, metrics, `trace_flags` |
| `SecurityEvent` | contracts/security, fait sécurité | oui | type, sévérité, frontière, reason code, coordonnées, compte de refs | metadata brute, contenu, lineage détaillée |
| `ErrorEnvelope` | contracts/errors, erreur d'attempt | oui | code, catégorie, source, retryable, sévérité, état d'effet, action, attempt, step, compte de refs | message, details, refs brutes |
| `ExecutionDirective` | runtime/execution, contrôle runtime | oui | code, reason code, step | state, payload, message, effet d'autorité |
| `PreLaunchDecision` | runtime/execution, décision de lancement | non | ses `SecurityEvent` peuvent être mappés séparément | disposition et assessment portent de l'autorité |
| `CoordinationDecision` | orchestration/coordination, décision d'orchestration | non | aucun en C | `RunState`, actions, raisons et contrôle ; G |
| `RecoveryDecisionResult` | recovery, décision de recovery | non | aucun en C | plan, snapshot, budgets et décisions ; G |
| `ToolCallResult` | contracts/tools, résultat Tool | non | erreur séparée éventuelle | output, metrics, artifacts et assessment opaques |
| `UseCaseResult` | contracts/application, résultat Application | non | erreur séparée éventuelle | outcome, événements métier et contenu opaques |
| `AgentResult` | contracts/invocation, résultat Agent | non | erreur séparée éventuelle | payload, warnings, metrics, refs et stop reason |
| `RunState` | runtime/state, snapshot de run | non | aucun en C | état complet, refs, stop reason et timestamps ; G |
| `StepState` | runtime/state, snapshot de step | non | aucun en C | état complet, metrics, refs et raisons ; G |

La séparation est obligatoire : un mapper d'observation ne devient ni owner du
fait source, ni producteur d'une décision.

## Décision

### Frontière et responsabilité

Les mappers et leur catalogue vivent sous :

```text
backend/agent_runtime/observability/
  log_catalog.py
  log_mapper.py
```

Cette structure évite un package ou une dépendance nommé comme un backend de
logging. Elle reste dans la frontière observability décidée en B.

Les quatre fonctions publiques sont :

```text
structured_log_from_workflow_event
structured_log_from_security_event
structured_log_from_error_envelope
structured_log_from_execution_directive
```

Elles sont pures, déterministes, synchrones et data-only. Elles ne disposent
d'aucun clock, sink, I/O, UUID, hash de payload, exporter ou owner d'autorité.
Les identités et timestamps absents de la source sont fournis explicitement par
le caller. Aucun mapper n'émet lui-même un record.

### Catalogue fermé

`StructuredLogCode` est l'unique vocabulaire de catalogue. Ses valeurs sont
uniques et couvrent uniquement les quatre familles réellement mappées :

| Source | Mapping de code fermé |
| --- | --- |
| chaque `WorkflowEventType` | `WORKFLOW.<EVENT_TYPE>` |
| chaque `SecurityEventType` | `SECURITY.<EVENT_TYPE>` |
| `ErrorEnvelope` | `ERROR.ENVELOPE` |
| chaque `ExecutionDirectiveCode` | `RUNTIME.<DIRECTIVE_CODE>` |

Les correspondances enum vers catalogue sont écrites explicitement. Le
`error_code` métier reste un attribut du fait erreur ; il ne peut pas créer
dynamiquement un `ObservationCode`.

### Niveaux explicites

`SecuritySeverity`, `ErrorSeverity` et `LogLevel` restent trois enums distincts.
Aucun alias n'est créé.

| Source | Mapping vers `LogLevel` |
| --- | --- |
| workflow planned/running/waiting/succeeded | `INFO` |
| workflow replanning/partial/cancelled/escalated | `WARNING` |
| workflow failed | `ERROR` |
| security low/medium/high/critical | `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| error info/warning/error/critical | `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| directive continue | `DEBUG` |
| directive waiting gate/condition required | `INFO` |
| directive denied/retry/replan/escalated/partial/reconciliation | `WARNING` |
| directive stopped/deadlines expirées | `ERROR` |

Chaque membre des enums sources apparaît dans un mapping exhaustif. Il n'existe
aucune heuristique fondée sur une chaîne.

### Minimisation allowlist-first

Chaque mapper construit littéralement son dictionnaire d'attributs :

| Mapper | Attributs admis |
| --- | --- |
| workflow | `event_type`, `workflow_status`, `ref_count` |
| security | `event_type`, `severity`, `boundary`, `reason_code`, `ref_count` |
| error | `error_code`, `category`, `source`, `retryable`, `severity`, `effect_state`, `recommended_action`, `attempt`, `related_ref_count` |
| directive | `directive_code`, `reason_code` si présent |

Les coordonnées déjà top-level — corrélation, run et step — ne sont jamais
dupliquées dans `attributes`. Les refs sont réduites à des comptes ; aucun
contenu de ref n'est copié.

Les exclusions structurantes sont :

```text
WORKFLOW_SUMMARY_IS_NOT_LOG_PAYLOAD_BY_DEFAULT
WORKFLOW_METRICS_ARE_NOT_LOG_ATTRIBUTES_BY_DEFAULT
SECURITY_EVENT_METADATA_IS_NOT_LOG_ATTRIBUTES_BY_DEFAULT
ERROR_MESSAGE_AND_DETAILS_ARE_NOT_LOGGED_BY_DEFAULT
MINIMIZATION_BEFORE_REDACTION
```

Les mappers n'utilisent ni `__dict__`, ni `asdict`, ni JSON générique, ni
`repr(exception)`, ni copie de mapping opaque. Le constructeur B de
`StructuredLogRecord` applique ensuite `freeze_observability_attributes` et les
protections communes 12.12-F. C ne crée aucun second moteur de redaction ou de
value safety.

### TraceContext

Un mapper transmet seulement l'instance `TraceContext` explicitement reçue. Il
ne génère ni trace, ni span enfant, ni sampling. Pour `WorkflowEvent`, le mapping
legacy `ContractMeta.trace_flags` est ignoré, même si ses clés ressemblent à une
trace.

```text
NO_IMPLICIT_CONVERSION
```

La propagation et la création de contexte restent entièrement différées à D.

### Autorité et pannes

Les records sont une projection immutable de faits existants. Ils ne retournent
aucune permission, disposition, transition, retry ou décision recovery. Aucun
mapper n'appelle `ToolCallPolicy`, `UseCaseRouter`, `GateEngine` ou
`RecoveryCoordinator` et aucun mapper ne modifie la source.

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

C n'appelle aucun sink. L'isolation d'un futur échec de livraison relève de F/G
et ne peut pas être implémentée implicitement dans un mapper.

## Alternatives rejetées

- sérialiser les dataclasses sources puis redacter : la donnée interdite aurait
  déjà traversé la frontière ;
- dériver un code de log de `ErrorEnvelope.error_code` : le catalogue ne serait
  plus fermé ;
- mapper directement Tool/Application/Agent results : leurs outputs et metrics
  sont opaques et sans vocabulaire fermé commun ;
- mapper les décisions prelaunch, coordination ou recovery : cela confondrait
  observation et autorité ;
- lire `trace_flags` : aucune sémantique canonique n'existe et D reste différée.

## Frontières différées

- D : création, propagation et lignée de trace ;
- E : catalogue et agrégation métriques ;
- F : exporters, buffering, backpressure et isolation de panne ;
- G : instrumentation réelle du runtime, du routing et du recovery.

Aucun executor, router, coordinator, controller, contrat source ou owner
d'autorité n'est modifié en C. Aucune dépendance runtime n'est ajoutée.

## Conséquences

Le logging structuré dispose d'une projection minimale, testable et indépendante
de tout backend. Le coût assumé est l'écriture explicite de chaque allowlist et
de chaque mapping enum, préférable à une fuite silencieuse de données ou à une
sémantique dynamique.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
