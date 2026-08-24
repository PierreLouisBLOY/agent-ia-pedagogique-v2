# Structure du depot

Cette baseline materialise sans logique metier la structure normative issue de la Phase 6.15.

## Correspondance des zones

| Zone reelle | Responsabilite canonique |
| --- | --- |
| `backend/shared_kernel/` | Primitives techniques generiques partagees |
| `backend/core_contracts/` | Frontieres contractuelles transverses futures |
| `backend/modules/` | Coeur metier decoupe en M01 a M12 et MX1 |
| `backend/adapters/inbound/` | Entrees API, UI locale, CLI, outils agents et batch |
| `backend/adapters/outbound/` | Integrations sortantes futures |
| `backend/infrastructure/` | Configuration, composition et observabilite |
| `tests/` | Tests par niveau et par frontiere |
| `architecture/adr/` | Decisions d'architecture explicites |

Les repertoires sont des frontieres et des emplacements reserves. Les marqueurs `__init__.py` ne contiennent aucune logique metier.

## Modules canoniques

| Code | Repertoire |
| --- | --- |
| M01 | `knowledge_reference` |
| M02 | `documents_provenance` |
| M03 | `resource_library` |
| M04 | `pedagogical_design` |
| M05 | `transformation_assembly` |
| M06 | `analysis_simulation` |
| M07 | `pedagogical_context` |
| M08 | `work_orchestration` |
| M09 | `validation_control` |
| M10 | `quality_evaluation` |
| M11 | `lifecycle_promotion` |
| M12 | `materialization_export` |
| MX1 | `audit_traceability` |

Chaque module porte les memes sous-frontieres `domain/`, `contracts/`, `ports/` et `application/` definies par la Phase 6.15. Aucun adaptateur ni element d'infrastructure n'est place sous un module.

## Regle de dependance

Le metier reste local a son module. Le shared kernel demeure generique. Les adaptateurs consomment les ports et use cases prevus; les outils agents entrent uniquement par `backend/adapters/inbound/agent_tools/`. Les contrats restent independants de HTTP, d'un ORM et des SDK fournisseurs.

Les repertoires globaux `backend/domain/`, `backend/repositories/` et `backend/services/` sont interdits. Les tests de `tests/architecture/` gardent cette baseline sans anticiper les fitness functions completes des phases suivantes.
