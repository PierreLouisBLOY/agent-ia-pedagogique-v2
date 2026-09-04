# Phase 12.17.4 — Ownership des vocabulaires SQLite

## Frontière de preuve

La preuve 12.17.3D authentifie le seed
`38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`
et son DDL (`98/20/7/2`). Aucune ligne pédagogique n'a été exportée ou utilisée
pour inférer une sémantique. La compatibilité ci-dessous signifie donc
« acceptée par le DDL observé », pas « vocabulaire métier prouvé ».

```text
SQLITE_VOCABULARY_FAMILIES_MAPPED = 10/10
MIGRATION_REQUIRED_TRUE = 0
MIGRATION_REQUIRED_UNKNOWN_CANDIDATES = 2
```

## Matrice cible

| # | Famille observée | Owner bounded context | Type cible | Traduction adapter | Compatibilité physique | Migration requise |
|---:|---|---|---|---|---|---|
| 1 | Notion : `fr`, `CANONICAL` | `knowledge_reference` Domain | `KnowledgeLanguageCode` VO, `NotionIdentityStatus` Enum | mapping explicite vers `notion.language_code/identity_status` | défaut/check compatibles (`CANONICAL/MERGED/DEPRECATED/ARCHIVED`) | FALSE |
| 2 | Document : `OTHER`, `fr`, `ACTIVE` | `documents_provenance` Domain | `DocumentType`, `DocumentLanguageCode`, `DocumentStatus` | codecs fermés vers `document_type/language_code/document_status` | defaults concordants ; type/status sans CHECK | FALSE |
| 3 | Resource : `OTHER`, `CANONICAL` | `resource_library` Domain/Application | `ResourceType`, `ResourceIdentityStatus` | mapping du record/DTO vers `resource_type/identity_status` | valeurs acceptées, mais défaut physique `ACTIVE` face à insertion `CANONICAL` | UNKNOWN |
| 4 | Context : note `runtime` | `pedagogical_context` Application | `ContextOrigin` VO technique, distinct des notes pédagogiques | ne plus confondre origin et `notes`; projection contrôlée | `notes` nullable/non contrainte, aucune colonne source dédiée | UNKNOWN |
| 5 | Session : `ACTIVE` | `work_orchestration` Domain | `SessionLifecycleStatus` Enum | mapping exhaustif vers `session.lifecycle_status` | CHECK inclut `ACTIVE/PAUSED/COMPLETED/ARCHIVED` | FALSE |
| 6 | Task : `RUNTIME_CONTRACT`, `contract`, `COMPLETED` | `work_orchestration` Application | `TaskType`, `TaskObjectiveRef`, `TaskStatus` | commande Application fournit les valeurs, adapter encode | `COMPLETED` vérifié ; type/objectif acceptés sans CHECK | FALSE |
| 7 | Production : `OTHER`, `runtime production`, `VALIDATED` | `transformation_assembly` Domain/Application | `ProductionType`, `ProductionTitle`, `ProductionLifecycleStatus` | DTO de persistance dédié | lifecycle CHECK accepte `VALIDATED`; type/titre acceptés | FALSE |
| 8 | Validation : `RUNTIME_CONTRACT`, `PASS`, `sqlite adapter` | `validation_control` Domain/Application | `ValidationType`, `ValidationResult`, `ValidatorRef` | résultat du use case vers colonnes validation, sans autorité adapter | colonnes non-null, sans vocabulaire CHECK | FALSE |
| 9 | Qualité/promotion : `COMPLETED`, `1.0`, `PROMOTED`, `runtime contract` | `quality_evaluation` et `lifecycle_promotion` | `QualityEvaluationStatus`, `QualityScore`, `PromotionStatus`, `PromotionJustification` | deux mappers owners, jamais une famille partagée générique | defaults/colonnes acceptent les valeurs observées | FALSE |
| 10 | Audit : `RUNTIME_PORT_CONTRACT`, `sqlite adapter`, `{}` | `audit_traceability` Application | `AuditEventType`, `AuditActorRef`, `AuditPayload` | sérialisation sûre et bornée dans l'adapter audit | event non-null ; actor/payload/reason permissifs | FALSE |

Les types métier ne vont pas dans `backend/shared_kernel`. Les valeurs
techniques (`ContextOrigin`, `ValidatorRef`, `AuditActorRef`) restent des
contrats Application/adapter et ne deviennent pas des statuts métier.

## Deux candidats `UNKNOWN`

1. `resource.identity_status` : `ACTIVE` et `CANONICAL` peuvent désigner deux
   dimensions différentes. Le mapper doit être spécifié avant de décider si la
   colonne suffit ou si un modèle séparé est requis.
2. `pedagogical_context.notes` : stocker l'origine technique `runtime` dans une
   note mélange métadonnée et contenu. La première option est de ne plus
   persister ce default ; une colonne dédiée ne peut être décidée qu'avec un
   besoin produit explicite.

Ils sont des candidats d'analyse, pas des migrations approuvées. Si un schéma
change, un lot séparé doit prouver le besoin, proposer une migration additive,
la tester sur une copie runtime fraîche et obtenir une approbation. Le seed ne
sera jamais migré.

## Ordre de matérialisation futur

1. créer les vocabulaires dans chaque owner ;
2. créer les use cases/ports manquants, notamment CAP-R02, CAP-A01 et CAP-A02 ;
3. remplacer les littéraux des adapters par des mappings exhaustifs ;
4. interdire les stores génériques d'écriture depuis les entrées qui n'ont pas
   d'owner Application ;
5. exécuter les tests de mapping contre une copie runtime authentifiée ;
6. statuer séparément sur les deux `UNKNOWN`.

La gate 12.17.4E ne doit pas introduire d'enum SQLite comme owner, exposer une
`sqlite3.Row`, ou faire des defaults du seed une décision métier.
