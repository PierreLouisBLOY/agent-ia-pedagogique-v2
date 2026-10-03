# ADR-P12-069 — Proposition de frontière produit HTTP locale READ-15

Statut : **PROPOSED / NOT_APPROVED**. Version de proposition : 1.0.
Baseline examinée : `24b7a9850bc4644391dee2307c8a8a31036cd503`.
Emplacement actuel : ce document H1A uniquement. Aucun ADR accepté n'est modifié.
Inventaire local : ADR-P12-001 à 068 ; 069 libre au contrôle. Revérifier avant promotion.

## 1. Décision proposée et justification

Proposition unique `H2_READ15_LOCAL_STDLIB_V1` : autoriser, après revue propriétaire, un hôte HTTP local dédié, une seule opération métier READ-15 et trois assets same-origin. Les handlers passent par une frontière inbound Application existante ; seule la composition assemble les ports et adaptateurs. Aucun SQL, repository, provider ou secret dans HTTP/UI ; aucun framework dans Domain/Application.

Ce n'est pas une permission générale de serveur ni une livraison de toute V2. Phase 8 décrit 54 opérations et 11 écrans ; les sept annexes distinctes de son §18 restent introuvables dans la recherche bornée. Le contrat proposé `READ15-HTTP-LOCAL-1.0` sera nouveau, limité et explicitement approuvé ; il ne sera pas présenté comme l'OpenAPI original.

Fondements consultés, identités dans [la matrice](01_SOURCES_ET_ECARTS_RECONCILIES.json) :

- EXT-S06, zones Z07 et Z10, §13, F6-14/F6-15 : adaptateurs protocole entrants et composition prévus ; invariants non désactivables par configuration.
- EXT-S08, §§4–5, 8, 11, 14, 17–18 : surface API, erreurs, UI et sécurité spécifiées ; implémentation HTTP future, framework non choisi.
- EXT-S11 : agent sans accès SQL/filesystem métier/secrets, sans autorité de promotion ; choix techniques restant à l'implémentation.
- EXT-S13 : navigateur local accepté, non preuve d'implémentation, ni approbation de cette évolution.
- `docs/development/phase_12_17_08_b04_local_browser_http_fail_closed/01_B04_SCOPE_RESOLUTION.md`, `07_FRONTEND_LOCAL_BROWSER_ASSUMPTIONS.md` et `08_IMPLEMENTATION_EVIDENCE.md` dans ce même dossier : B04 livrait un contrat pur, excluait serveur/socket/routes/frontend et préparait leur raccordement futur.
- `architecture/adr/ADR-P12-001-python-runtime-baseline.md` : Python 3.12 ; absence de framework runtime dans le lot 12.2, pas interdiction perpétuelle d'adaptateur HTTP.

Conclusion motivée : l'absence globale est une restriction des lots historiques, non un invariant architectural général des Phases 6/8. Son évolution exige néanmoins une décision explicite ; H1A ne l'applique pas.

## 2. Identités et portée réelle des guards

Les trois fichiers et leurs derniers commits sont :

- `tests/architecture/test_local_browser_http_boundary_fitness.py`
  SHA-256 : `d324d383351cce3039225a8439338f6059abbd2b34bebf286b0e29b8933d56e6` ; dernier commit : `b63a1463046141512739e4c8f4618ab967002c78`.
- `tests/architecture/test_minimal_local_observability_fitness.py`
  SHA-256 : `87adef3498b85d2bf9f9c462b8b493b29b4d6a474c36976ba775297fde249d7e` ; dernier commit : `2650ae7616fc7067e6c6341f854a10efee633d6f`.
- `tests/architecture/test_security_recovery_observability_e2e_fitness.py`
  SHA-256 : `9b7d9a25430a41dd5a1c6696b11d582dbfe37d7b5cf425ccc0946d6baf37b501` ; dernier commit : `b63a1463046141512739e4c8f4618ab967002c78`.

Helpers : les trois fichiers parcourent l'AST ; `Import` produit `alias.name`, `ImportFrom` produit `node.module`. Le premier agrège tous les imports backend, sans exception de chemin. Le second cible notamment `BOOTSTRAP = backend/infrastructure/composition/bootstrap/observability.py`. Le troisième dispose aussi de `_python_files` et interroge le diff Git courant.

### 2.1 Six assertions, quatre nodeids

Les nodeids ci-dessous sont complets. Les autres assertions de ces tests et les autres tests des fichiers restent actifs.

| Référence | Nodeid et assertion actuelle | Remplacement proposé | Invariant préservé |
| --- | --- | --- | --- |
| A1 | `tests/architecture/test_local_browser_http_boundary_fitness.py::test_b04_adds_no_http_server_framework_or_route` : aucun import commençant par aiohttp, fastapi, flask, http.server, hypercorn, starlette, uvicorn dans tout backend | Six familles tierces toujours interdites partout ; `http.server` autorisé uniquement dans `backend/adapters/inbound/api/server.py`. Conserver attribution par fichier, pas agrégation perdant la localisation. | Aucun framework dans le métier ; aucun autre hôte HTTP. |
| A2 | Même nodeid : aucun fichier API nommé `server.py` ou `routes.py` | Chemins de ces deux noms exactement ceux listés au §4 ; aucun second emplacement/sous-dossier. | Composition produit bornée, pas découverte dynamique de routes. |
| A3 | Même nodeid : aucune chaîne `/api/v2` dans l'arbre API | Registre fermé au §3, déclaration seulement dans `routes.py` ; AST/contrat et dispatch testés ensemble. Pas simple exemption du fichier au scan. | Une seule opération, aucune route supplémentaire. |
| A4 | `tests/architecture/test_local_browser_http_boundary_fitness.py::test_b04_adds_no_frontend_public_url_or_drive_runtime_dependency` : `assert not (ROOT / "frontend").exists()` | Inventaire récursif exact des trois assets du §4, imports/requêtes seulement same-origin, aucune résolution distante. | Les trois autres assertions no Drive, no wildcard bind, no adresse LAN demeurent. |
| A5 | `tests/architecture/test_minimal_local_observability_fitness.py::test_http_observability_adds_no_server_framework_or_route` : absence globale de `api/server.py` | Le bootstrap observabilité ne doit importer, construire ni binder le serveur ; assemblage uniquement dans la factory produit. | Assertions `http_request` et absence de frameworks dans BOOTSTRAP inchangées ; observabilité indépendante du transport. |
| A6 | `tests/architecture/test_security_recovery_observability_e2e_fitness.py::test_later_provider_work_preserves_phase_f_backend_owners` : tout fichier backend changé doit appartenir aux exceptions existantes | Ajouter seulement les quatre chemins entrants API/CLI du §4 à un ensemble explicite H2. Conserver toutes les exclusions d'owners et compléter par le nouvel inventaire architectural borné. | Pas de nouveau préfixe permissif, ni droit métier supplémentaire. |

A6 utilise `git diff --name-only HEAD -- backend` : les nouveaux fichiers non suivis n'y apparaissent pas. Le futur contrôle doit vérifier leur inventaire indépendamment et l'ensemble du diff approuvé avant/après commit ; un commit ou l'état untracked ne doit jamais contourner ce test.

Exceptions A6 déjà présentes : préfixes `backend/adapters/outbound/`, `backend/infrastructure/composition/factories/`, `backend/infrastructure/config/` ; ensembles F2A de cinq fichiers, B02 de trois, B03 de cinq et B04 de deux (`api/__init__.py`, `api/local_browser.py`). Ces permissions historiques ne sont pas des autorisations H2 : l'inventaire H2 sera plus étroit, exact et complémentaire.

### 2.2 Assertions durables inchangées

Maintenir notamment `test_b04_contract_has_no_provider_database_repository_or_business_dependency` : interdiction des imports API `anthropic`, `backend.adapters.outbound`, `backend.modules`, `calibration_tooling`, `openai`, `sqlite3`. Le transport délègue à `backend/adapters/inbound/application/resource_library.py`, sans importer le domaine pour contourner cette règle. La composition hors API construit et injecte l'inbound/les ports ; pas d'accès SQL derrière un helper de handler.

Maintenir les autres tests B03/B04/F : loopback, rejets non locaux, CORS, erreurs minimisées, corrélation B03 sans second générateur, schéma d'événements allowlisté, stockage local privé, absence de provider/réseau dans l'observabilité, agents sans décisions de gate/promotion, recovery sans fabrication de permissions, catalogue et owners protégés.

Aucune suppression globale, skip, xfail, exclusion mypy, wildcard de chemins, import dynamique de contournement, ni flag « autoriser serveur ». Les nouveaux tests négatifs vérifient les contre-exemples par fixtures AST isolées, sans modifier le code produit pour la démonstration.

## 3. Contrat courant et delta proposé

### 3.1 Contrat B04 repris sans modification

Sources actuelles :

- `backend/adapters/inbound/api/local_browser.py` : `cc7ee88ebbb41d17feb301c9707d1ab05efe3d1fa3118be8612c1b4c735d1148`.
- `backend/infrastructure/config/schemas/http.py` : `511336250f3a3274fe4f2f17f328771111250b0ec916a4e18723abc6b4ecf298`.

Bind par défaut `127.0.0.1` ; valeurs autorisées `127.0.0.1` et `::1`. Port obligatoire, entier non booléen, de 1 à 65535, sans défaut implicite. Hosts autorisés : localhost, 127.0.0.1, ::1. IPv6 entre crochets traité par le parseur ; port Host explicite différent rejeté, mais le contrat actuel accepte l'absence de port Host : ne pas lui attribuer une obligation inexistante.

Origins CORS vides par défaut, méthodes CORS `("GET",)`, headers CORS `("x-correlation-id",)`. Credentials, debug, reload, docs et sessions stateful à False et valeurs permissives rejetées. Aucun wildcard ; origines locales contrôlées, aucune autorisation cookie/proxy-auth/authorization implicite.

GET/HEAD admis par la frontière ; autres méthodes refusées, hors OPTIONS de preflight strict lorsqu'une configuration CORS l'autorise. Dans l'incrément proposé, CORS reste vide : pas de preflight ouvert. Origin absente admise, Origin présente validée par le contrat ; Host et Origin évalués avant toute action Application.

`SanitizedHttpError.as_mapping()` produit uniquement `status`, `error_code`, `correlation_id`. Codes fermés : ALLOWED, HOST_REJECTED, ORIGIN_REJECTED, METHOD_REJECTED, PREFLIGHT_REJECTED, INTERNAL_ERROR. Réutiliser `correlation_id`, `http_request`, `security_rejected` de B03. Aucun prompt, payload, réponse brute, chemin, query, référence métier brute, secret ou exception textuelle dans les logs.

OBS_A inchangée : NDJSON local, rotation 5 MiB, cinq fichiers, rétention 14 jours, flush/arrêt borné à deux secondes. Pas de télémétrie distante.

### 3.2 Nouveau contrat borné, encore NON APPROUVÉ

| Méthodes et route exacte | Destination | Limite |
| --- | --- | --- |
| GET `/api/v2/resources/{resource_ref}` | READ-15 existant via inbound Application | Seule opération métier ; aucun query parameter, body, version_ref ou include. |
| GET/HEAD `/` | `frontend/index.html` | Asset fixe, jamais chemin filesystem fourni par le client. |
| GET/HEAD `/assets/app.js` | `frontend/app.js` | Asset fixe, même origine. |
| GET/HEAD `/assets/styles.css` | `frontend/styles.css` | Asset fixe, même origine. |

HEAD sur l'API serait refusé 405 ; permission globale GET/HEAD n'impose pas HEAD pour chaque route. Toute autre route refusée ; ni /health supplémentaire, /docs, /openapi, /orchestrate, route générique, commande HTTP ou exposition de répertoire. HEAD ne rend aucun corps.

ResourceRef conserve le contrat existant ASCII `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`, sans double décodage ni acceptation de slash encodé. Le métier reste l'owner de sa validation ; le transport ne déduit aucun ID numérique/canonicalité. Le bridge appelle `application.read_canonical_resource` avec seulement `resource_ref`. La factory fournit les métadonnées Application attendues, sans laisser un header navigateur fabriquer une permission ou une décision de gate.

Enveloppe nouvelle à approuver selon EXT-S08 §5 : succès 200 `data` contenant exactement resource_ref, resource_type, canonical_title, availability_status et `meta.correlation_id`. Pas de canonicality ajoutée. Échec : `error` avec catégorie fermée et code public, `meta.correlation_id` ; pas de message d'exception. BusinessError, ValidationIssue et ApplicationFailure restent distincts ; un échec Application ne doit pas être converti en succès vide.

Projection proposée : 404/RES_NOT_FOUND pour absence métier ; 400/READ15_REQUEST_REJECTED pour requête/validation invalide ; 404/ROUTE_NOT_FOUND pour route inconnue ; 405/METHOD_REJECTED ; 403 pour les rejets Host/Origin/preflight ; 500/INTERNAL_ERROR pour échec technique. Les catégories business/validation/transport/security/technical sont explicites dans le nouveau contrat, pas présentées comme déjà implémentées. La couche d'enveloppe consomme la projection minimisée B04 sans modifier ce contrat pur.

## 4. Inventaire futur exact et choix technique proposé

Tous les chemins de création ci-dessous sont absents au contrôle H1A. Cette liste n'est pas un diff exécuté.

| Fichier à créer après approbation | Responsabilité |
| --- | --- |
| `backend/adapters/inbound/api/server.py` | Hôte stdlib HTTPServer + BaseHTTPRequestHandler dédié, seule importation de http.server. |
| `backend/adapters/inbound/api/routes.py` | Registre exact ci-dessus, résolution sans accès fichier arbitraire. |
| `backend/adapters/inbound/api/read15.py` | Décodage borné, invocation inbound et projection des résultats. |
| `backend/adapters/inbound/cli/local_browser.py` | Point d'entrée explicite sans effet à l'import ; affiche l'URL, arrêt contrôlé. |
| `backend/infrastructure/composition/factories/local_browser.py` | Assemblage Application/ports/runtime autorisée/observabilité/hôte ; aucun owner nouveau. |
| `frontend/index.html` | Formulaire ResourceRef et résultat READ-15, sans prétendre couvrir 11 écrans. |
| `frontend/app.js` | Fetch same-origin, encodage de référence, rendu textContent et erreur publique. |
| `frontend/styles.css` | Styles locaux, sans import/CDN. |

Choix proposé, pas décision déjà canonique : Python 3.12 stdlib et HTML/CSS/JS sans nouvelle dépendance. Aucun framework tiers, npm, CDN, téléchargement, modification des trois locks ou de la configuration persistante. Une autre stack demanderait une décision technique explicite et, si nécessaire, une nouvelle autorisation de résolution réseau ; B05 n'est pas réutilisable.

Pas de SimpleHTTPRequestHandler, CGI, auto-index, logs stdlib de requêtes brutes ni attribut Server dévoilant les versions. Hôte mono-requête à la fois, connexion HTTP/1.0 fermée ; pas de threads non bornés. Limites proposées : cible de requête 8 KiB, headers agrégés 64 KiB, timeout socket 5 s, body refusé. Ce sont des paramètres nouveaux proposés, non une garantie acquise de la stdlib. Les tests devront démontrer l'application avant parsing/dispatch ; autrement NO_GO, sans fallback permissif. Host dupliqué/manquant ou ambigu, cible absolue, traversal, double encodage, framing ambigu et Content-Length/Transfer-Encoding incompatibles rejetés. La version IPv6 doit être sélectionnée explicitement si bind ::1 ; aucun élargissement d'adresse automatique.

Ce choix est une proposition de petit hôte local, pas une recommandation de déploiement public ni une certification de sécurité de la bibliothèque.

Modifications futures : uniquement les trois guards §2 et les six assertions décrites. Aucun changement prévu dans Domain/Application, contrats B04, bootstrap observabilité, migrations, config, agent_runtime, provider, locks ou guards historiques hashés.

Créations de tests proposées :

- `tests/architecture/test_local_browser_product_boundary.py`
- `tests/unit/test_local_browser_product_routes.py`
- `tests/unit/test_local_browser_read15_http.py`
- `tests/integration/test_local_browser_product_composition.py`
- `tests/integration/test_local_browser_read15_http.py`

Documents futurs : `architecture/adr/ADR-P12-069-local-browser-read15-product-boundary.md` seulement après approbation ; dans `docs/development/phase_12_18_h2_local_read15/`, `READ15_HTTP_LOCAL_V1.json`, `IMPLEMENTATION_EVIDENCE.md`, `MANIFEST_SHA256.txt`. Aucun fichier futur ne reçoit de hash inventé dans H1A. Tout besoin d'élargir cet inventaire exige de revenir à la revue de portée, pas un ajustement silencieux.

## 5. Preuves futures exigées

Les tests ci-dessous sont **à implémenter/exécuter après approbation**, zéro exécution technique H1A.

| Axe | Positif | Négatif / absence de contournement |
| --- | --- | --- |
| Architecture | http.server seulement dans le serveur ; factory assemble inbound Application et port READ-15 | Import serveur/framework dans Domain/Application ou autre fichier refusé ; SQL/repository/provider dans handler refusé, y compris import relatif/dynamique de contournement. |
| Inventaire/route | Les quatre routes et les trois assets exacts fonctionnent ; inventaire untracked compris | Deuxième serveur, route non listée, asset supplémentaire, source UI externe, owner agent modifié : échec. |
| Frontière | Configuration loopback/port/Host/Origin B04 et corrélation B03 réutilisées | Wildcards, LAN, Host dupliqué, mauvais port, origin externe, debug/docs/reload, query/body, framing/traversal/limites invalides : refus avant Application. |
| READ-15 | Fixture synthétique trouvée : quatre champs + meta ; absente : RES_NOT_FOUND | Référence malformée, version_ref/include, canonicalité inférée, SQL depuis API, échec technique transformé en succès : refus/échec du test. |
| Lifecycle | Démarrage sans effets à l'import, bind autorisé, fermeture/flush, redémarrage après arrêt | Port occupé, permission locale invalide, bootstrap qui migre implicitement, shutdown bloqué : échec explicite. |
| Confidentialité | Événements minimisés et corrélation commune ; fichier local privé | Log automatique brut HTTP, secret/chemin/payload/query/ref brute, rendu HTML non échappé : test en échec. |
| Autorisations | Zéro provider, réseau externe, credential ou donnée utilisateur ; boucle locale seulement pour tests approuvés | Dépendance téléchargée, seed réel ouvert, runtime utilisateur modifiée ou migration implicite : arrêt. |

Réutiliser, sans duplication ni neutralisation, les trois fichiers de guards, `tests/unit/test_local_browser_http_contract.py`, `tests/integration/test_local_browser_http_observability.py`, `tests/integration/test_minimal_local_observability_signals.py`, `tests/integration/test_resource_library_application_route.py`, `tests/architecture/test_resource_ref_contract_fitness.py`, `tests/architecture/test_active_canonical_semantics_fitness.py`. Les tests real-seed ne sont pas une permission d'ouvrir le seed.

Validation H2 future selon ENVIRONMENT.md : tests ciblés et architecture, lint, typecheck applicables, puis suite de fin d'incrément avec environnement/permissions explicités. Ne pas créer de nouveau skip pour masquer un contrôle manquant. Les 4 947/5/0 B07 restent une preuve historique et ne valident pas le futur serveur.

## 6. Compatibilité historique, risques et retour arrière

Les trois guards ne figurent pas dans les 48 identités protégées B07, dont le freeze historique de 40 fichiers. Cela ne les rend pas librement modifiables. Le hash du guard B04 est référencé dans l'écart H1 ; conserver ce snapshot et son manifeste. Les versions B03/B04/F restent consultables aux commits §2 ; ne pas réécrire les anciennes preuves pour leur attribuer la nouvelle sémantique.

Après décision : produire un nouveau binding PRE/POST des trois seuls guards, lié à cette proposition et aux tests nouveaux ; conserver H1, les anciens manifests et les identités protégées. L'ancien historique « aucun serveur » reste vrai sur sa baseline, pas sur la future baseline produit. Aucun résultat historique renommé PASS d'un test nouveau.

Risques : faux sentiment de couverture V2 par READ-15 ; exposition locale à un site hostile ; serveur stdlib insuffisamment borné ; migration implicite via factory existante ; tests Git n'inventoriant pas les untracked. Réponses : scope visible, contrôle Host/Origin avant dispatch, parsing/limites testés, runtime synthétique uniquement et inventaire complémentaire exact.

`build_configured_sqlite_runtime` / la factory SQLite existante ne doivent pas être invoqués aveuglément : certains chemins provisionnent/migrent. Le futur raccordement doit injecter une runtime de test synthétique existante et validée, avec connexions/lifecycle maîtrisés. Une impossibilité sans changement hors inventaire exige une nouvelle décision, pas un assouplissement.

Retour arrière futur : arrêter l'hôte, revenir par revert local du ou des commits d'implémentation exactement approuvés après revue, conserver preuves et logs minimisés selon rétention. Ni reset destructif, ni restauration/migration SQLite implicite, ni modification du seed. Aucun retour arrière exécuté ici.

## 7. État H1A

`GUARD_MODIFIED = FALSE`. `H2_STARTED = FALSE`.
`OWNER_APPROVAL_STATUS = NOT_RECEIVED`.
La revue porte conjointement sur D-SOURCE, D-GUARD et D-INCREMENT dans [le paquet propriétaire](03_PAQUET_DECISION_ET_PLAN_H2.md).
