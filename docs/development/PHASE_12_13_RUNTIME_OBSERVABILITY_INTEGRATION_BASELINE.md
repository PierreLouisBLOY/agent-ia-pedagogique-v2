# Phase 12.13 — Baseline intégration observability runtime/recovery

## Portée du lot G

G connecte réellement les ports B aux chemins runtime et recovery par une
composition provider-neutral, explicite et failure-neutral. Les contrats B, les
mappers C, la trace D, le catalogue E et le delivery F restent les owners.

Décision canonique :

- [ADR-P12-048](../../architecture/adr/ADR-P12-048-runtime-recovery-observability-integration.md)

## Baseline Git d'entrée

```text
branch = phase12/12-13-observability
HEAD = 5b3c3847c1dfe7e89877062e59dcad7cb421949e
origin/phase12/12-13-observability = 5b3c3847c1dfe7e89877062e59dcad7cb421949e
parent F = 784cc4489ae79eb67498d78adbaf4ab1aceb055c
main = 4aa90f7455c483d1870742976c3c2abe863bb12a
origin/main = 4aa90f7455c483d1870742976c3c2abe863bb12a
merge-base(main, HEAD) = 4aa90f7455c483d1870742976c3c2abe863bb12a
main...HEAD = 0 5
worktree = clean
```

Le fetch origin et toutes les vérifications strictes ont été exécutés avant
modification.

## Call graph et seam

```text
schedule
-> prelaunch (wrapper, inner une fois)
-> launched step / route (wrapper, inner une fois)
-> ExecutionCycleResult
-> coordination (inchangée, une fois)
-> recovery (wrapper de RecoveryCoordinator, inner une fois)
-> budget/reconciliation/retry/checkpoint/snapshot
-> RecoveryCycleResult
```

La composition `instrument_recovery_runtime_controller` conserve les instances
canoniques de scheduler, orchestration et dépendances recovery. Elle remplace
seulement les seams de ports par des wrappers. Aucun appel métier n'est effectué
pour mesurer et les modules core n'importent pas observability.

## Composants G

Couche agent runtime :

- `RuntimeObservabilityContext` : root/current explicites, caller-owned ;
- `ObservationIdSourcePort` et `ObservationClockPort` ;
- `RuntimeObservationEmitter` : mappings C/D/E et appels B contenus ;
- trois sinks null explicites ;
- wrappers prelaunch, step, recovery et controller ;
- fonctions de composition plan executor/controller.

Infrastructure :

- `UuidObservationIdProvider` ;
- `UtcObservationClock`.

Tests/support : providers déterministes, clock contrôlée, sinks collecteurs et
sinks custom levant directement.

## Trace root, IDs et temps

Le caller fournit le TraceId et le root SpanId. Le contexte n'est ni dérivé du
run/correlation/payload, ni lu depuis `trace_flags` ou le mapping legacy de
delegation. L'ID provider ne produit que record IDs et SpanIds enfants opaques.

Le clock observability sert exclusivement à `started_at`, `ended_at` et
`observed_at`. Le `now` métier/recovery traverse les owners historiques sans
changement. Toute panne de provider abandonne l'observation et laisse l'output
runtime identique.

Le caller restaure explicitement le root après crash s'il souhaite la continuité
du logical run. Aucun contexte n'entre dans snapshot, ledger ou identité
idempotente.

## Matrice d'émission réelle

| Point réel | Spans | Logs | Metrics |
| --- | --- | --- | --- |
| cycle controller | `RUNTIME.CYCLE` | directives/security du résultat | directives/security |
| prelaunch | `ROUTING.PRELAUNCH`, gate si appelé | owner cycle uniquement | owner cycle uniquement |
| Tool | `RUNTIME.STEP` + `TOOL.CALL` | erreur canonique éventuelle | error éventuelle |
| Application | `RUNTIME.STEP` + `APPLICATION.CALL` | erreur canonique éventuelle | error éventuelle |
| Agent | `RUNTIME.STEP` + `AGENT.INVOCATION` | erreur canonique éventuelle | error éventuelle |
| Gate step | `RUNTIME.STEP` + `GATE.EVALUATION` | directive owner cycle | directive owner cycle |
| recovery | `RECOVERY.CYCLE` | aucun record synthétique | action + six budget gauges |
| reconciliation réelle | `RECOVERY.RECONCILIATION` | aucun | disposition |
| retry decision réelle | `RECOVERY.RETRY` | aucun | disposition |

Les directives et SecurityEvents sont émis une fois au niveau controller. Les
ErrorEnvelope sont émis une fois au retour du runner, avant perte de la source.
WorkflowEvent n'est pas synthétisé.

## Sampling et status

`DROP` supprime tous les spans, sans supprimer logs, métriques, security events
ou décisions runtime. `RECORD_ONLY` et `RECORD_AND_SAMPLE` livrent tous deux les
spans locaux en G. La future différence exporter reste hors scope.

`OK` indique seulement la complétion technique. Deny prelaunch est CANCELLED,
waiting/condition et PARTIAL sont UNSET, exception/failed est ERROR. Aucun span
d'exécution n'est créé pour un step non lancé.

## Delivery et flush

Les wrappers soumettent via les ports et ne flushent jamais. Le caller/admin
flush explicitement les adapters F hors cycle. Les canaux disabled utilisent
des null sinks sans I/O ; aucune condition `sink is not None` n'est dispersée.

## Matrice d'équivalence

| Configuration | Résultat runtime/recovery | Effet/probe count | Observation |
| --- | --- | --- | --- |
| null/disabled | baseline | inchangé | aucune I/O |
| collectors sains | égal baseline | inchangé | records collectés |
| ports custom raising | égal baseline | inchangé | exceptions contenues |
| buffers tiny saturés | égal baseline | inchangé | drops F |
| max bytes rejet | égal baseline | inchangé | rejects F |
| writer partiel au flush | déjà égal baseline | inchangé | failure F après cycle |
| ID provider/clock raising | égal baseline | inchangé | observation abandonnée |

Les comparaisons utilisent l'égalité structurelle complète du
`RecoveryCycleResult`, incluant run state, IDs lancés/terminés, directives,
security events, coordination, action recovery, budget, snapshot, retry et
reconciliation.

## Dédoublonnage, call counts et reprise

- scheduler et controller : un appel canonique ;
- prelaunch : un wrapper par appel candidat, aucun rappel ;
- runner et route externe : un appel par step lancé ;
- Tool/Application/Agent : call count inchangé ;
- coordination et recovery : une fois ;
- reconciliation probe : une fois ;
- une source security/directive/error : une émission owner ;
- nouvelle tentative : nouvelle paire step/route de SpanIds, même TraceId.

Aucun ledger telemetry n'est ajouté. Une telemetry perdue après crash n'est pas
rejouée et ne modifie jamais recovery.

## Privacy et cardinalité

Les wrappers ne consultent pas payload, result output, prompt, path, metadata
security brute, message/details d'erreur ou metrics opaques. Les logs d'erreur
réellement soumis et sérialisés excluent message/details. Les security logs
excluent metadata/content lineage.

Tous les points runtime viennent des mappers E et leurs descriptors appartiennent
à `METRIC_CATALOG`. Les seules labels sont les valeurs fermées du catalogue ;
trace/span/run/step/registry IDs restent hors labels.

## Failure recursion, durabilité et autorité

Une panne sink/provider ne crée aucun nouveau log, metric ou SecurityEvent. G
n'ajoute ni worker, file exporter, DB, SQLite, WAL, retry delivery, état global
ou dépendance externe. Aucun observability state n'entre dans RunState/snapshot.

Les invariants security 12.12 et recovery 12.11 restent propriétaires : UNKNOWN
avant replay, PARTIAL jamais auto-retry, COMMITTED jamais replay, NONE seul
potentiellement retryable, aucune identité idempotente synthétique et aucun retry
loop interne.

## Validation normative

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m compileall backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy backend
git diff --check
```

Résultats exécutés avant livraison :

```text
tests G ciblés = 24 passed
régression observabilité B→F = 195 passed
régression security/recovery/routing/sandbox = 855 passed
architecture fitness = PASS
suite globale = 3519 passed
Python = 3.12.13
compileall backend = PASS
ruff check . = PASS
mypy backend = PASS (618 source files)
git diff --check = PASS
project.dependencies = []
```

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
NEXT_GATE = 12.13-H1_READY
```
