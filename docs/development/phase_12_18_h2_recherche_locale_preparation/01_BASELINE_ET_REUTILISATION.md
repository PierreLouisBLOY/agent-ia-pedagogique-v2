# Baseline et réutilisation — préparation de recherche locale

Statut : PROPOSED_NOT_APPROVED. PROPOSITION_COMPLETE désigne uniquement le paquet documentaire ; IMPLEMENTATION_AUTHORIZED = FALSE. Les intitulés de cet incrément et des futurs fichiers sont des propositions organisationnelles, pas des identifiants canoniques retrouvés.

## 1. Binding d’entrée vérifié statiquement

| Élément | Valeur constatée |
| --- | --- |
| HEAD | 3f724ca81843b5d45ac534e9654ff16281c55713 |
| Incrément livré | H2_READ15_LOCAL_STDLIB_V1 |
| ZIP reçu, SHA-256 | 0b67c668b2534288ab3bd8b04162a31591f95c3a01180b47f64137d59368d5fd |
| Manifest READ-15 | 0b21d5ed85751b89c8bd55182392a2de99507b817d351a8211ba9834f54eddb7 |
| Vérification du manifest READ-15 | 20 entrées conformes aux fichiers de la baseline d’entrée |
| IMPLEMENTATION_EVIDENCE.md | 979732d0b5ae8996b4eafae51df3550b63e5f0308125321d66cbd3af22d86b5b |
| Contrat READ15_HTTP_LOCAL_V1.json | 7bee880ab6a982e520d3ca69284d1d311789b8e32397d1f26c25dcd217934d7a |
| ADR-P12-069 accepté | 8970146f2561b91cc999e18f7faa11ccc305b7b1415091f455358d361d7dda9d |
| Index Git à l’entrée | Vide ; aucun staging effectué |
| Delta technique à l’entrée | Aucun |
| Untracked préexistants | Seulement les deux dossiers H1/H1A, 11 documents protégés conformes |

Les 11 chemins et hashes H1/H1A sont reproduits dans 03_INVENTAIRE_FICHIERS_ET_GUARDS.json. Ils restent byte-identiques et hors du diff/commit futur proposé. Les six sorties de cette préparation n’appartiennent pas au snapshot initial ; leur ajout ne justifie pas un rebind des manifests historiques.

La preuve READ-15 conserve un statut LOCAL_COMMIT_PENDING et une baseline PRE 24b7a9850bc4644391dee2307c8a8a31036cd503 : elle a été écrite avant commit. Le commit d’entrée et le manifest vérifié établissent le binding livré ; ce résidu pré-commit est signalé, non réécrit. A7 est réellement appliqué dans la baseline : le contrôle ResourceRef n’interdit plus globalement HTTP, il impose exactement les quatre routes READ-15/assets.

## 2. Preuves historiques, pas nouvelles exécutions

La preuve d’implémentation rapporte 186 tests ciblés réussis, puis 5043 passed / 28 skipped / 0 failed dans la suite autorisée, et un stress lifecycle 12/12. Elle rapporte également mypy sur 688 fichiers et les contrôles lint/compilation/dépendances. Ces nombres ne sont ni régénérés, ni comptés comme tests de recherche locale.

Le premier lancement historique de suite a atteint un contrôle is_file() du chemin seed/runtime par défaut avant de s’arrêter : accès de métadonnée consigné, sans ouverture SQLite réelle. Il n’est pas masqué par le résultat de la suite corrigée et n’est pas reproduit. Le gate réel reste NOT_RUN / NOT_PASS dans le périmètre reçu. Le fichier tests/non_functional/test_retrieval_quality_real_gate.py n’est pas inoffensif en l’absence de flag : sa fonction appelle load_sqlite_paths(os.environ), puis seed_path.is_file(). La préparation ne l’exécute ni ne l’importe.

## 3. Sources pertinentes et chronologie

- H1A, 03_PAQUET_DECISION_ET_PLAN_H2.md, §3 REC-02/SCN-02 : composants retrieval/SQLite présents, besoin de contrat/projection/provenance et composition produit. §4 : données réelles non vérifiées, droits séparés. §5 : aucune clôture H2/H3 déduite.
- H1A, 01_SOURCES_ET_ECARTS_RECONCILIES.json : supersession de l’admission STRUCTURED-only par F2A ; disponibilité distincte de canonicalité ; I04/I06/I08 et sources absentes toujours limitants. Ses états historiques « serveur absent » ne décrivent pas HEAD après READ-15.
- H1, 03_ETAT_INTEGRATION_PRODUIT.md et 04_ECARTS_ET_PREPARATION_RECETTE.json : lignes retrieval, REC-02 et distinctions preuve/doubles/recette ; pas de réaudit des 33 exigences.
- architecture/adr/ADR-P12-057-sqlite-evidence-port-integration.md : OP-11/OP-13 et contenu non fiable.
- architecture/adr/ADR-P12-061-retrieval-admissibility-decoupling.md : admission indépendante avant utilisation/fusion ; rang et appartenance à un canal ne confèrent pas l’autorité.
- architecture/adr/ADR-P12-062-semantic-retrieval-embedding-index.md : la présence d’un index local ne rend pas le query embedding implicitement offline.
- ADR-P12-069, contrat actif READ-15, tests A1–A7, AGENTS.md et docs/development/ENVIRONMENT.md : frontières, réseau/SQLite, validation et hygiène.

Les sept annexes Phase 8 et l’original précis 12.1 ne sont ni recherchés à nouveau ni recréés. Le contrat proposé n’est pas présenté comme l’OpenAPI original. Les sources ci-dessus suffisent à préparer une disposition bornée ; elles ne démontrent pas une conformité exhaustive aux 54 opérations historiques.

## 4. Disponibilité réelle des composants

| Segment / symbole constaté dans le source | État | Réutilisation et limite |
| --- | --- | --- |
| frontend/index.html, app.js, styles.css | Présents, à adapter | UI READ-15 et rendu textContent ; aucun formulaire recherche existant |
| backend/adapters/inbound/api/routes.py : resolve_route(method, target) -> RouteMatch | Présent, à adapter | Registre fermé de quatre routes ; tout query actuellement refusé ; exception ciblée à proposer pour la nouvelle route |
| backend/adapters/inbound/api/server.py : LocalRead15Service.respond(...) | Présent, à adapter | Host/Origin, corrélation, assets, endpoint READ-15 ; nouveau dispatch injecté requis |
| backend/adapters/inbound/application/resource_library.py : ResourceLibraryUseCaseInbound.invoke(*, request) | Présent, conservé | Seul application.read_canonical_resource accepté ; ne sait pas rechercher |
| M03 : GetResourceQuery.get_resource(*, request, correlation_id) | Présent, conservé | Lecture ResourceRef via ResourceStorePort ; pas de recherche produit |
| M03 : use case / port de recherche | Absents à développer | Nouveau SearchLocalQuery et contrats neutres, pas un simple câblage d’un use case déjà disponible |
| backend/adapters/outbound/search/sqlite.py : BusinessSearchAdapter.search(text, *, limit=5) -> tuple[SearchHit, ...] | Présent, raccordable | FTS5 paramétré, CURRENT, registre, NOTION CANONICAL, bm25 puis sc.id ; limit 1..100 ; tous types d’objets |
| backend/adapters/outbound/evidence/sqlite.py : SQLiteEvidenceSearchAdapter.search(*, query, channel) | Présent, raccordable | LEXICAL sans backend sémantique ; DTO RetrievalCandidate agent, pas DTO M03/HTTP |
| Même fichier : is_admissible(*, candidate, query) -> bool | Présent, à réutiliser obligatoirement | Source policy, active, autorité/provenance, checksum, passage courant ; vérification indépendante du canal STRUCTURED |
| backend/adapters/outbound/document_content/sqlite.py : DocumentContentAccessAdapter.read_passage(passage_ref) | Présent, raccordable | Fragment CURRENT avec object id / passage / checksum / texte ; seulement après admission |
| backend/adapters/outbound/resource_library/sqlite.py : SQLiteResourceStoreAdapter.load_resource(ResourceRef) | Présent, raccordable | OP-03 pour le mapping exact objet RESOURCE vers READ-15, sans SQL dupliqué |
| backend/infrastructure/composition/factories/local_browser.py : build_local_read15(configuration, target) | Présent, à adapter | Target explicite + hash + lecteur readonly ; pas de loader ambient/provisioning ; futur reader recherche par requête |
| backend/infrastructure/observability/operational.py | Présent, conservé | Le champ route_template admet /api/v2/search sans query ; aucune nouvelle famille ni politique de logs nécessaire |

Les signatures sont lues dans les fichiers, pas obtenues par import. Les SHA PRE du code utilisé sont dans le JSON d’inventaire.

## 5. Point central : un hit n’est pas une ressource

SearchHit.entity_ref est l’object_id du registre ; passage_ref est l’id du chunk ; version_or_checksum est chunk_hash. Attention : SearchHit.entity_kind désigne chunk_type, tandis que registry_object_type donne le type d’objet. Le pont Evidence les expose séparément en provenance.object_kind et provenance.chunk_type. Un RetrievalCandidate ne contient pas le snippet : OP-13 doit fournir le texte après admission.

Les types peuvent inclure NOTION, PEDAGOGICAL_CONTENT et RESOURCE. Un passage ou une notion ne se convertit pas en ResourceRef par préfixe, titre ou analogie. Proposition : résultat de passage explicite, avec ouverture seulement si object_kind == RESOURCE, ResourceRef(object_ref) valide et GetResourceQuery trouve exactement cette référence sur la même cible. Aucun parcours relationnel ou jointure notion-vers-ressource nouveau.

## 6. Faisabilité et limites de readiness

Une recherche lexicale locale est faisable avec les composants réels ; cela reste une conclusion de lecture statique, pas une preuve d’exécution sur la bibliothèque utilisateur. Aucun besoin identifié de package, nouvel index, migration, provider ou query embedding. OP-11/OP-13/OP-03 existants ne sont pas modifiés ; un pont outbound nouveau traduit leurs résultats et conserve F2A.

Le choix M03 pour l’ownership d’une découverte de passages menant à ResourceRef est NOUVEAU et proposé à l’approbation, non attribué à un document canonique absent. L’Application n’importe pas agent_runtime ; seul le pont outbound traduit les contrats techniques existants. Aucun quatorzième module créé.

La recherche n’implémente pas le parcours complet AG-02 hybride/RRF ni les workflows pédagogiques. La séparation CAP-R02 → CAP-A01 → CAP-A02 reste intacte. Une ressource non indexée peut ne jamais apparaître ; disponibilité du schéma FTS5 et lien RESOURCE ne sont pas prouvés sur les données réelles.

## 7. Contrôles de cette préparation

Lecture statique, SHA-256 des documents/sources, JSON, inventaire, UTF-8/LF et diff seulement. Aucun test technique, serveur, socket, SQLite, accès seed/runtime même de métadonnée, credential, réseau ou opération Git mutante. Les tests/lint/typecheck/compile applicatifs sont NOT_RUN ici par le mandat documentaire, et restent obligatoires avant toute réussite du futur incrément.
