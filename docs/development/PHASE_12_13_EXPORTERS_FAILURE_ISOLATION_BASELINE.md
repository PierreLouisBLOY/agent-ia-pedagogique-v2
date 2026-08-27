# Phase 12.13 — Baseline exporters et isolation des échecs

## Portée du lot F

F livre la couche de delivery best-effort qui pourra être composée par G. Les
ports B restent inchangés et aucun appel sink n'est ajouté aux chemins runtime,
routing, orchestration, Tool/Application/Agent ou recovery.

Décision canonique :

- [ADR-P12-047](../../architecture/adr/ADR-P12-047-observability-delivery-failure-isolation.md)

## Baseline Git d'entrée

```text
branch = phase12/12-13-observability
HEAD = 784cc4489ae79eb67498d78adbaf4ab1aceb055c
origin/phase12/12-13-observability = 784cc4489ae79eb67498d78adbaf4ab1aceb055c
main = 4aa90f7455c483d1870742976c3c2abe863bb12a
origin/main = 4aa90f7455c483d1870742976c3c2abe863bb12a
merge-base(main, HEAD) = 4aa90f7455c483d1870742976c3c2abe863bb12a
main...HEAD = 0 4
worktree = clean
```

## Audit delivery

Le dépôt ne contenait aucun serializer, exporter, queue ou buffer observability
concret. `backend/infrastructure/observability/` était structurel. Les trois
ports B sont synchrones et retournent `None` :

```text
LogSinkPort.emit(StructuredLogRecord) -> None
TraceSinkPort.emit(SpanRecord) -> None
MetricSinkPort.record(MetricPoint) -> None
```

La sérialisation JSON générique existante appartient à l'identité idempotente
recovery et accepte des dataclasses arbitraires ; elle n'est pas réutilisée.
Recovery RetryPolicy/backoff/circuit breaker, SandboxPolicy, SecurityEvent,
ErrorEnvelope et EffectState ont des owners et autorités incompatibles avec un
delivery diagnostic.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
OBSERVABILITY_DELIVERY_HAS_ITS_OWN_NON_AUTHORITATIVE_FAILURE_POLICY
```

## Architecture

### Couche provider-neutral

`backend/agent_runtime/observability/` contient uniquement :

- enums fermés channel/disposition/drop/overflow/health ;
- résultats et snapshots immutables ;
- `ObservabilityDeliveryPolicy` bornée.

Cette couche n'importe ni infrastructure, I/O, JSON, threading ou filesystem.

### Couche infrastructure

`backend/infrastructure/observability/` contient :

- serializers allowlistés log/span/metric ;
- `BoundedDeliveryBuffer`, FIFO générique réutilisé ;
- `TextRecordWriter` et `StreamTextRecordWriter` sur stream injecté ;
- `FailureIsolatedLogSink`, `FailureIsolatedTraceSink` et
  `FailureIsolatedMetricSink`.

Il n'existe aucun file exporter, global stdout logger, chemin configurable,
SDK externe ou fake de production. Les writers de panne/collecte restent sous
`tests/support`.

## Schéma NDJSON

Chaque observation devient exactement un objet JSON UTF-8 terminé par newline,
avec ordre de clés stable, séparateurs compacts et `allow_nan=False`.

Champs communs :

```text
type = log | span | metric
schema_version = MAJOR.MINOR
```

Les serializers sélectionnent explicitement les champs B-E. Ils n'utilisent
jamais `asdict`, `__dict__`, `repr`, nom de classe Python ou serializer générique
de dataclass.

Formats canoniques :

- `Instant` : UTC ISO-8601, six décimales, suffixe `Z` ;
- `Decimal` : objet `{type: decimal, value: string}` sans conversion float ;
- int/float métriques : objets typés avec valeur textuelle canonique ;
- trace : IDs et sampling technique explicites ;
- refs/attributes : conversion récursive des seuls types allowlistés B.

La safe-data validation est réappliquée au payload explicitement construit avant
JSON. Aucun prompt, message/details, secret-like value ou private path ne peut
réapparaître par sérialisation.

```text
MAX_SERIALIZED_RECORD_BYTES = 65536
```

La newline est comprise. Un dépassement est rejeté avant write par le code fermé
`RECORD_TOO_LARGE`.

## Buffer et backpressure

Policy baseline :

```text
max_items = 256           (borne absolue 4096)
max_bytes = 4194304       (borne absolue 67108864)
max_flush_items = 256     (borne absolue 1024)
overflow = DROP_NEWEST
```

Le buffer est FIFO et borné simultanément en items et bytes. `DROP_NEWEST`
préserve par défaut l'historique déjà bufferisé. `DROP_OLDEST`, uniquement sur
configuration explicite, déplace le minimum d'items et ne réordonne pas les
survivants.

Chaque channel possède son buffer. Il n'existe aucune garantie d'ordre globale
log/span/metric. Aucune attente conditionnelle ou backpressure métier n'existe :
la saturation produit un drop fermé.

## Dispositions et raisons

Dispositions de submit réellement utilisées :

```text
BUFFERED
DROPPED
REJECTED
```

Raisons fermées réellement utilisées :

```text
BUFFER_FULL
SERIALIZATION_REJECTED
SINK_FAILURE
RECORD_TOO_LARGE
CHANNEL_DISABLED
```

Elles ne contiennent jamais d'exception, record ID, message, stack ou payload.

## Flush, ordering et retry

`flush(max_items=None)` utilise au plus `policy.max_flush_items`. Un item est
dépilé FIFO puis reçoit une seule tentative de write :

- write complet : delivered ;
- exception ou longueur partielle : failed, item perdu, batch arrêté ;
- items non tentés : restent dans le buffer, dans leur ordre initial ;
- limite atteinte : tail conservé, `limit_reached=True` ;
- flush concurrent : retour immédiat `busy=True`.

Il n'existe ni requeue, retry automatique, backoff ou circuit breaker delivery.
La garantie est best-effort at-most-one write attempt, jamais exactly-once. Une
panne après write partiel reste inconnue pour l'exporter uniquement.

## Failure isolation et récursion

Les exceptions de serializer et writer sont contenues. Les erreurs de
serialization portent seulement code/channel et masquent leur cause. Les
signatures B ne renvoient aucun résultat administratif et ne propagent pas les
pannes.

Les stats scalaires monotones sont :

```text
delivered_count
buffered_count
dropped_count
failed_count
rejected_count
```

Le health ajoute status fermé, occupancy/capacity et dernier drop reason fermé.
Il ne conserve aucune exception ou liste par record. Stats et health ne sont
jamais réémis automatiquement ; une panne ne crée ni StructuredLogRecord,
SecurityEvent, MetricPoint ou retry.

```text
OBSERVABILITY_DELIVERY_FAILURE_IS_CONTAINED
OBSERVABILITY_FAILURE_IS_NOT_OBSERVED_RECURSIVELY_BY_DEFAULT
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
```

## Thread-safety, crash et durabilité

Buffer, stats, stream writer et adapters utilisent des locks stdlib. Les
submits concurrents sont atomiques et restent indépendants d'un write en cours.
Un seul flush progresse par adapter ; les concurrents n'attendent pas.

Aucun thread, timer ou worker de fond n'est créé. Le buffer est mémoire : un
crash process peut perdre toutes les observations. Aucun fichier, SQLite, DB,
WAL, ledger, replay guard ou idempotency identity n'est ajouté.

## Métriques

Les `MetricPoint` E bruts sont sérialisés. F ne crée ni aggregation, bucket,
registry de séries ou duplication de MetricCatalog.

## Matrice de panne

| Cas | Résultat F | Source/runtime | Stats et récursion |
| --- | --- | --- | --- |
| sink success | buffered puis delivered | inchangé | compteurs +1 |
| writer raises avant write | failed, batch arrêté | exception contenue | aucun raw/record récursif |
| writer partiel/reject | `SINK_FAILURE` | inchangé | failed +1 |
| buffer full | newest dropped par défaut | non bloqué | dropped +1 |
| record oversized | rejected avant I/O | inchangé | rejected +1 |
| record invalide | rejected sans escape du port | inchangé | rejected +1 |
| flush partial progress | succès conservés, tail FIFO | inchangé | delivered/failed exacts |
| repeated failure | un item distinct par flush | aucun retry du même item | failed monotone |
| disabled channel | dropped avant serialization | inchangé | health DISABLED |
| concurrent submit/flush | atomique ; flush concurrent busy | non autoritatif | bornes préservées |

## Architecture fitness

Les tests prouvent :

- adapters conformes aux trois ports B ;
- aucun import infrastructure depuis agent runtime ;
- aucun branchement dans runtime/recovery/routing/orchestration ;
- serializers allowlistés et taille bornée ;
- buffer borné, FIFO et overflow explicite ;
- absence de retry infini, worker, file exporter ou SDK ;
- absence de RetryPolicy/ReplayGuard/EffectState/SecurityEvent delivery ;
- aucune persistance d'exception ou récursion observability ;
- dépendances runtime vides.

## Frontière G

G possédera exclusivement la composition et le placement des appels aux sinks
dans les chemins réels. F n'ajoute aucune instrumentation.

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
tests F ciblés / failure matrix = 35 passed
régression observabilité B→F = 195 passed
régression sécurité/value-safety/Budget/recovery/retrieval/Evidence = 499 passed
suite globale = 3495 passed
Python = 3.12.13
compileall backend = PASS
ruff check . = PASS
mypy backend = PASS (613 source files)
git diff --check = PASS
project.dependencies = []
```

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
NEXT_GATE = 12.13-G_READY
```
