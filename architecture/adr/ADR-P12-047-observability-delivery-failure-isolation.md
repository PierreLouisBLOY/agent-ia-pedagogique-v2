# ADR-P12-047 — Livraison observability et isolation des échecs

## Statut

Accepté pour la Phase 12.13-F.

## Contexte

Les Phases 12.13-B à E fournissent trois ports synchrones, des records déjà
minimisés et des catalogues/mappers provider-neutral. Aucun adapter de livraison,
serializer ou buffer n'existe encore dans `backend/infrastructure/observability`.
F doit préparer une livraison concrète sans instrumenter les chemins runtime ou
recovery que G composera plus tard.

## Audit et rationalisation

| Primitive | Owner | Lifecycle | Failure semantics | I/O | État borné | Réutilisation |
| --- | --- | --- | --- | --- | --- | --- |
| `LogSinkPort` | agent runtime observability | appel synchrone | best-effort, `None` | abstrait | non | préserver |
| `TraceSinkPort` | agent runtime observability | appel synchrone | best-effort, `None` | abstrait | non | préserver |
| `MetricSinkPort` | agent runtime observability | appel synchrone | best-effort, `None` | abstrait | non | préserver |
| delivery policy/model | agent runtime observability | configuration/snapshot | non autoritative | non | oui | créer |
| serializer NDJSON | infrastructure observability | une observation | rejet fermé avant write | non | taille record | créer par channel |
| writer | infrastructure observability | un record sérialisé | write ou exception/partial write | oui | externe | port infrastructure injecté |
| buffer FIFO | infrastructure observability | durée du process | drop explicite | non | items + bytes | mécanique générique, instance par channel |
| channel sink | infrastructure observability | durée du process | contient toute exception | oui | buffer + compteurs | trois adapters distincts |
| delivery stats/health | observability delivery | durée du process | diagnostic uniquement | non | compteurs scalaires | créer |
| recovery `RetryPolicy`/backoff | recovery | tentative métier | décide retry/replan/stop | non | budget métier | ne pas réutiliser |
| recovery circuit breaker | recovery | route/effect | bloque ou autorise un lancement | ports store | état persistant | ne pas réutiliser |
| `SandboxPolicy` | sandbox | accès filesystem métier | allow/deny | non | registry | ne pas réutiliser ; aucun file exporter |
| `SecurityEvent` | security | fait de sécurité | signal structuré | non | record | ne jamais créer sur panne delivery |
| `ErrorEnvelope`/`EffectState` | runtime/recovery | échec et effet métier | décisions recovery | non | état métier | ne pas réutiliser |

Les cycles de vie et autorités diffèrent. Le verdict est :

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
OBSERVABILITY_DELIVERY_HAS_ITS_OWN_NON_AUTHORITATIVE_FAILURE_POLICY
```

## Décision

### Modèle provider-neutral

`delivery_model.py` définit des vocabulaires fermés pour les channels,
dispositions, drop reasons, overflow policy et health, ainsi que des snapshots
immutables. `delivery_policy.py` porte uniquement la configuration bornée :

```text
1 <= max_items <= 4096
1 <= max_bytes <= 67108864
1 <= max_flush_items <= 1024
default = 256 items / 4194304 bytes / 256 flush items
overflow default = DROP_NEWEST
```

Les signatures B restent inchangées. Une API administrative `submit`, `flush`
et `health_snapshot` existe sur les adapters concrets, sans modifier les retours
des ports.

### Sérialisation

Trois serializers spécifiques produisent un objet NDJSON UTF-8 terminé par
`\n`. Chaque objet porte `type` (`log`, `span`, `metric`) et `schema_version`.
Les champs sont allowlistés explicitement ; aucun `asdict`, `__dict__`, `repr`,
nom de classe Python ou serializer générique de dataclass n'est utilisé.

L'ordre JSON est déterministe (`sort_keys=True`, séparateurs compacts,
`allow_nan=False`). Les instants UTC sont émis avec six décimales et suffixe
`Z`. Les `Decimal` métriques restent exacts sous la forme typée :

```json
{"type":"decimal","value":"1.25"}
```

Les entiers et floats ont aussi un discriminant fermé ; les floats utilisent
une représentation `.17g`. Les refs et attributs utilisent une conversion
allowlistée des seuls types déjà acceptés par les contrats B.

`MAX_SERIALIZED_RECORD_BYTES = 65536`, newline comprise. Cette borne peut
refuser un record B valide mais volumineux avant toute I/O ; elle limite le coût
de delivery et reste cohérente avec les attributs B bornés à 512 nœuds. Le rejet
ne modifie jamais le record source.

### Buffer et backpressure

Une mécanique FIFO générique stocke les NDJSON sérialisés. Chaque adapter
log/trace/metric possède sa propre instance : aucune garantie d'ordre
cross-channel n'est promise.

Les bornes `max_items` et `max_bytes` sont vérifiées atomiquement. La policy par
défaut `DROP_NEWEST` préserve l'historique déjà en queue. `DROP_OLDEST` est
disponible explicitement et retire le minimum d'anciens items nécessaire sans
réordonner les survivants. Il n'existe ni attente conditionnelle, ni queue
illimitée, ni boucle de retry.

### Flush et write

`flush(max_items=None)` est synchrone, explicite et borné par
`policy.max_flush_items`. Un seul flush par adapter peut progresser ; un second
appel concurrent retourne immédiatement `busy=True`. Les submits concurrents
restent disponibles pendant le write.

Chaque item dépilé reçoit au plus une tentative de write. Un write réussi doit
retourner exactement le nombre de caractères du NDJSON. Exception ou write
partiel donne `SINK_FAILURE`, retire l'item, incrémente les stats et arrête le
batch ; les items non tentés restent FIFO. Il n'y a ni requeue ni retry interne.

Cette sémantique est best-effort et at-most-one write attempt, pas exactly-once.
Une panne après write partiel est inconnue uniquement pour l'exporter et ne
devient jamais un `EffectState`.

### Isolation, stats et récursion

`emit`/`record`, `submit` et `flush` contiennent les exceptions de serialization
et de writer. Les erreurs fermées ne conservent que code/channel et jamais le
texte, stack ou payload de l'exception originale.

Les compteurs monotones scalaires sont : delivered, buffered, dropped, failed,
rejected. Le health snapshot ajoute occupancy/capacity et un dernier drop reason
fermé. Il ne contient aucune liste par record, exception ou contenu. Les stats
ne sont jamais réémises automatiquement :

```text
OBSERVABILITY_DELIVERY_FAILURE_IS_CONTAINED
OBSERVABILITY_FAILURE_IS_NOT_OBSERVED_RECURSIVELY_BY_DEFAULT
```

### Concurrence et durabilité

Les buffers, stats et adapters sont thread-safe avec des locks stdlib simples.
Il n'existe aucun thread, timer ou worker de fond. Les calls de submit ne sont
pas bloqués par un writer lent ; les flush concurrents échouent immédiatement
en mode busy.

Le buffer est seulement mémoire. Un crash process peut perdre toutes les
observations. F n'ajoute ni fichier, SQLite, base, WAL, ledger, replay guard ou
idempotency identity.

### Exporters concrets

F livre seulement des adapters NDJSON vers un `TextRecordWriter` injecté et un
wrapper de stream injecté. Il n'existe aucun global stdout logger ni file
exporter. OpenTelemetry, Prometheus et HTTP restent différés ; aucune dépendance
externe n'est ajoutée.

### Métriques

Les `MetricPoint` bruts E sont sérialisés directement. F ne duplique pas le
catalogue et ne crée aucun agrégateur ou bucket mutable.

## Autorité et frontières

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
METRIC_POINT_IS_NEVER_A_DECISION_FACT
NO_INTERNAL_DELIVERY_RETRY_LOOP
```

`agent_runtime` n'importe jamais `infrastructure`. F ne modifie aucun executor,
router, coordinator, recovery controller ou owner de sécurité. G possédera la
composition et les appels réels aux sinks.

## Conséquences

La livraison est bornée, testable et isolée sans SDK. Le coût assumé est une
perte possible sous saturation, panne writer ou crash, ainsi que l'absence de
durabilité et de retry automatique. Ces pertes restent strictement extérieures
aux résultats métier et recovery.
