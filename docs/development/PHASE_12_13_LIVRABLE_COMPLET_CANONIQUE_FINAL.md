# Phase 12.13 — Livrable complet canonique final

## 1. Objet de la phase

La Phase 12.13 ferme le périmètre canonique d'observabilité provider-neutral :

```text
Logs
Traces
Métriques
Audit
Runbooks
```

Les observations restent diagnostiques, minimisées, bornées et sans autorité
sur le métier, la sécurité ou recovery.

## 2. Baseline d'entrée et résultat fonctionnel

```text
ENTRY_BASELINE = 4aa90f7455c483d1870742976c3c2abe863bb12a
FUNCTIONAL_SHA = 9f4b5ad9a0095994be149b4efe47a1af0ff71f16
FUNCTIONAL_TREE = 836c789266b8d53738db9ec48ba154a5c6930674
```

La baseline d'entrée est la clôture canonique de la Phase 12.12. Le SHA
fonctionnel final est G ; H3 ajoute uniquement les cinq documents de clôture.

## 3. Chaîne fonctionnelle A→G

A a audité le périmètre sans commit fonctionnel. La chaîne linéaire livrée est :

```text
B = 8227e7612e1884bef9f557e7f86e34255ce56e0a
C = 686e22e5c43d168974d67551316cdc06440afa49
D = d0a225aaf873da0a991f0befc152f686b844d2fd
E = 784cc4489ae79eb67498d78adbaf4ab1aceb055c
F = 5b3c3847c1dfe7e89877062e59dcad7cb421949e
G = 9f4b5ad9a0095994be149b4efe47a1af0ff71f16
```

G a F pour parent unique. Aucun merge commit ne se trouve dans cette chaîne.

## 4. Phase 12.13-A — audit initial

A a cartographié les contrats, événements, surfaces runtime/recovery, exigences
de privacy, cardinalité et failure isolation. Il a séparé les faits sources des
projections observability et confirmé qu'aucun SDK/provider ne devait être
introduit pour fermer la phase.

## 5. Phase 12.13-B — contrats et ports

B établit les contrats `TraceContext`, `StructuredLogRecord`, `SpanRecord` et
`MetricPoint`, ainsi que les ports synchrones log, trace et metric. Les contrats
n'importent ni HTTP, ORM, infrastructure ou SDK fournisseur. Leurs valeurs sont
data-only et n'accordent aucune autorité.

Décision : [ADR-P12-043](../../architecture/adr/ADR-P12-043-observability-contract-boundary.md).

## 6. Phase 12.13-C — structured logging

C introduit un catalogue fermé et des mappers explicites pour WorkflowEvent,
SecurityEvent, ErrorEnvelope et ExecutionDirective. La minimisation précède la
sérialisation : aucun prompt, payload/output, message/details d'erreur,
metadata security brute, secret ou chemin privé n'est copié.

Décision : [ADR-P12-044](../../architecture/adr/ADR-P12-044-structured-logging-minimization.md).

## 7. Phase 12.13-D — trace et propagation

D établit une propagation explicite root/child, sans contexte global ou
conversion legacy. TraceId et CorrelationId restent deux identités distinctes.
Le parent fournit TraceId et sampling ; chaque enfant reçoit un SpanId nouveau.

Décision : [ADR-P12-045](../../architecture/adr/ADR-P12-045-trace-context-propagation.md).

## 8. Phase 12.13-E — métriques et cardinalité

E ferme le catalogue à 14 métriques et à 285 séries théoriques, avec labels
allowlistés, maximum 256 séries par descriptor et 512 pour le catalogue. Les
IDs dynamiques et mappings métriques opaques ne deviennent jamais des labels ou
descriptors.

Décision : [ADR-P12-046](../../architecture/adr/ADR-P12-046-metric-catalog-cardinality.md).

## 9. Phase 12.13-F — delivery et isolation des échecs

F livre les serializers allowlistés, buffers FIFO bornés, writers injectés et
sinks failure-isolated. La baseline est 256 items, 4 MiB, flush 256 et
`DROP_NEWEST`; les hard maximums sont 4096 items, 64 MiB et flush 1024. Un
record sérialisé est limité à 65536 octets.

Le flush est explicite, synchrone, borné et caller/admin-owned. Il s'arrête au
premier échec, ne requeue pas l'item tenté et ne contient aucune retry loop.

Décision : [ADR-P12-047](../../architecture/adr/ADR-P12-047-observability-delivery-failure-isolation.md).

## 10. Phase 12.13-G — intégration runtime/recovery

G compose des wrappers autour des seams prelaunch, step, controller et recovery.
Chaque inner reste appelé exactement une fois. L'emitter projette les résultats
canoniques et contient toute panne de sink, provider d'ID ou clock.

Les directives et SecurityEvents sont observés une fois par le controller, les
ErrorEnvelope une fois par le runner, et les faits recovery après décision.
Aucun flush n'est exécuté dans `execute_cycle()`.

Décision : [ADR-P12-048](../../architecture/adr/ADR-P12-048-runtime-recovery-observability-integration.md).

## 11. Architecture finale

```text
Business / Security / Recovery owners
                |
                v
      canonical events/results
                |
                v
       explicit C/D/E mappers
                |
                v
        B provider-neutral ports
                |
                v
       F failure-isolated sinks
```

Les dépendances vont des adapters vers les contrats. Le core runtime/recovery
n'importe pas `backend.infrastructure.observability`, et `shared_kernel` ne
dépend pas d'`agent_runtime`.

## 12. Équivalence du résultat runtime

Les résultats business et recovery sont structurellement identiques avec
observability disabled, healthy, raising, saturated, rejected ou avec échec de
writer au flush. Les call counts scheduler, routing, Tool/Application/Agent,
gate, orchestration, effect, recovery et reconciliation probe sont inchangés.

```text
OBSERVABILITY_CONFIGURATION_DOES_NOT_CHANGE_RUNTIME_OUTCOME
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

## 13. Privacy et sécurité

La phase applique `MINIMIZATION_BEFORE_REDACTION`. Les payloads et outputs
Tool/Application/Agent, prompts, documents, provider responses, private
reasoning, secrets, chemins privés, ErrorEnvelope message/details et metadata
SecurityEvent brute sont interdits.

Les tests utilisent uniquement des fixtures synthétiques. Une panne de delivery
ne génère ni SecurityEvent, ni log, ni métrique récursive.

## 14. Trace et sampling

```text
TRACE_ID_STABLE_FOR_LOGICAL_RUN
NEW_SPAN_ID_PER_ATTEMPT
CHILD_SAMPLING_INHERITS_PARENT_EXACTLY
NO_IMPLICIT_CONVERSION_FROM_TRACE_FLAGS
NO_IMPLICIT_CONVERSION_FROM_DELEGATION_TRACE_CONTEXT
```

`ContractMeta.trace_flags` et `DelegationEnvelope.trace_context` restent legacy
opaque. `DROP` supprime uniquement les spans ; logs, métriques, SecurityEvents
et résultat runtime restent inchangés.

## 15. Métriques finales

```text
METRIC_CATALOG_SIZE = 14
THEORETICAL_SERIES = 285
MAX_SERIES_PER_DESCRIPTOR = 256
MAX_CATALOG_SERIES = 512
```

Chaque point runtime vient d'un mapper E et référence un descriptor catalogué.
Run/step/correlation/trace/span/invocation/delegation/record IDs, refs, URL,
paths et données provider restent hors labels.

## 16. Delivery et health

Les statuts sont `HEALTHY`, `DEGRADED` et `DISABLED`. Les raisons sont
`BUFFER_FULL`, `SERIALIZATION_REJECTED`, `SINK_FAILURE`, `RECORD_TOO_LARGE` et
`CHANNEL_DISABLED`. Stats, buffer, health et flush exposent uniquement des
snapshots scalaires et codes fermés, jamais un record ou une exception brute.

```text
OBSERVABILITY_DELIVERY_FAILURE_IS_CONTAINED
OBSERVABILITY_FAILURE_IS_NOT_OBSERVED_RECURSIVELY_BY_DEFAULT
NO_INTERNAL_DELIVERY_RETRY_LOOP
```

## 17. Recovery 12.11 préservé

```text
UNKNOWN -> reconcile before replay
PARTIAL -> never auto retry
COMMITTED -> never replay
NONE -> only potentially retryable
COMMITTED != SUCCEEDED without trusted terminal receipt
no synthetic idempotency identity
no retry loop
snapshot/budget/ledger/circuit monotone
recovery technical-only
```

Telemetry ne déclenche aucun retry et ne modifie ni EffectState, snapshot,
BudgetState, ledger, ReplayGuard ou CircuitBreaker.

## 18. Security 12.12 préservée

Security reste restriction-only et ses événements restent des faits data-only.
L'observabilité ne crée aucune permission, route, capability, gate, promotion
ou décision. Chaque SecurityEvent runtime possède un owner d'émission unique.

```text
ONE_SECURITY_EVENT_OBSERVATION_PER_RUNTIME_EVENT
```

## 19. Audit cumulatif H1

H1 a audité la chaîne B→G, les owners, l'équivalence runtime, la privacy, la
cardinalité, la récursion, le layering, les dépendances et le delta cumulatif.

```text
cumulative diff = 71 files
10735 insertions
2 deletions
targeted cumulative = 1196 PASS
global H1 = 3519 PASS
Python = 3.12.13
mypy = 618 source files
blocking findings = 0
```

Ruff, compileall, mypy et `git diff --check` étaient PASS.

## 20. Fast-forward strict H2

H2 a exécuté `git merge --ff-only` de la branche fonctionnelle vers `main`,
sans merge commit, rebase, squash, cherry-pick ou force push.

Après H2 :

```text
main = origin/main = G
phase12/12-13-observability local/remote = G
main vs phase branch = 0/0
MERGE_MODE = FAST_FORWARD_ONLY
```

## 21. Runbooks opérationnels H3

```text
RUNBOOKS = CLOSED
RUNBOOK_COUNT = 4
```

- [Operations et health](../runbooks/observability/01_OPERATIONS_AND_HEALTH.md)
  couvre l'exploitation nominale, les snapshots et le flush explicite ;
- [Delivery failures et backpressure](../runbooks/observability/02_DELIVERY_FAILURES_AND_BACKPRESSURE.md)
  traite les cinq raisons fermées et leurs remédiations ;
- [Privacy, sécurité et cardinalité](../runbooks/observability/03_PRIVACY_SECURITY_AND_CARDINALITY.md)
  couvre incidents de données, métriques et trace spoofing ;
- [Runtime, recovery et trace diagnostics](../runbooks/observability/04_RUNTIME_RECOVERY_TRACE_DIAGNOSTICS.md)
  couvre call graph, spans, sampling, call counts et recovery.

Chaque runbook contient objet, périmètre, invariants, triggers/symptômes,
données sûres, diagnostic, actions autorisées/interdites, tests, critères de
retour, critères d'escalade et références relatives au dépôt.

## 22. Invariants finaux

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
OBSERVABILITY_CONFIGURATION_DOES_NOT_CHANGE_RUNTIME_OUTCOME
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
OBSERVABILITY_DELIVERY_FAILURE_IS_CONTAINED
OBSERVABILITY_FAILURE_IS_NOT_OBSERVED_RECURSIVELY_BY_DEFAULT
NO_INTERNAL_DELIVERY_RETRY_LOOP
MINIMIZATION_BEFORE_REDACTION
NO_IMPLICIT_CONVERSION_FROM_TRACE_FLAGS
NO_IMPLICIT_CONVERSION_FROM_DELEGATION_TRACE_CONTEXT
TRACE_ID_STABLE_FOR_LOGICAL_RUN
NEW_SPAN_ID_PER_ATTEMPT
CHILD_SAMPLING_INHERITS_PARENT_EXACTLY
METRIC_POINT_IS_NEVER_A_DECISION_FACT
DO_NOT_EXPORT_OPAQUE_METRIC_MAPPINGS_BY_DEFAULT
TRACE_SAMPLING_DOES_NOT_CONTROL_METRIC_COLLECTION
ONE_SECURITY_EVENT_OBSERVATION_PER_RUNTIME_EVENT
```

## 23. Dépendances, scope et artifacts

```text
[project].dependencies == []
```

Aucun SDK de télémétrie, exporter réseau, DB/SQLite/WAL, queue durable, global
logger/tracer, UI, alerting, provider ou configuration distante n'est livré.
Le delta H3 contient exclusivement cinq fichiers Markdown.

## 24. Validation normative H3

La gate est exécutée avec les cinq documents présents :

| Validation | Résultat |
| --- | --- |
| Python | 3.12.13 |
| suite globale H3 | 3519 PASS |
| `python -m compileall backend` | PASS |
| `python -m ruff check .` | PASS |
| `python -m mypy backend` | PASS — 618 source files |
| `git diff --check` | PASS |
| `[project].dependencies` | `[]` |

## 25. Rationalisation finale

WorkflowEvent, SecurityEvent, ErrorEnvelope, records observability, contexte de
trace, catalogues, emitter, delivery, RetryPolicy et CircuitBreaker gardent des
owners, sémantiques, autorités et cycles de vie distincts. Les fusionner créerait
une façade trop puissante ou modifierait leurs garanties de panne.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

Aucune consolidation n'est effectuée en H3.

## 26. Audit post-merge et clôture documentaire

Le préflight H3 a confirmé `main`, `origin/main` et les refs locale/distante de
la branche fonctionnelle sur G, le tree fonctionnel attendu, la relation `0/0`
et un worktree propre. H3 ajoute exactement quatre runbooks et ce livrable,
sans fichier Python, configuration, dépendance, test, ADR ou baseline modifié.

Le commit documentaire unique a G pour parent direct. Son push cible uniquement
`main`; la branche fonctionnelle reste sur G.

## 27. Statut final

```text
PHASE 12.13-H3 — PASS / CLOSED
PHASE 12.13 — CLOSED / MERGED
RUNBOOKS = CLOSED
RUNBOOK_COUNT = 4
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
MERGE_MODE = FAST_FORWARD_ONLY
NEXT_PHASE = 12.14
PHASE_12_14_SCOPE = HARNESS_TESTS_EVALUATIONS_AGENTIQUES
```

## 28. Handoff canonique

```text
NEXT_PHASE = 12.14
PHASE_12_14_SCOPE = HARNESS_TESTS_EVALUATIONS_AGENTIQUES
```

La suite de la feuille de route reste :

```text
12.14 — Harness de tests et évaluations agentiques
12.15 — Intégration end-to-end sur scénarios pédagogiques canoniques
12.16 — Choix/calibration providers, modèles, budgets, timeouts et contexte
12.17 — Audit de rationalisation de l'implémentation et dette technique
12.18 — Gate finale et livrable complet canonique Phase 12
```

La Phase 12.14 n'est pas implémentée dans ce lot.
