# Observability — Privacy, sécurité et cardinalité

## Objet

Ce runbook permet de détecter, contenir et corriger une exposition de données
dans l'observabilité, une tentative de trace spoofing ou une dérive de
cardinalité, sans reproduire la donnée sensible ni conférer d'autorité à la
télémétrie.

## Périmètre

Le périmètre couvre les mappers logs/métriques, les contrats trace, les
serializers allowlistés, le catalogue métrique et les observations de
`SecurityEvent`. Les sources métier, politiques de sécurité et owners de
recovery restent hors de l'autorité observability.

## Invariants

```text
MINIMIZATION_BEFORE_REDACTION
NO_IMPLICIT_CONVERSION_FROM_TRACE_FLAGS
NO_IMPLICIT_CONVERSION_FROM_DELEGATION_TRACE_CONTEXT
METRIC_POINT_IS_NEVER_A_DECISION_FACT
DO_NOT_EXPORT_OPAQUE_METRIC_MAPPINGS_BY_DEFAULT
TRACE_SAMPLING_DOES_NOT_CONTROL_METRIC_COLLECTION
ONE_SECURITY_EVENT_OBSERVATION_PER_RUNTIME_EVENT
```

La minimisation se fait avant la sérialisation. La redaction tardive d'un
payload déjà copié n'est pas une stratégie acceptée.

## Données interdites

Ne jamais transporter dans log, span ou metric :

- raw prompt ;
- texte de document ou d'Evidence ;
- payload/output Tool, Application ou Agent ;
- réponse provider ;
- private reasoning ;
- secrets, credentials ou tokens ;
- `ErrorEnvelope.message` ou `ErrorEnvelope.details` ;
- `SecurityEvent.metadata` brute ;
- chemins privés ou locaux ;
- clés d'idempotence brutes.

Les références opaques et attributs fermés ne sont admis que par les mappers et
serializers allowlistés.

## Triggers et symptômes

- une valeur sensible ou un chemin privé apparaît dans un record sérialisé ;
- un mapper accède à un payload, output, message/details ou metadata brute ;
- un descriptor ou label métrique est créé dynamiquement ;
- un identifiant à forte cardinalité apparaît dans les labels ;
- un mapping legacy modifie le `TraceContext` canonique ;
- le health ou une métrique influence une décision runtime/security/recovery ;
- un même `SecurityEvent` est observé plusieurs fois.

## Données sûres à examiner

Examiner le channel, type/code fermé, mapper/serializer concerné, noms de champs
allowlistés, descriptor catalogué, noms/valeurs de labels fermés, taille du
record et IDs opaques déjà autorisés par le contrat. Pour reproduire, utiliser
exclusivement les fixtures synthétiques de test.

Ne jamais copier une valeur suspecte dans un ticket, une capture, un nouveau
log, un test ou ce runbook.

## Procédure d'incident privacy

1. Ne pas reproduire la valeur sensible dans une nouvelle observation.
2. Identifier le channel et le type/code d'observation.
3. Identifier le mapper puis le serializer allowlisté qui ont construit le
   record.
4. Désactiver explicitement le channel par composition si nécessaire pour
   contenir l'exposition.
5. Confirmer que cette désactivation ne modifie pas le runtime outcome.
6. Si une correction de code est nécessaire, ouvrir un lot séparé ; ne pas
   patcher silencieusement pendant l'incident.
7. Rejouer les tests privacy avec des fixtures uniquement synthétiques.

Une vraie valeur secrète ne doit jamais être introduite dans un ticket,
runbook, test ou message de diagnostic.

## Cardinalité

La baseline fermée est :

```text
Metric catalog = 14 metrics
theoretical series = 285
MAX_SERIES_PER_DESCRIPTOR = 256
MAX_CATALOG_SERIES = 512
```

Chaque `MetricPoint` runtime doit référencer un descriptor de `METRIC_CATALOG`
et utiliser exactement ses labels allowlistés. Aucun descriptor runtime ne peut
être dérivé d'un contenu, mapping ou fournisseur.

Labels interdits :

- `run_id`, `step_id`, `correlation_id` ;
- `trace_id`, `span_id` ;
- `invocation_id`, `delegation_id`, `record_id` ;
- `refs` ;
- URL ou path ;
- contenu ou donnée provider.

Les mappings `metrics` opaques transportés par des sources historiques ne sont
pas exportés automatiquement.

### Diagnostic de cardinalité

1. Résoudre le descriptor dans `METRIC_CATALOG`.
2. Comparer l'ensemble exact des labels avec `allowed_labels`.
3. Vérifier que chaque valeur appartient au vocabulaire fermé du mapper.
4. Vérifier les bornes par descriptor et du catalogue.
5. Rechercher toute construction dynamique de nom/descriptor/label.
6. Vérifier que le sampling trace ne supprime ni n'ajoute une métrique.

## Trace spoofing

```text
ContractMeta.trace_flags = legacy opaque
DelegationEnvelope.trace_context = legacy opaque
```

Ces deux mappings sont conservés pour compatibilité de contrat mais ne sont
jamais parsés ou convertis vers `TraceContext`. Le root est fourni explicitement
par le caller ; les enfants sont créés par la policy de trace à partir du parent
canonique.

Si un mapping legacy contient des IDs vraisemblables, ils restent des données
opaques et ne remplacent jamais trace ID, span ID, parent ou sampling.

## SecurityEvent

La metadata brute de `SecurityEvent` n'est pas loggée. Le mapper n'en extrait
que les champs sûrs explicitement autorisés. Chaque événement runtime est
observé une fois au niveau du controller wrapper.

Un échec de serializer, buffer, sink ou writer ne génère jamais un nouveau
`SecurityEvent`. Le health observability ne devient jamais un fait de sécurité.

## Procédure de diagnostic

1. Classer l'incident : privacy, cardinalité, spoofing ou duplication.
2. Contenir le channel concerné si une donnée peut encore sortir.
3. Inspecter uniquement code, schémas, allowlists et fixtures synthétiques.
4. Vérifier l'owner de l'émission et l'absence d'un second point d'observation.
5. Comparer le résultat runtime avec observability disabled et healthy.
6. Exécuter les tests ciblés ci-dessous.
7. N'autoriser le retour que si les critères objectifs sont remplis.

## Actions autorisées

- désactiver temporairement un canal par composition ;
- inspecter catalogues, allowlists et snapshots scalaires ;
- reproduire avec valeurs synthétiques explicitement fausses ;
- ouvrir un lot correctif séparé et minimisé ;
- resserrer un mapper à la source dans ce futur lot ;
- vérifier le compte exact d'observations security.

## Actions interdites

- copier, hasher ou fingerprint une vraie valeur sensible ;
- dumper payload, output, metadata, exception ou source brute ;
- créer descriptor ou label dynamique ;
- placer un ID dynamique dans les labels ;
- parser un contexte legacy vers `TraceContext` ;
- utiliser métrique, health ou sampling comme autorité ;
- produire un `SecurityEvent` en réponse à un échec de delivery.

## Tests de vérification

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_error_structured_log_mapper.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_security_structured_log_mapper.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_metric_catalog_and_policy.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_metric_mappers.py
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_trace_legacy_compatibility.py
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_runtime_observability_integration.py
.\.venv\Scripts\python.exe -m pytest -q tests/architecture/test_metric_cardinality_boundary_fitness.py
```

## Critères de retour à la normale

- aucune valeur interdite n'apparaît dans les records réellement sérialisés ;
- les tests privacy passent avec fixtures synthétiques ;
- les 14 descriptors et les 285 séries théoriques restent inchangés ;
- aucun label dynamique ou ID de run/trace/span n'est présent ;
- les mappings legacy restent opaques ;
- chaque `SecurityEvent` possède exactement une observation ;
- runtime, security et recovery produisent les mêmes résultats.

## Critères d'escalade et STOP

STOP et traiter comme incident bloquant si un secret ou chemin réel est
sérialisé, si un descriptor/label dynamique apparaît, si un mapping legacy
contrôle la trace, ou si telemetry health influence une autorité security ou
runtime.

## Références techniques

- [ADR-P12-044](../../../architecture/adr/ADR-P12-044-structured-logging-minimization.md)
- [ADR-P12-045](../../../architecture/adr/ADR-P12-045-trace-context-propagation.md)
- [ADR-P12-046](../../../architecture/adr/ADR-P12-046-metric-catalog-cardinality.md)
- [Baseline structured logging](../../development/PHASE_12_13_STRUCTURED_LOGGING_BASELINE.md)
- [Baseline trace](../../development/PHASE_12_13_TRACING_PROPAGATION_BASELINE.md)
- [Baseline metrics](../../development/PHASE_12_13_METRICS_BASELINE.md)
- [Log mapper](../../../backend/agent_runtime/observability/log_mapper.py)
- [Metric catalog](../../../backend/agent_runtime/observability/metric_catalog.py)
- [Serialization](../../../backend/infrastructure/observability/serialization.py)
