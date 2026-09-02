# Phase 12.17.1 — Inventaire architecture et runtime

## Runtime agent

| Package | Fichiers Python | Responsabilité observée |
| --- | ---: | --- |
| `agents` | 34 | Evidence, génération, review et coordination. |
| `application_routing` | 5 | Routage exact-match vers les inbounds Application. |
| `contracts` | 60 | Contrats neutres, statuts, sécurité, planning et observabilité. |
| `gates` | 5 | Autorité et résolution fail-closed. |
| `observability` | 16 | Logs, traces, métriques et delivery. |
| `orchestration` | 14 | Compilation, sélection, workflows et coordination. |
| `policy` | 9 | Capability, délégation, scope et appels d'outil. |
| `recovery` | 22 | Retry, budget, circuit breaker, replay, ledger et snapshot. |
| `registry` | 5 | Agents, capabilities, outils et matrice d'accès. |
| `runtime` | 24 | Exécution, routing, scheduling et état. |
| `sandbox` | 5 | Modèle et policy de chemins/opérations. |
| `security` | 7 | Isolation de contenu, valeurs sensibles et composition. |
| `tools` | 4 | Registry/routing des outils. |
| `versioning` | 5 | Politique et vocabulaire de versions de contrats. |

`RoutingStepRunner`, `RecoveryAwareStepRunner` et `ObservedStepRunner` forment des wrappers distincts. Les tests de frontière confirment que `backend/agent_runtime` n'importe directement ni SQLite, ni adapters, ni SDK OpenAI/Anthropic.

## Adapters et gateways

Les adapters outbound concrets couvrent notamment :

- SQLite : persistence, transaction, search, read models, document content, evidence, resource library et index sémantique;
- OpenAI : transport Responses partagé, génération, review et embeddings;
- matérialisation/delivery/events : packages structurels ou interfaces selon le sous-domaine.

Les huit imports `sqlite3` du backend sont tous sous `backend/adapters/outbound`. Les imports SDK OpenAI sont limités à `backend/adapters/outbound/openai/transport.py` et `backend/adapters/outbound/semantic/openai.py`. Aucun import direct adapter/infrastructure n'a été détecté sous `backend/modules`.

La composition concrète est regroupée dans trois factories : `sqlite.py`, `semantic.py` et `openai.py`. Les packages `bindings`, `bootstrap` et `readiness` ne contiennent que leur `__init__.py`.

## Retrieval

Le chemin concret documenté et implémenté est :

```text
EvidenceAgent -> RetrievalCoordinator -> EvidenceSearchPort
-> SQLiteEvidenceSearchAdapter -> BusinessSearchAdapter -> SQLite
-> SQLiteEvidenceDocumentContentAdapter -> DocumentContentAccessAdapter
```

Le semantic backend utilise une base SQLite dérivée avec `semantic_index_metadata`, `semantic_vector` et `semantic_rollup`. Sa composition peut utiliser le service d'embedding OpenAI, mais aucun appel n'a été ouvert pendant cet audit.

## Surface Application et API

Un seul inbound Application concret existe : `ResourceLibraryUseCaseInbound`, lié à READ-15/getResource. Le package `backend/adapters/inbound/api` ne contient qu'un `__init__.py` structurel. Il n'existe donc aucun router HTTP ou endpoint `/api/v2` inspectable dans la baseline actuelle.

## Harness et branches historiques

`evaluation_harness` contient `29` fichiers fonctionnels répartis entre assertions, contracts, reporting, runner et scoring, plus son package racine. Les helpers pédagogiques sous `tests/calibration/pedagogical` contiennent `50` fichiers et `11` points d'entrée `main`.

Composants versionnés candidats à rationalisation :

- `live_runner.py` et `live_runner_v4_1.py`;
- `semantic_parser_adapter_v5_1.py`;
- `semantic_gate_v5_2.py`;
- `pairwise_runner_v5_2_2.py`;
- `pairwise_output_contract_v5_2_3.py` et `pairwise_output_contract_v5_2_4.py`;
- `tests/providers/anthropic/{transport,scorer}.py`, utilisés pour la calibration mais rangés sous tests.

Ces composants peuvent être légitimes comme preuves immuables de version. Leur duplication n'est donc qu'un candidat jusqu'à l'audit 12.17.4.
