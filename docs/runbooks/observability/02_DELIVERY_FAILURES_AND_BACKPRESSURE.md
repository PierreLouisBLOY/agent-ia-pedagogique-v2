# Observability — Échecs de delivery et backpressure

## Objet

Ce runbook traite les cinq raisons canoniques de non-livraison et la saturation
des buffers, sans retry interne, blocage métier ou récursion observability.

## Périmètre

Le périmètre commence à la soumission d'un `StructuredLogRecord`, `SpanRecord`
ou `MetricPoint`, puis couvre sérialisation, enqueue et flush vers un writer
injecté. Il s'arrête avant tout exporter fournisseur ou stockage durable.

## Invariants

```text
OBSERVABILITY_DELIVERY_FAILURE_IS_CONTAINED
OBSERVABILITY_FAILURE_IS_NOT_OBSERVED_RECURSIVELY_BY_DEFAULT
NO_INTERNAL_DELIVERY_RETRY_LOOP
```

Les seules raisons sont :

```text
BUFFER_FULL
SERIALIZATION_REJECTED
SINK_FAILURE
RECORD_TOO_LARGE
CHANNEL_DISABLED
```

Elles ne transportent ni exception, ni stack, ni contenu, ni identifiant de
record. La soumission est non bloquante et le delivery est best-effort.

## Triggers et symptômes

- `dropped_count`, `rejected_count` ou `failed_count` augmente ;
- `last_failure_reason` devient une des cinq valeurs fermées ;
- l'occupation atteint une capacité en items ou bytes ;
- un flush s'arrête avec `SINK_FAILURE`, `busy=True` ou `limit_reached=True` ;
- le canal apparaît `DISABLED`.

## Données sûres à examiner

Examiner channel, disposition, raison fermée, compteurs, occupancy/capacity,
taille sérialisée, limite de flush et retour numérique du writer. Ne jamais
collecter le record brut, `repr(exception)`, stack, prompt, output, métadonnée
security brute ou dump de la source.

## Procédure de diagnostic commune

1. Identifier le canal et la raison canonique.
2. Capturer uniquement les snapshots administratifs scalaires.
3. Vérifier la policy injectée et ses bornes.
4. Distinguer échec de soumission, saturation et échec de flush.
5. Vérifier que le runtime a produit exactement le même résultat.
6. Appliquer la procédure spécifique ci-dessous.
7. Exécuter un test synthétique ciblé avant clôture.

## BUFFER_FULL

**Symptômes.** `DROPPED/BUFFER_FULL`, occupation à `max_items` ou
`max_bytes`, ou `displaced_count > 0` avec `DROP_OLDEST`.

**Causes possibles.** Writer non flushé, capacité insuffisante, cadence de
production supérieure au flush, ou record qui ne tient pas avec les survivants.

**Diagnostic.** Comparer occupation/capacité, policy et cadence des flushs. La
baseline est `max_items=256`, `max_bytes=4 MiB`, `DROP_NEWEST`. Avec
`DROP_OLDEST` explicite, le minimum d'items anciens est déplacé ; les survivants
et le nouvel item conservent l'ordre FIFO. Il n'existe aucun block.

**Actions autorisées.** Flush borné si writer sain ; ajuster la capacité dans
les hard maximums ; choisir explicitement `DROP_OLDEST` si la perte de
l'historique est acceptée ; réduire le volume d'observations à la source.

**Actions interdites.** Attendre de la place, créer une queue non bornée,
rejouer le métier, persister en DB/WAL ou masquer la saturation par une boucle
de flush.

**Clôture.** Occupation stabilisée, policy explicitement validée, drops revenus
au niveau attendu et runtime inchangé.

**Escalade.** Toute croissance non bornée, tout block, ou impossibilité de
respecter les hard maximums.

## SERIALIZATION_REJECTED

**Symptômes.** `REJECTED/SERIALIZATION_REJECTED` et hausse de
`rejected_count` avant tout write.

**Causes possibles.** Type/champ non allowlisté, valeur non sûre, structure
invalide, serializer inattendu ou exception interne contenue.

**Diagnostic.** Identifier le type et le code d'observation, puis auditer le
mapper et le serializer allowlisté. Les serializers log/span/metric sont
explicites : aucune sérialisation générique de dataclass, aucun `asdict`,
`__dict__`, `repr(exception)` ou dump brut de la source.

**Actions autorisées.** Corriger le mapper ou l'allowlist dans un lot de code
séparé ; reproduire uniquement avec des fixtures synthétiques ; garder le canal
désactivé si le risque privacy l'exige.

**Actions interdites.** Ajouter `default=str`, sérialiser arbitrairement une
dataclass, copier l'exception ou contourner la validation safe-data.

**Clôture.** Fixture synthétique acceptée/rejetée conformément au contrat,
aucune valeur brute sérialisée, et tests de sérialisation verts.

**Escalade.** Fuite de donnée, type arbitraire accepté ou rejet affectant le
résultat runtime.

## RECORD_TOO_LARGE

**Symptômes.** `REJECTED/RECORD_TOO_LARGE`; aucune écriture writer. La borne
incluant la newline est :

```text
MAX_SERIALIZED_RECORD_BYTES = 65536
```

**Causes possibles.** Trop d'attributs/refs sûrs ou valeurs autorisées trop
volumineuses dans la projection.

**Diagnostic.** Examiner seulement la taille totale et le type/code du record,
jamais son contenu brut.

**Actions autorisées.** Réduire les attributs observability à la source et
resserrer le mapper dans un lot séparé.

**Actions interdites.** Augmenter la borne, tronquer aveuglément un contenu
potentiellement sensible ou fractionner le payload brut en plusieurs records.

**Clôture.** Records sous la borne, données toujours minimisées, tests de taille
et privacy verts.

**Escalade.** Besoin déclaré de transporter un contenu brut ou contournement de
la borne.

## SINK_FAILURE

**Symptômes.** Writer en exception, écriture partielle, retour non entier ou
longueur différente ; `failed_count` augmente et le flush s'arrête.

**Causes possibles.** Writer indisponible, contrat de writer violé, stream
fermé, exception ou write partiel.

**Diagnostic.** Examiner uniquement le type de writer injecté, le nombre
d'octets attendu/accepté et `DeliveryFlushResult`. Après le premier failure :

- le batch s'arrête ;
- l'item tenté n'est pas requeue ;
- les items non tentés restent FIFO ;
- aucune retry interne n'est lancée.

**Actions autorisées.** Remplacer/rétablir le writer, puis lancer un nouveau
flush borné explicitement. Accepter que l'item tenté puisse être perdu ou que
son état externe soit inconnu après write partiel.

**Actions interdites.** Retry automatique, requeue de l'item tenté, boucle de
backoff, déduction d'exactly-once ou événement récursif « delivery failed ».

**Clôture.** Writer conforme, flush borné réussi, tail FIFO préservée et aucun
effet runtime supplémentaire.

**Escalade.** Écritures partielles récurrentes, besoin de garantie durable/
exactly-once ou récursion observability.

## CHANNEL_DISABLED

**Symptômes.** `DROPPED/CHANNEL_DISABLED`, health `DISABLED`, aucune
sérialisation et aucune I/O.

**Causes possibles.** Composition volontaire avec `enabled=False` ou null sink.
Ce statut peut être nominal et n'est pas une panne métier.

**Diagnostic.** Vérifier la configuration de composition et la décision
opérationnelle ayant désactivé le canal.

**Actions autorisées.** Le laisser désactivé ou le réactiver explicitement avec
writer/policy valides.

**Actions interdites.** Réactiver implicitement depuis le runtime, traiter le
statut comme une décision security/recovery ou rejouer les observations perdues.

**Clôture.** État volontaire confirmé, ou canal réactivé et `HEALTHY`, avec
résultat runtime inchangé.

**Escalade.** Canal activé mais présenté comme disabled, ou configuration
observability qui change l'issue métier.

## Actions autorisées

- utiliser les snapshots et raisons fermées ;
- reproduire avec writers et records synthétiques ;
- flush explicite borné ;
- modifier la composition opérationnelle dans les bornes ;
- ouvrir un lot de correction séparé si le code doit changer.

## Actions interdites

- enregistrer l'exception ou le record brut ;
- créer une retry/requeue loop ;
- bloquer un chemin runtime ;
- créer un événement security ou une métrique récursive ;
- introduire worker, timer, queue durable, filesystem, DB ou WAL.

## Tests de vérification

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_observability_serialization.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_observability_delivery_buffer.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_observability_failure_isolated_sinks.py
.\.venv\Scripts\python.exe -m pytest -q tests/architecture/test_observability_delivery_boundary_fitness.py
```

## Critères de retour à la normale

La raison est expliquée par une configuration ou une cause connue, les bornes
sont respectées, le writer est conforme si activé, aucun compteur d'échec ne
progresse de manière inattendue, et les résultats métier/recovery sont égaux à
la baseline.

## Critères d'escalade

STOP si l'échec sort du port, déclenche retry/replay métier, fuit une donnée,
contourne les bornes, crée une récursion ou requiert une garantie de durabilité
hors scope.

## Références techniques

- [ADR-P12-047](../../../architecture/adr/ADR-P12-047-observability-delivery-failure-isolation.md)
- [Baseline delivery](../../development/PHASE_12_13_EXPORTERS_FAILURE_ISOLATION_BASELINE.md)
- [Delivery model](../../../backend/agent_runtime/observability/delivery_model.py)
- [Delivery policy](../../../backend/agent_runtime/observability/delivery_policy.py)
- [Serialization](../../../backend/infrastructure/observability/serialization.py)
- [Buffers](../../../backend/infrastructure/observability/buffering.py)
- [Sinks](../../../backend/infrastructure/observability/sinks.py)
