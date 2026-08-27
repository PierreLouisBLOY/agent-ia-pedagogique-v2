# Observability — Operations et health

## Objet

Ce runbook décrit l'exploitation normale des trois canaux d'observabilité :
`log`, `span` et `metric`. Il permet d'inspecter leur état, de diagnostiquer une
dégradation et de rétablir la livraison sans modifier le résultat runtime,
security ou recovery.

## Périmètre

Le périmètre couvre les adapters de delivery en mémoire, leurs policies, leurs
snapshots administratifs et le flush explicite. Il ne couvre ni exporter
réseau, ni persistance, ni alerting, ni décision métier.

Chaque canal possède son buffer, ses compteurs, son writer et son health. Il
n'existe aucune garantie d'ordre globale entre les trois canaux.

## Politique baseline et plafonds

La policy baseline est :

```text
baseline max_items       = 256
baseline max_bytes       = 4 MiB
baseline max_flush_items = 256
baseline overflow        = DROP_NEWEST
```

Les hard maximums, distincts de la baseline, sont :

```text
MAX_BUFFER_ITEMS = 4096
MAX_BUFFER_BYTES = 64 MiB
MAX_FLUSH_ITEMS  = 1024
MAX_SERIALIZED_RECORD_BYTES = 65536
```

Une composition peut choisir une valeur comprise dans ces bornes. Elle ne doit
jamais présenter un hard maximum comme la configuration opérationnelle active.

## Invariants

```text
OBSERVABILITY_NEVER_CREATES_AUTHORITY
OBSERVABILITY_CONFIGURATION_DOES_NOT_CHANGE_RUNTIME_OUTCOME
OBSERVABILITY_FAILURE_NEVER_CHANGES_BUSINESS_RUNTIME_SECURITY_OR_RECOVERY_OUTCOME
OBSERVABILITY_DELIVERY_FAILURE_IS_CONTAINED
NO_INTERNAL_DELIVERY_RETRY_LOOP
```

Le runtime soumet des observations best-effort. Il n'attend ni livraison, ni
flush, ni retour à `HEALTHY` pour continuer.

## Health et surfaces administratives

Les statuts fermés sont :

- `HEALTHY` : canal activé et aucune raison d'échec courante ;
- `DEGRADED` : canal activé avec une raison fermée dans
  `last_failure_reason` ;
- `DISABLED` : canal désactivé volontairement par sa composition.

Les surfaces sûres sont :

- `DeliveryHealthSnapshot` : canal, statut, stats, buffer et dernière raison ;
- `DeliveryStatsSnapshot` : compteurs scalaires monotones ;
- `DeliveryBufferSnapshot` : occupation et capacités en items et octets ;
- `DeliveryFlushResult` : tentatives, livraisons, échecs, reste, busy, limite
  atteinte et raison d'arrêt.

Ces surfaces sont diagnostiques. Elles ne sont ni `PolicyFact`, ni entrée de
gate, ni état recovery.

## Triggers et symptômes

Utiliser ce runbook lorsqu'un canal devient `DEGRADED` ou `DISABLED`, lorsque
l'occupation progresse durablement, lorsque des compteurs dropped/failed/
rejected augmentent, ou lorsqu'un flush signale `busy`, `limit_reached` ou
`SINK_FAILURE`.

Une absence d'observation n'est pas à elle seule une panne métier. Vérifier le
sampling pour les spans et l'état volontairement disabled avant d'escalader.

## Données sûres à examiner

Examiner uniquement : channel, health status, capacités/occupations, compteurs,
raison fermée, disposition, code d'observation, labels allowlistés et résultat
agrégé d'un flush. Ne pas copier payload, prompt, contenu, output, message ou
détails d'exception pour diagnostiquer la livraison.

## Procédure de diagnostic

1. Identifier le channel exact : `log`, `span` ou `metric`.
2. Lire son health status : `HEALTHY`, `DEGRADED` ou `DISABLED`.
3. Lire `occupancy_items` et `occupancy_bytes`.
4. Comparer avec `capacity_items` et `capacity_bytes`, puis avec la policy
   réellement injectée.
5. Comparer les compteurs `delivered_count`, `buffered_count`, `dropped_count`,
   `failed_count` et `rejected_count` sur une fenêtre bornée.
6. Lire uniquement le code fermé `last_failure_reason`.
7. Déclencher un flush explicite et borné seulement si le writer est prêt et
   si cette action sert le diagnostic ou le retour à la normale.
8. Confirmer que le résultat business/runtime/recovery reste inchangé, quelle
   que soit la santé du canal.

Pour un motif précis, poursuivre dans
`02_DELIVERY_FAILURES_AND_BACKPRESSURE.md`.

## Flush

Le flush est caller/admin-owned, synchrone, borné et exécuté hors
`execute_cycle()`. Sans limite explicite, il utilise au plus
`policy.max_flush_items`. Un flush concurrent retourne immédiatement
`busy=True`. Le runtime ne lance jamais de flush automatique.

Chaque item dépilé reçoit au plus une tentative de write. Un échec arrête le
batch ; l'item tenté n'est pas requeue et les items non tentés restent FIFO.

## Actions autorisées

- désactiver ou activer explicitement un canal par composition ;
- ajuster la policy dans ses bornes, après validation de capacité ;
- remplacer le writer injecté par une implémentation conforme ;
- effectuer un flush explicite, synchrone et borné ;
- exécuter les tests observability et les tests d'équivalence runtime ;
- comparer des snapshots scalaires avant/après une action bornée.

## Actions interdites

- bloquer indéfiniment le runtime en attente de delivery ;
- créer un buffer non borné, une queue durable, une DB, SQLite ou WAL ;
- déclencher un retry ou replay métier pour récupérer une observation ;
- modifier `RunState`, snapshot, ledger, budget ou circuit breaker ;
- utiliser le health comme fait d'autorité ou critère de sécurité ;
- ajouter un flush automatique dans `execute_cycle()` ;
- réinjecter un échec de delivery dans le pipeline observability.

## Tests de vérification

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_observability_delivery_buffer.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_observability_failure_isolated_sinks.py
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_runtime_observability_integration.py
.\.venv\Scripts\python.exe -m pytest -q tests/architecture/test_observability_delivery_boundary_fitness.py
```

## Critères de retour à la normale

- le statut est `HEALTHY`, ou `DISABLED` si cette désactivation est voulue ;
- l'occupation reste sous les capacités et ne croît plus sans borne ;
- un flush borné livre les items attendus sans `SINK_FAILURE` ;
- les compteurs failed/rejected/dropped ne progressent plus sur la fenêtre de
  vérification ;
- le résultat runtime/recovery est identique à la baseline sans observability.

## Critères d'escalade

Escalader si une borne est contournée, si un canal bloque le runtime, si le
health influence une décision, si des observations sont persistées hors scope,
si un échec est observé récursivement, ou si le résultat métier/recovery varie
avec la configuration observability.

## Références techniques

- [ADR-P12-043](../../../architecture/adr/ADR-P12-043-observability-contract-boundary.md)
- [ADR-P12-047](../../../architecture/adr/ADR-P12-047-observability-delivery-failure-isolation.md)
- [Baseline delivery](../../development/PHASE_12_13_EXPORTERS_FAILURE_ISOLATION_BASELINE.md)
- [Delivery model](../../../backend/agent_runtime/observability/delivery_model.py)
- [Delivery policy](../../../backend/agent_runtime/observability/delivery_policy.py)
- [Buffers](../../../backend/infrastructure/observability/buffering.py)
- [Sinks](../../../backend/infrastructure/observability/sinks.py)
