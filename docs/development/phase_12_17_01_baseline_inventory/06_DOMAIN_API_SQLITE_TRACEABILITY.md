# Phase 12.17.1 — Traçabilité Domain, Application, API et SQLite

## Matrice initiale

| Concept | Domain / Application | Contrat API `/api/v2` | SQLite | État observé |
| --- | --- | --- | --- | --- |
| Notion | Module `knowledge_reference` structurel; pas de use case concret | Aucun endpoint matérialisé | `notion`, `notion_alias`, `object_registry` | Store OP-01 concret, chaîne Domain/API absente. |
| Document | Module `documents_provenance` structurel | Aucun endpoint matérialisé | `document`, migration SHA-256 001 | Store OP-02 concret; règle SHA locale; chaîne API absente. |
| Resource | `GetResourceQuery`, DTO, IP-03 et OP-03 | Identité documentaire `getResource`; aucun endpoint HTTP | `resource` via `ResourceStore` | Seule chaîne Application complète; C2 prouve SQLite réelle. |
| Pedagogical context | Module `pedagogical_context` structurel | Aucun endpoint matérialisé | `pedagogical_context`, `notion_context` | Store OP-04 concret; chaîne Domain/API absente. |
| Session / Task / Production | Module `work_orchestration` structurel | Aucun endpoint matérialisé | `session`, `task`, `production` | Store OP-05 concret; statuts codés dans l'adapter. |
| Validation | Module `validation_control` structurel | Aucun endpoint matérialisé | `validation_event` | Store OP-06 concret; chaîne Domain/API absente. |
| Quality evaluation | Module `quality_evaluation` structurel | Aucun endpoint matérialisé | `quality_evaluation`, `quality_framework_version` | Store OP-07 concret; chaîne Domain/API absente. |
| Promotion | Module `lifecycle_promotion` structurel | Aucun endpoint matérialisé | `production_resource_promotion` | Store OP-08 concret; chaîne Domain/API absente. |
| Audit event | Module `audit_traceability` structurel | Aucun endpoint matérialisé | `audit_event` | Store OP-09 concret; chaîne Domain/API absente. |
| Evidence/search | Agent runtime et ports Evidence | Aucun endpoint matérialisé | `search_chunk`, `content_notion`, `method_notion`, `resource_notion` et tables de référence | Chemin C1 concret via OP-11/OP-13, sans use case métier HTTP. |
| Semantic retrieval | Service/adapters semantic | Aucun endpoint matérialisé | Index dérivé `semantic_*` séparé | Backend technique concret, sans surface API. |

## Contraintes et invariants visibles

- `GetResourceRequest`, `ResourceRecord` et `ResourceView` exigent des chaînes non vides.
- Le bridge READ-15 accepte exactement `resource_ref` et refuse tout champ supplémentaire.
- L'absence de ressource produit `RES_NOT_FOUND`, bloquant et non retryable.
- Les connexions SQLite activent les clés étrangères; les connexions mutables ajoutent busy timeout et WAL.
- La migration 001 vérifie le format SHA-256 du document.
- Les migrations sont versionnées/checksummées dans `_runtime_migration_ledger` et les transactions utilisent `_runtime_operation_commit`.

## Limite de vérification

Le dépôt ne contient pas le DDL initial des `98` tables du seed canonique Phase 3. Il contient la migration corrective 001 et le code qui authentifie/copie ce seed externe. La matrice ci-dessus est donc construite depuis les stores, requêtes, tests SQLite et baselines C0/C1/C2; elle ne remplace pas une introspection complète du schéma source.

Cette absence empêche de conclure en 12.17.1 sur les colonnes sans usage, toutes les contraintes dupliquées ou l'exhaustivité des enums stockés. Le finding reste `CANDIDATE`; aucune migration n'est créée.
