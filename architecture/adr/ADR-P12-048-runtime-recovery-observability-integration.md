# ADR-P12-048 — Intégration observability runtime et recovery

## Statut

Accepté pour la Phase 12.13-G.

## Contexte

Les lots B à F ont fermé les contrats log/span/metric, les mappers minimisés,
la propagation de trace explicite, le catalogue métrique borné et les sinks
failure-isolated. Aucun chemin runtime ou recovery ne les appelait. G doit
observer les appels canoniques sans déplacer l'autorité, rappeler une source ou
modifier les résultats structuraux.

## Audit du call graph

Le cycle réel est :

```text
RecoveryRuntimeController.execute_cycle
  -> PlanExecutor.execute_cycle
       -> DeterministicScheduler.schedule
       -> PreLaunchGuard.check, une fois par candidat visité
            -> résolution + gate/policy/security canoniques
       -> StepRunner.run, une fois par step lancé
            -> RoutingStepRunner
                 -> ToolRouter.route | UseCaseRouter.route
                    | AgentStepRouter.route | GateEngine.evaluate
  -> OrchestrationCoordinator.coordinate, une fois
  -> RecoveryCoordinator.recover, une fois
       -> budget courant
       -> reconciliation uniquement si exigée et éligible
       -> retry policy uniquement après effect fact NONE
       -> checkpoint/snapshot
```

`ExecutionCycleResult` est l'owner des `SecurityEvent` et directives retenus.
Le `StepExecutionResult` est le dernier point où un `ErrorEnvelope` canonique est
encore disponible. `RecoveryDecisionResult` est l'owner des facts recovery,
retry, reconciliation et budget. Aucun `WorkflowEvent` n'est produit par ce call
graph ; G n'en synthétise donc pas pour logger.

## Décision

### Seam de composition

G utilise quatre éléments bornés :

- `ObservedPreLaunchGuard`, wrapper structurel du port `PreLaunchGuard` ;
- `ObservedStepRunner`, wrapper structurel du port `StepRunner` ;
- `ObservedRecoveryCoordinator`, sous-type du coordinator canonique qui appelle
  exactement une fois `RecoveryCoordinator.recover` ;
- `ObservedRecoveryRuntimeController`, wrapper externe qui appelle exactement
  une fois le controller canonique.

`instrument_plan_executor` et `instrument_recovery_runtime_controller`
recomposent uniquement le conteneur avec les mêmes scheduler, guards/runners,
coordinator d'orchestration et dépendances recovery. Les modules runtime,
recovery, Tool, Application, Agent, Gate et orchestration n'importent pas
observability. Il n'existe aucun manager global, singleton ou `ContextVar`.

Cette seam laisse les résultats `ExecutionCycleResult`, `CoordinationDecision`,
`RecoveryDecisionResult` et `RecoveryCycleResult` strictement inchangés.

### Façade failure-neutral

`RuntimeObservationEmitter` est l'unique owner technique de la construction via
les factories/mappers C, D et E puis des appels aux ports B. Chaque génération
d'ID, lecture d'horloge, mapping et appel sink est contenu. Une exception d'un
sink custom conforme aux ports est donc aussi neutralisée, indépendamment des
adapters F.

La façade ne retourne aucune décision, ne possède aucune policy d'autorité et ne
lit jamais payload, résultat opaque, metadata de sécurité brute ou métriques
opaques. Une panne telemetry ne produit ni log, metric ou `SecurityEvent`
récursif.

### Contexte de trace et providers

`RuntimeObservabilityContext` appartient au caller pour un logical run. Le
caller fournit son `TraceContext` root ; G ne génère donc pas le TraceId. Le
contexte conserve seulement root/current et est activé/restauré de façon
synchrone par les wrappers. Il n'entre jamais dans `RunState`, `StepState`,
snapshot, payload, arguments, requested effect ou delegation.

Après crash, la continuité existe uniquement si le caller restaure explicitement
le même root hors recovery business state. Le TraceId ne devient ni identité
idempotente, ni precondition de replay.

`ObservationIdSourcePort` fournit record IDs et nouveaux SpanIds ;
`ObservationClockPort` fournit seulement les timestamps telemetry. Les adapters
stdlib `UuidObservationIdProvider` et `UtcObservationClock` vivent sous
infrastructure. Le `now` runtime/recovery n'est jamais remplacé ou alimenté par
l'horloge observability.

### Hiérarchie et statuts des spans

```text
caller root
  -> RUNTIME.CYCLE
       -> ROUTING.PRELAUNCH
            -> GATE.EVALUATION, si le prelaunch appelle réellement le gate
       -> RUNTIME.STEP, seulement après lancement
            -> TOOL.CALL | APPLICATION.CALL | AGENT.INVOCATION
               | GATE.EVALUATION
       -> RECOVERY.CYCLE
            -> RECOVERY.RECONCILIATION, seulement si résultat réel
            -> RECOVERY.RETRY, seulement si décision réelle
```

Un nouveau SpanId est demandé pour chaque wrapper et chaque tentative. Le
TraceId reste celui du logical run et le parent du span de route est le span du
step. Le sidecar Agent est donc typé et n'utilise jamais
`DelegationEnvelope.trace_context`; `ContractMeta.trace_flags` est aussi ignoré.

`OK` signifie uniquement que l'appel technique s'est terminé. Un deny pre-effect
est `CANCELLED`, une attente/condition `UNSET`, un résultat partiel `UNSET`, un
échec technique `ERROR`. Un prelaunch deny ne crée aucun `RUNTIME.STEP` ni span
d'effet.

`SamplingDecision.DROP` supprime seulement les SpanRecords. `RECORD_ONLY` et
`RECORD_AND_SAMPLE` ont la même livraison locale en G ; leur distinction reste
réservée à un futur exporter. Logs et métriques sont indépendants du sampling.

### Ownership des émissions

| Source canonique | Owner G | Log C | Span D | Metrics E |
| --- | --- | --- | --- | --- |
| prelaunch decision | prelaunch wrapper | non | prelaunch/gate | non |
| launched `StepExecutionResult` | step wrapper | error réel | step + route | error |
| `SecurityEvent` du cycle | controller wrapper | une fois | non | security count |
| directive du cycle | controller wrapper | une fois | non | directive count |
| `RecoveryDecisionResult` | recovery wrapper | non | recovery cycle | recovery + budget |
| reconciliation réelle | recovery wrapper | non | reconciliation | reconciliation |
| retry decision réelle | recovery wrapper | non | retry | retry |

Les mappers C/E existants sont réutilisés. Aucun metric dynamique n'est créé ;
tous les `MetricPoint` valident contre le catalogue E et les IDs ne sont jamais
des labels. Aucun WorkflowEvent artificiel, ledger de déduplication ou scan de
metrics opaques n'est introduit.

### Dédoublonnage et ordre

Chaque wrapper appelle son inner une seule fois. Les security events et
directives sont parcourus une seule fois par le controller owner ; les erreurs
sont émises une fois au retour du runner ; recovery observe une seule décision.
Une nouvelle tentative est un nouvel événement et reçoit de nouveaux IDs.

L'ordre local suit prelaunch, step/route, sources du cycle puis recovery. Aucune
garantie cross-channel n'est ajoutée au delivery F.

### Delivery, flush et panne

G appelle seulement `emit`/`record`. Aucun wrapper ne flush. Le caller/admin
reste owner du flush explicite et borné F hors `execute_cycle`. Sinks absents ou
désactivés se composent avec `NullLogSink`, `NullTraceSink` et `NullMetricSink`,
sans I/O ni état autoritaire.

Les matrices disabled, healthy, custom raising, buffer saturated, serialization
rejected et partial writer prouvent :

```text
OBSERVABILITY_CONFIGURATION_DOES_NOT_CHANGE_RUNTIME_OUTCOME
```

Cette équivalence couvre run state, launched/completed IDs, directives,
security events, coordination, recovery action, budget, snapshot, retry et
reconciliation. Les nombres d'appels Tool et de probes recovery restent
identiques.

### Confidentialité et durabilité

Les wrappers ne lisent aucun prompt, payload, output, path, secret, message ou
details. Les records d'erreur passent par le mapper C qui exclut message/details.
La sérialisation F reste allowlistée. G n'ajoute ni DB, fichier, SQLite, WAL,
trace persistée ou dépendance externe. Un crash peut perdre toute telemetry sans
affecter recovery.

## Autorité et invariants

```text
OBSERVABILITY = observation only
OBSERVABILITY_CONFIGURATION_DOES_NOT_CHANGE_RUNTIME_OUTCOME
ONE_SECURITY_EVENT_OBSERVATION_PER_RUNTIME_EVENT
TRACE_ID_STABLE_FOR_LOGICAL_RUN
NEW_SPAN_ID_PER_ATTEMPT
METRIC_POINT_IS_NEVER_A_DECISION_FACT
```

UNKNOWN reste reconcilié avant replay ; PARTIAL n'est jamais auto-retry ;
COMMITTED n'est jamais rejoué ; NONE seul peut devenir retryable. Aucun owner
des Phases 6, 11 ou 12.12 n'est modifié.

## Rationalisation

Les wrappers ont des lifecycles distincts (prelaunch, route, recovery, cycle) et
des sources/dédoublonnages différents. Les fusionner déplacerait l'owner ou
forcerait des rappels de sources. La façade centralise déjà la seule mécanique
sûrement commune : mapping et livraison failure-neutral.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Frontière H

H1/H2/H3 peuvent auditer, durcir et fermer la phase. Ils ne doivent pas faire
des observations des facts d'autorité, ajouter une durabilité implicite ou
modifier les contrats B-F sans nouvelle décision canonique.
