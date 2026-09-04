# Phase 12.17.4 — Graphe runtime et tooling actif

## Base et méthode

La cartographie porte sur la baseline `6d0d66380757d7502fd967cd0246c5b6ff91d5f8`.
Elle combine l'inventaire 12.17.1, la portée mypy 12.17.2/12.17.2A, les imports
statiques observés et les manifests 12.16. Une catégorie principale est affectée
à chaque groupe ; une propriété secondaire signale les placements incorrects ou
les liaisons par hash.

Un fichier n'est déclaré `DEAD_OR_UNREACHABLE` que si l'absence de tout appel est
prouvée. L'absence d'endpoint ou le caractère squelettique d'un module ne suffit
pas à le déclarer mort.

## Comptes de référence

| Périmètre Python | Fichiers | Catégorie principale | Base de classement |
|---|---:|---|---|
| `backend/**/*.py` | 659 | `ACTIVE_RUNTIME` | portée mypy runtime et imports backend |
| `evaluation_harness/**/*.py` | 30 | `ACTIVE_TOOLING` | bibliothèque offline utilisée par les évaluations |
| `tests/calibration/pedagogical/**/*.py` | 50 | `HISTORICAL_EVIDENCE` ou `TEST_ONLY` | chaîne fermée 12.16 et tests associés |
| `tests/providers/anthropic/**/*.py` | 6 | `HISTORICAL_EVIDENCE`, `TEST_ONLY` ou `LEGACY_COMPAT` | provider de calibration 12.16 placé sous tests |
| `scripts/` et `tools/` | 0 | sans objet | aucun de ces répertoires n'existe sur la baseline |

`ACTIVE_RUNTIME_FILES = 659` et `ACTIVE_TOOLING_FILES = 30`. Ces comptes sont des
comptes de paquets complets, fichiers `__init__.py` inclus, cohérents avec la
portée de validation existante. Ils ne prétendent pas que les 659 fichiers
portent tous une implémentation : 12 modules métier sur 13 restent principalement
structurels.

## Graphe observé

```text
backend
  -> backend.modules / backend.agent_runtime / backend.shared_kernel
  -> backend.adapters / backend.infrastructure
  -X-> evaluation_harness
  -X-> tests

evaluation_harness
  -> stdlib
  -> backend.shared_kernel._value_safety
  -X-> backend.infrastructure / backend.agent_runtime / tests / provider SDK

tests/calibration/pedagogical
  -> evaluation_harness
  -> backend provider-neutral configuration
  -> backend OpenAI adapters
  -> tests/providers/anthropic          [historical operational tooling]

tests/providers/anthropic
  -> evaluation_harness contracts
  -> backend provider-neutral configuration/secrets
```

Les recherches d'imports ne trouvent aucun import `tests.*` depuis `backend` ou
`evaluation_harness`. La dette est dans le sens tooling historique vers les
packages actifs, pas dans le runtime produit.

## Fichiers runtime pertinents

| Fichier/groupe | Classe | Rôle prouvé | Disposition de design |
|---|---|---|---|
| `backend/agent_runtime/**/*.py` | `ACTIVE_RUNTIME` | agents, ports Generation/Review, security, recovery, observability | conserver les frontières Phase 6/11 |
| `backend/modules/resource_library/**/*.py` | `ACTIVE_RUNTIME` | seule tranche Domain/Application concrète end-to-end | owner du READ-15 |
| `backend/modules/{knowledge_reference,documents_provenance,pedagogical_context,work_orchestration,transformation_assembly,validation_control,quality_evaluation,lifecycle_promotion,audit_traceability}/**/*.py` | `ACTIVE_RUNTIME` | bounded contexts présents, majoritairement structurels | futurs owners des vocabulaires, aucune autorité déduite des squelettes |
| `backend/adapters/inbound/application/resource_library.py` | `ACTIVE_RUNTIME` | frontière inbound vers `GetResourceQuery` | future API doit l'appeler, jamais le repository directement |
| `backend/adapters/inbound/api/__init__.py` | `ACTIVE_RUNTIME` | package sans endpoint matérialisé | API différée à 12.17.5 |
| `backend/adapters/outbound/openai/{contracts,schema,transport}.py` | `ACTIVE_RUNTIME` | transport OpenAI commun de production | reste sous backend |
| `backend/adapters/outbound/generation/openai/{mapping,adapter}.py` | `ACTIVE_RUNTIME` | implémentation `GenerationPort` | reste sous backend |
| `backend/adapters/outbound/review/openai/{mapping,adapter}.py` | `ACTIVE_RUNTIME` | implémentation `ReviewPort` | reste sous backend |
| `backend/adapters/outbound/semantic/{contracts,index,service,openai}.py` | `ACTIVE_RUNTIME` | recherche sémantique et adapter OpenAI | hors rationalisation de calibration |
| `backend/infrastructure/config/{schemas,loaders,effective_config,secrets}/**/*.py` | `ACTIVE_RUNTIME` | configuration provider-neutral et secrets redacted | source de configuration injectée, jamais de secret sérialisé |
| `backend/infrastructure/composition/factories/{openai,semantic,sqlite}.py` | `ACTIVE_RUNTIME` | composition explicite | aucune route 12.16 ne devient une autorité métier |
| `backend/adapters/outbound/{persistence,transaction,search,read_models,document_content,evidence,resource_library}/**/*.py` | `ACTIVE_RUNTIME` | seed/runtime SQLite et ports outbound | seed immuable, SQL confiné aux adapters |

## Fichiers tooling pertinents

| Fichier/groupe | Classe | Justification |
|---|---|---|
| `evaluation_harness/contracts/**/*.py` | `ACTIVE_TOOLING` | contrats offline provider-neutral acceptés par ADR-P12-049 |
| `evaluation_harness/{runner,scoring,assertions,reporting}/**/*.py` | `ACTIVE_TOOLING` | exécution, scoring, assertions et rendu offline |
| `tests/calibration/pedagogical/test_*.py` | `TEST_ONLY` sauf liaison historique explicite | tests de preuves et réconciliations 12.16 |
| `tests/calibration/pedagogical/*.py` versionnés V2/V3/V4/V5.x | `HISTORICAL_EVIDENCE` | plans, corpora, runners et parsers de la phase fermée 12.16 |
| `tests/calibration/pedagogical/__init__.py` | `LEGACY_COMPAT` | réexport historique du catalogue ; ne doit pas devenir une API active |
| `tests/providers/anthropic/{contracts,mapping,scorer,transport}.py` | `HISTORICAL_EVIDENCE` | octets utilisés par les preuves/calculs 12.16 |
| `tests/providers/anthropic/test_transport.py` | `TEST_ONLY` | test du transport historique |
| `tests/providers/anthropic/__init__.py` | `LEGACY_COMPAT` | package historique |

`tests/providers/anthropic/transport.py` et
`tests/providers/anthropic/scorer.py` sont en outre les deux
`MISPLACED_IMPLEMENTATION` : ils réalisent un tooling provider opérationnel,
mais restent immuables à leur emplacement pour la preuve passée.

## Reachability et absence de reclassement intuitif

- Les stores d'écriture génériques de `persistence/sqlite.py` sont atteints par
  `SQLiteUnitOfWork` et les gates réelles C0 ; ils sont donc `LEGACY_COMPAT`, pas
  morts, tant que leurs owners Application ne sont pas matérialisés.
- Les runners V4/V5.x ont eu des points d'entrée et ont produit des preuves ; ils
  sont `HISTORICAL_EVIDENCE`, même si aucune autorisation live n'est active.
- Aucun fichier pertinent n'est classé `UNKNOWN` : tous les groupes ont une
  preuve de package, d'import, de test ou de manifest.
- Aucun fichier n'est classé `DEAD_OR_UNREACHABLE` dans cette gate. Une future
  suppression exige une preuve d'absence d'import et une vérification des hashes.

## Graphe cible résumé

```text
backend product runtime --------------------X--------------------> tests
evaluation_harness provider-neutral --------X--------------------> tests
calibration_tooling (nouveau, offline) ------> evaluation_harness
calibration_tooling -------------------------> config/secrets injectés
calibration_tooling.adapters.anthropic ------> port de scoring
tests ---------------------------------------> tous les packages ci-dessus
historical V4/V5.x --------------------------X--------------------> graphe actif
```

Le nouveau package est un objectif d'une future exécution, pas un changement de
ce lot de design.
