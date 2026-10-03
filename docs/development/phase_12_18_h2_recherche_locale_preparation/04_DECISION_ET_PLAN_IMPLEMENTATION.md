# Décision et plan d’implémentation proposés

PROPOSED_NOT_APPROVED. IMPLEMENTATION_AUTHORIZED = FALSE.
Aucune attestation, signature, approbation ou date propriétaire n’est préremplie. Le prochain geste est une décision sur CE paquet complet, pas une série de sous-gates.

## 1. Recommandation unique soumise ensemble à décision

Adopter SEARCH-HTTP-LOCAL-1.0, règles P01..P15 du document 02 : GET /api/v2/search?q=...&limit=..., recherche LEXICAL de passages admis F2A, limite 10 par défaut/20 maximum et fenêtre 100, extrait 320 points de code, ouverture READ-15 conditionnelle avec preuve exacte. Développer le use case M03 et le pont outbound, sans modification d’OP-11/OP-13/OP-03, des contrats agents, de ResourceRef ni des politiques de canonicalité.

Accepter ENSEMBLE les 30 fichiers et les évolutions G01..G04/U01 ci-dessous, les tests positifs/négatifs, les permissions synthétiques/loopback, le nouvel ADR descriptif et un seul commit local cohérent après contrôles. Il ne s’agit pas d’une autorisation de fichiers sans leurs assertions exactes, ni de guards sans fonctionnalité.

Écart assumé par rapport à « trouver toute ressource » : seuls les passages déjà indexés sont recherchables ; un résultat non-RESOURCE reste non ouvrable. Cette proposition ne cache pas cet écart derrière un faux ResourceRef. M03 comme owner de la découverte bornée est une décision NOUVELLE de ce paquet, pas une assertion de source canonique antérieure.

Aucun arbitrage indispensable laissé indéterminé : choix recommandé fermé. La décision d’implémenter reste requise. En cas de désaccord sur ce comportement, réviser le même paquet avant code.

## 2. Fichiers exacts du futur incrément

30 fichiers : 20 CREATE et 10 MODIFY. Parmi eux : 15 fichiers production/assets (9 nouveaux, 6 modifiés), 11 fichiers de tests (7 nouveaux, 4 modifiés), 1 nouvel ADR et 3 nouvelles preuves/contrats. Aucun __init__.py à modifier : imports directs des nouveaux modules. Aucun lock/config/CLI, schéma SQL, migration, historique ou source utilisateur.

Les SHA PRE des dix fichiers modifiés et les responsabilités détaillées figurent dans le JSON. null pour une création veut dire « aucun fichier existant à la baseline », pas « hash non contrôlé ». Toute préexistence inattendue lors de la reprise bloque ce chemin sans écrasement.

| # | Action | Chemin relatif au dépôt | Responsabilité |
| --- | --- | --- | --- |
| 01 | MODIFY | `backend/adapters/inbound/api/routes.py` | Registre fermé cinq routes ; décodage borné uniquement sur /api/v2/search. |
| 02 | MODIFY | `backend/adapters/inbound/api/server.py` | Dispatcher un endpoint de recherche injecté, erreurs minimisées ; sécurité et serveur unique inchangés. |
| 03 | MODIFY | `backend/infrastructure/composition/factories/local_browser.py` | Composer la recherche par inbound Application et adapters existants ; ouverture readonly explicite par requête. |
| 04 | MODIFY | `frontend/index.html` | Ajouter formulaire recherche et liste accessible ; conserver la consultation READ-15. |
| 05 | MODIFY | `frontend/app.js` | GET recherche same-origin, textContent, annulation ; ouvrir seulement les références prouvées via READ-15. |
| 06 | MODIFY | `frontend/styles.css` | Styles locaux de la recherche dans l’asset existant. |
| 07 | MODIFY | `tests/architecture/test_local_browser_product_boundary.py` | G01/G02 : helpers du registre et inventaire fermé ; tests/contre-exemples existants conservés. |
| 08 | MODIFY | `tests/architecture/test_resource_ref_contract_fitness.py` | G03 : seule assertion ROUTE_SPECS de l’ancien A7 ; autres assertions conservées. |
| 09 | MODIFY | `tests/architecture/test_security_recovery_observability_e2e_fitness.py` | G04 : ajout exact des nouveaux owners M03/inbound à la seule assertion concernée. |
| 10 | MODIFY | `tests/unit/test_local_browser_product_routes.py` | U01 : cardinalité 4 vers 5 ; tous les tests et autres assertions conservés. |
| 11 | CREATE | `backend/modules/resource_library/domain/value_objects/search_text.py` | SearchText et erreur de validation ; normalisation Unicode et tokens sans HTTP/SQL. |
| 12 | CREATE | `backend/modules/resource_library/application/dto/input/search_local.py` | SearchLocalRequest text typé et limit 1..20. |
| 13 | CREATE | `backend/modules/resource_library/application/dto/output/local_search_view.py` | Vues bornées passage/provenance/ouverture ; aucun type agent, HTTP ou SQLite. |
| 14 | CREATE | `backend/modules/resource_library/application/queries/search_local.py` | SearchLocalQuery ; admission via port puis liaison ResourceRef via READ-15 Application. |
| 15 | CREATE | `backend/modules/resource_library/ports/inbound/local_search.py` | LocalSearchInbound Protocol ; recherche typée avec CorrelationId. |
| 16 | CREATE | `backend/modules/resource_library/ports/outbound/local_search.py` | LocalSearchPort, AdmittedLocalPassage et fenêtre de candidats ; contrat neutre. |
| 17 | CREATE | `backend/adapters/inbound/application/local_search.py` | application.search_local_passages via UseCaseRequest/Result ; mapping fermé. |
| 18 | CREATE | `backend/adapters/outbound/search/local.py` | Pont vers OP-11 LEXICAL, admission F2A puis OP-13 ; aucun provider, aucune écriture. |
| 19 | CREATE | `backend/adapters/inbound/api/search.py` | SearchEndpoint : invocation injectée et projection JSON bornée ; sans accès M03/SQL. |
| 20 | CREATE | `tests/unit/test_local_search_text.py` | Cas Unicode, tailles, ponctuation, FTS littéral. |
| 21 | CREATE | `tests/unit/test_local_search_application.py` | Doubles de ports : admissions, bornes, ordre et liaison READ-15 conditionnelle. |
| 22 | CREATE | `tests/unit/test_local_search_http_projection.py` | Projection et erreurs sans fuite ; interdiction de types/champs supplémentaires. |
| 23 | CREATE | `tests/unit/test_local_search_routes.py` | Paramètres, décodage, limites et méthodes de la seule nouvelle route. |
| 24 | CREATE | `tests/integration/test_local_search_sqlite.py` | FTS5/OP-11/OP-13/OP-03 sur fixture synthétique hors dépôt ; lecture seule. |
| 25 | CREATE | `tests/integration/test_local_search_http.py` | Chaîne HTTP loopback réelle, recherche puis READ-15, sécurité, arrêt et confidentialité. |
| 26 | CREATE | `tests/architecture/test_local_search_product_boundary.py` | Non-régression exacte G01..G04/U01 ; port M03, absence SQL HTTP/provider/semantic et mutations négatives. |
| 27 | CREATE | `architecture/adr/ADR-local-lexical-search-product-boundary.md` | Nouvel ADR proposé ; adoption uniquement après décision propriétaire. ADR-P12-069 intact. |
| 28 | CREATE | `docs/development/phase_12_18_h2_local_search/SEARCH_HTTP_LOCAL_V1.json` | Contrat actif futur dérivé sans changement sémantique de cette proposition approuvée ; inventaire exact. |
| 29 | CREATE | `docs/development/phase_12_18_h2_local_search/IMPLEMENTATION_EVIDENCE.md` | Preuves réelles et périmètre des tests futurs ; aucune réussite présumée. |
| 30 | CREATE | `docs/development/phase_12_18_h2_local_search/MANIFEST_SHA256.txt` | Empreintes des preuves futures, sans auto-référence. |

Le nom du nouvel ADR est proposé sans numéro canonique inventé. Il sera relu/adopté seulement dans l’exécution autorisée ; ADR-P12-069 reste intact. Aucun fichier supplémentaire implicite. Une nécessité découverte hors inventaire est rapportée avec le besoin exact, pas intégrée silencieusement.

Les six fichiers du présent paquet sont des entrées documentaires protégées, pas des créations du futur incrément. Les 11 documents H1/H1A et les manifests historiques restent hors commit proposé.

## 3. Guards et assertions : aucun A7 oublié

| Id | Fichier / nodeid ou helper | Changement proposé borné |
| --- | --- | --- |
| G01 | test_local_browser_product_boundary.py : route_contract_violations ; test_approved_registry_and_frontend ; test_a7_closed_registry_rejects_extra_routes_outside_or_inside_registry | Oracle littéral fermé de quatre à cinq routes, SEARCH_TEMPLATE reconnu par AST, nouveau contrat actif ; assertions positives/négatives des tests conservées |
| G02 | même fichier : inventory_violations ; test_inventory_survives_staging_and_updated_head | Baseline de diff 3f724ca... distincte de BASELINE historique ; tuple littéral des 30 paths ; protection hashée des 11 H1/H1A + six pièces de préparation |
| G03 | test_resource_ref_contract_fitness.py : test_read15_keeps_one_field_and_deprecations_without_http_implementation | Seule assertion ROUTE_SPECS == tuple remplacée par le tuple précis de cinq routes ; six assertions précédentes et autres tests inchangés |
| G04 | test_security_recovery_observability_e2e_fitness.py : test_later_provider_work_preserves_phase_f_backend_owners | Ajout exact de huit chemins M03/inbound à l’assertion all existante ET contrôle G02 conservé |
| U01 | test_local_browser_product_routes.py : test_registry_has_one_business_operation_and_three_assets | Seul len(ROUTE_SPECS) == 4 devient == 5 ; test et autres assertions inchangés |

Cela représente quatre évolutions de guards dans trois fichiers d’architecture et une assertion dans un fichier unitaire. G01/G02 font évoluer les helpers sous les assertions existantes ; ne pas les présenter comme deux simples lignes supprimées. Les expressions PRE/POST, SHA PRE complets et nodeids de non-régression proposés sont dans le JSON.

Les anciens guards B04 (A1..A4) et B03 (A5) sont relus et affectés indirectement par leur délégation mais NON modifiés. L’ancien contrôle F/A6 et ResourceRef/A7 sont explicitement couverts par G04/G03. Aucun contrôle de serveur/framework/SQL/API/asset ne disparaît.

Préserver test_existing_pure_contracts_and_original_guards_other_tests_preserved et ses comparaisons AST sur BASELINE=24b7a... ; ne pas substituer HEAD à cette preuve. Introduire _SEARCH_BASELINE=3f724ca... pour le nouvel inventaire seulement. Le nouveau guard verrouille également les autres fonctions des quatre fichiers modifiés contre la baseline d’entrée, à l’exception exacte G01..G04/U01, sans skip/xfail ni liste d’exceptions globale.

L’ancien manifest READ-15 est un snapshot historique. Ses entrées dont le code évolue par l’allowlist se vérifient sur les blobs Git de 3f724ca... après implémentation ; ne pas réécrire le manifest pour lui faire décrire le nouvel incrément. Les documents historiques eux-mêmes et les fichiers réutilisés hors allowlist restent byte-identiques.

## 4. Scénarios futurs — décrits, NON exécutés

Les nouveaux noms de tests ci-dessous sont des spécifications, pas des tests déjà présents ou réussis.

| Groupe / fichier futur | Cas positifs et négatifs à exécuter après approbation |
| --- | --- |
| test_local_search_text.py | NFC/français, apostrophes, séparateurs ; 256/257 caractères, 12/13 tokens, 64/65 par token, vide, contrôles/bidi/surrogates ; OR littéral et ponctuation sans injection |
| test_local_search_routes.py | q/limit exacts, UTF-8, +, ordre des clés ; clés inconnues/dupliquées/encodées, % invalide/double, limit 0/21/bool textualisé, body, slash final, query toujours interdit sur READ-15/assets, HEAD/POST refusés |
| test_local_search_application.py | Ordre et fenêtre, zéro résultat, refus d’admission ; RESOURCE présent/absent/ref invalide et non-RESOURCE non ouvrables ; mismatch d’identité, résultat inconnu et absence de publication de score |
| test_local_search_http_projection.py | Enveloppe/champs/corrélation fermés ; sortie >64 KiB, ids illégaux, erreur technique != vide, exception sans fuite, extrait 320/321, contenu HTML affichable seulement comme texte |
| test_local_search_sqlite.py | Petite fixture FTS5 avec object_registry, search_chunk, notion et resource selon les adapters actuels ; LEXICAL-only admis sans STRUCTURED, CURRENT vs ancien, NOTION non CANONICAL, mauvais hash ; OP-13 après admission seulement ; bm25/sc.id stables ; 100 candidats et limit ; schéma/FTS absent échoue 500 |
| test_local_search_http.py | Chaîne réelle UI-assets/HTTP/inbound/use case/ports/adapters synthétiques ; recherche puis GET READ-15 pour sélection ; non ouvrable sans requête READ-15 ; Host/Origin invalides ; métadonnées/logs minimisés ; panne sink ; port occupé ; stop, restart, requête lente et flush |
| test_local_search_product_boundary.py | G01..G04/U01 et contre-exemples exacts ; pas de route sixième/dupliquée/méthode nouvelle ; pas de nouveau backend hors allowlist ; SQL HTTP/imports agent dans M03 refusés ; aucune validation par rang ni accès provider/semantic ; préservation des anciennes assertions |

Compléments obligatoires dans ces fichiers (aucun fichier de support supplémentaire) :

- Base synthétique créée dans un NOUVEAU répertoire temporaire système hors dépôt, aucune copie d’une vraie base. Fermeture de l’initialisation puis hash explicite avant lecture ; schéma de fixture conforme aux SQL lus, pas d’autodétection de bibliothèque utilisateur.
- Trois adapters sur la même connexion readonly/query_only et transaction de lecture ; tentatives d’écriture refusées ; fichiers/sidecars synthétiques PRE/POST inchangés pendant la phase de lecture. Nettoyage limité aux fixtures créées, jamais un chemin utilisateur calculé.
- Validation invalide avant tout target.validate ; garde espion des fonctions de path/loader/open sur les chemins utilisateur ; imports et construction d’objets sans accès de métadonnées à ces chemins. Aucun faux is_file sur un chemin réel « pour vérifier ».
- Désactiver les interfaces d’accès externe/credentials par doubles de refus pour les tests concernés ; aucun appel réseau autre que boucle locale explicitement testée.
- Absence de q/tokens/extrait/titre/références/SQL/chemin dans les événements et erreurs, y compris mauvais Host, timeout et panne technique. Template routier seulement.
- Occuper puis libérer un port loopback de test et vérifier fermeture des ressources ; 12 cycles de stress local proposés, ne pas réutiliser le 12/12 historique comme preuve de recherche.
- Répéter deux recherches identiques sur le même snapshot : ordre/provenance identiques, corrélations distinctes. Suppression d’une ressource entre recherche et ouverture dans une NOUVELLE phase d’écriture de fixture, jamais pendant le reader : READ-15 retourne RES_NOT_FOUND normalement.

Réutiliser intégralement les fichiers existants, sans modification :

- tests/unit/test_local_browser_read15_http.py ;
- tests/integration/test_local_browser_read15_http.py (budget target/headers/deadline, sécurité, application réellement traversée, tamper, IPv6) ;
- tests/integration/test_local_browser_product_composition.py (read-only, mauvais hash, absence target, port occupé, stop/flush et CLI minimisée) ;
- guards ResourceRef, M03, F2A, Evidence, semantics, contrats canoniques, B03/B04 et hygiène énumérés dans le JSON.

### Trois niveaux de preuve distincts

1. Technique Python/HTTP/SQLite synthétique : pytest exécute effectivement Application et adapters, et sert les trois assets ; cela ne prouve pas un clic navigateur.
2. UI statique : inventaire et interdits JS/HTML, textContent et absence de CDN/storage/logging ; aucun faux résultat « UI automatisée PASS ». Pas de dépendance navigateur nouvelle ni automatisation UI requise par l’allowlist.
3. Recette manuelle navigateur locale : proposée après tests sur le même hôte/fixture synthétique, par le propriétaire ou avec son autorisation d’outil navigateur. Saisie, résultat vide, non ouvrable, sélection READ-15, clavier/aria-live, erreur visible et absence de trafic externe. Si non réalisée, UI_MANUAL_ACCEPTANCE = NOT_RUN ; ne pas prétendre que le trajet interactif complet a été recetté. Ce n’est pas H3 ni une recette de données réelles.

## 5. Permissions futures à approuver explicitement

La décision d’exécution demandera, dans un seul accord lié au manifest de ce paquet et à HEAD :

- Les 30 créations/modifications exactes, uniquement selon le contrat proposé ; nouvel ADR relu avant implémentation.
- Écritures d’initialisation/teardown sur petites fixtures SQLite SYNTHÉTIQUES et logs/caches temporaires hors dépôt ; ensuite lecteurs query_only et hash explicite. Pas de copie de seed ni runtime utilisateur.
- Sockets HTTP TCP sur 127.0.0.1 / ::1 seulement, ports temporaires explicites, pour les tests et éventuelle recette manuelle synthétique. Aucune connexion externe, DNS, fournisseur, accès package index ou crédit B05 réutilisé.
- Configuration du processus de validation seulement, environnement enfant minimal sans settings seed/runtime/credentials hérités et sans loader de découverte. Aucun affichage de leurs valeurs.
- Tests, lint, typecheck, compilation et pip check avec dépendances déjà disponibles ; caches et JUnit privés hors dépôt.
- Un commit LOCAL cohérent des 30 fichiers exacts après contrôles réussis, fonctionnalité + tests/guards + ADR/preuves réunis. Aucun commit préalable de neutralisation de guard.

Interdictions maintenues : seed/runtime utilisateur et leurs sidecars, y compris exists/stat/hash ; migration, configuration persistante, provider/credential, nouvelle dépendance/lock, réseau externe, sources/manifest historiques, push, merge, H3. L’accès futur à la bibliothèque réelle exige une autorisation séparée portant sur une cible exacte.

## 6. Ordre de réalisation proposé après décision

1. Vérifier HEAD=3f724ca... et tous SHA PRE/inputs de la décision par lecture de dépôt seulement ; tolérer les 11 H1/H1A et six pièces préparatoires hashées, rejeter tout delta technique inattendu. Aucun reset/stash/clean.
2. Relire la décision et le nouvel ADR dans le scope adopté. Matérialiser le contrat actif et son inventaire fermé. Conserver le contrat READ-15 historique.
3. Développer SearchText, DTO/ports, use case M03, pont réutilisant admission/OP-13, inbound, endpoint, dispatch/factory et UI dans la même unité cohérente. Ne pas déplacer du SQL vers HTTP pour limiter l’inventaire.
4. Faire évoluer uniquement G01..G04/U01 et écrire les nouvelles non-régressions avant de déclarer l’incrément fonctionnel.
5. Exécuter les contrôles ciblés positifs ET négatifs, puis la suite autorisée proportionnée et les outils ENVIRONMENT.md ; écrire les résultats réels, séparer les niveaux de recette.
6. Vérifier diff/allowlist/anciens hashes/assertions, absence runtime/secret, fermeture des ressources, puis commit local explicite des 30 paths, sans git add global. H1/H1A et la préparation restent des entrées protégées hors commit. Vérifier post-commit par diff de baseline fixe et index vide ; ne pas déclarer le dépôt propre en ignorant les untracked protégés.
7. Arrêter sur un échec ; diagnostiquer dans le périmètre, sans exclusion/skip/xfail de masquage ni élargissement. Reprise sur les mêmes preuves/identités ; aucun rerun fournisseur possible. Maintenir CAP-R02 → CAP-A01 → CAP-A02 hors cet incrément.

### Validation globale future : périmètre honnête

ENVIRONMENT.md impose Python 3.12, pytest, ruff, mypy backend, compileall et contrôle des dépendances. Cette proposition ne les exécute pas. À l’exécution : utiliser les outils installés, PYTHONDONTWRITEBYTECODE=1, pytest -p no:cacheprovider, basetemp/caches/JUnit externes ; compileall avec PYTHONPYCACHEPREFIX externe ; ruff --no-cache ; mypy --cache-dir externe. Aucune installation ni mise à jour.

Avant la suite, lire statiquement les conditions d’accès réel des tests/config de collecte. Le fichier tests/non_functional/test_retrieval_quality_real_gate.py accède au chemin par défaut même sans flag : le plan propose explicitement --ignore=tests/non_functional/test_retrieval_quality_real_gate.py pour la seule suite SYNTHETIC_AUTHORIZED. Ce n’est ni un changement de test, ni une suppression de guard, ni un PASS de la suite exhaustive. Le propriétaire approuve cette délimitation de données en même temps que les droits de test. Le gate réel demeure NOT_RUN / NOT_PASS. Les autres tests réels à activation explicite ne sont pas activés ; reporter leurs skips existants honnêtement.

Si l’examen révèle un autre accès non conditionnel à des données réelles, ne pas lancer la suite et ne pas ajouter une exclusion implicite : rapporter ce fichier et son besoin précis. Les tests de l’incrément et les guards concernés ne sont jamais exclus. Un succès de suite synthétique n’autorise pas à annoncer la suite avec seed réussie.

## 7. Statuts de sortie attendus, sans les fabriquer

Aujourd’hui : PROPOSITION_COMPLETE = TRUE ; IMPLEMENTATION_AUTHORIZED = FALSE ; PROVIDER_CALLS = 0 ; SQLITE_ACCESS = 0 ; USER_DATA_METADATA_ACCESS = 0 ; SOCKETS_OPENED = 0 ; TECHNICAL_TESTS = NOT_RUN ; GIT_MUTATION = NONE ; H3_STARTED = FALSE.

Futur, uniquement sur résultats exécutés : implementation technique, scénarios synthétiques, lint/typecheck/compile, diff/hygiène et recette UI séparément. REAL_SEED_GATE reste NOT_RUN / NOT_PASS dans ce scope. Aucune clôture H2, H3, Phase 12 ou projet n’est déduite d’un test de recherche réussi.

Le hash du paquet décisionnel est le SHA-256 du fichier MANIFEST_SHA256.txt couvrant les cinq pièces. Il est communiqué hors de ces pièces pour éviter toute auto-référence. Une décision future lie ce hash à la baseline et au périmètre complet ci-dessus ; ce document n’est pas cette décision.
