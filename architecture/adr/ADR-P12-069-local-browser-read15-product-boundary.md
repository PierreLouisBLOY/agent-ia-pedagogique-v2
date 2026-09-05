# ADR-P12-069 — Frontière produit HTTP locale READ-15

## Statut et autorité

ACCEPTED pour le seul incrément H2_READ15_LOCAL_STDLIB_V1, à la suite du message propriétaire explicite approuvant D-SOURCE, D-GUARD et D-INCREMENT, les tests HTTP loopback, les fixtures SQLite synthétiques temporaires hors dépôt et le commit local borné après contrôles.
L'acceptation de l'architecture ne préjuge pas du résultat d'implémentation.

Baseline approuvée : `24b7a9850bc4644391dee2307c8a8a31036cd503`.
Source reconciliation : `a8dd8edc13d505e504a3983bf5598a834f2fb57ba4fead0d3545f1d2848448d3`.
Proposition ADR v1.0 : `f019d1e74e079ca2ecfc48f77da8ef3bee6904affa59346b48b59d8d9840a80c`.
Les deux originaux restent inchangés dans `docs/development/phase_12_18_h1a_sources_et_evolution_guard/`.
Le numéro 069 était libre à l'entrée H2. Aucune attestation horodatée supplémentaire n'est fabriquée.

## Décision bornée

Python 3.12 stdlib HTTPServer/BaseHTTPRequestHandler, hôte local dédié sans serveur de fichiers générique ; HTML/CSS/JavaScript local same-origin sans dépendance. Domain/Application restent indépendants du transport. Handlers sans SQL, repository, provider ou domaine : délégation à ResourceLibraryUseCaseInbound, assemblage par factory dédiée.

Contrat nouveau READ15-HTTP-LOCAL-1.0, non reconstitution des annexes Phase 8 absentes :
GET `/api/v2/resources/{resource_ref}` ; GET/HEAD `/`, `/assets/app.js`, `/assets/styles.css`.
Aucune autre route, body ou query ; HEAD API = 405. ResourceRef conserve la validation métier.
Succès data : resource_ref, resource_type, canonical_title, availability_status, exactement ; meta.correlation_id.
Erreurs bornées, BusinessError/validation/ApplicationFailure distingués ; pas de canonicalité inférée.

Contrats B04 et OBS_A inchangés : bind loopback, port explicite, Host/Origin contrôlés, CORS vide, pas de sessions/credentials/debug/reload/docs ; NDJSON 5 MiB × cinq fichiers au total, 14 jours, flush à l'arrêt ≤ 2 s. Aucun log brut HTTP ni second générateur de corrélation. Hôte mono-requête, HTTP/1.0 fermé, cible ≤ 8 KiB, headers agrégés ≤ 64 KiB, timeout socket 5 s ; rejet avant dispatch des ambiguïtés et dépassements. Les garanties sont à tester, pas supposées offertes par la stdlib.

## Évolution exacte A1–A7

Les nodeids A1–A6 restent ceux de la proposition. A7 conserve son nodeid historique relevé dans le dépôt ; toutes les autres assertions restent inchangées.

1. B04 test_b04_adds_no_http_server_framework_or_route : six frameworks tiers toujours interdits ; http.server au seul chemin API/server.py, attribution par fichier.
2. Même test : server.py/routes.py exclusivement aux deux emplacements API approuvés.
3. Même test : registre fermé des quatre routes, preuve AST/contrat/dispatch, pas exemption lexicale générale.
4. B04 test_b04_adds_no_frontend_public_url_or_drive_runtime_dependency : trois assets exacts, same-origin ; les autres assertions demeurent.
5. B03 test_http_observability_adds_no_server_framework_or_route : bootstrap observabilité indépendant du serveur ; pas de construction/bind/import serveur, factory dédiée propriétaire.
6. F test_later_provider_work_preserves_phase_f_backend_owners : quatre chemins entrants API/CLI exacts ajoutés, aucun préfixe permissif nouveau ; inventaire indépendant du diff HEAD, couvrant untracked/staged et après commit.
7. ResourceRef test_read15_keeps_one_field_and_deprecations_without_http_implementation : l'interdiction historique de toute présence READ-15 est remplacée par l'égalité stricte avec le registre fermé approuvé. Les six assertions précédentes du nodeid et tous les autres tests du fichier restent inchangés. Des contre-exemples H2 vérifient qu'une route supplémentaire dans le registre ou déclarée hors de son seul propriétaire est rejetée.

Interdictions API conservées : anthropic, backend.adapters.outbound, backend.modules, calibration_tooling, openai, sqlite3. Imports relatifs/dynamiques de contournement testés négativement. Pas de skip/xfail/exclusion mypy/flag permissif.

## Inventaire et historique

Inventaire exact : quatre guards existants, huit créations code/assets, cinq tests nouveaux et les quatre documents énumérés dans la proposition liée. Aucune autre modification autorisée.
Les bindings PRE/POST sont consignés dans `docs/development/phase_12_18_h2_local_read15/IMPLEMENTATION_EVIDENCE.md`.
H1/H1A, manifests historiques et 48 identités protégées sont conservés ; les tests B03/B04/F restent des preuves de leurs baselines historiques. Aucune re-liaison des anciennes preuves à des octets nouveaux.

Addendum A7 accepté par message propriétaire réel : l'extension ajoute uniquement `tests/architecture/test_resource_ref_contract_fitness.py` à l'inventaire existant modifiable. Elle ne change ni route, ni enveloppe, ni permission du contrat READ15-HTTP-LOCAL-1.0 ; A1–A6 gardent leur portée initiale. Les sources et manifests H1/H1A restent inchangés.

## Limites et conséquences

Aucun accès seed/sidecars/runtime utilisateur, copie de base réelle, migration utilisateur, credential, réseau externe/provider, installation/lock/config persistante, push/merge/H3. La factory dédiée reçoit une runtime de fixture existante et un hash explicite ; aucun appel aux chemins de bootstrap/migration. Connexions read-only ouvertes et fermées dans le thread de requête.

Cet incrément ne livre pas les 54 opérations/11 écrans, CAP-R02/A01/A02, commandes HTTP, recherche/workflows complets, package ou recette H3. Les sept annexes Phase 8 et le livrable 12.1 restent manquants/non identifiés. ContextOrigin UNKNOWN, RELEASE_THRESHOLD NONE et absence d'autorité métier des agents préservés.

Risques : exposition locale à un site hostile, limites du petit serveur stdlib, confusion prototype/produit complet, migration implicite et contournement du diff par commit. Réponses : frontière fermée avant dispatch, tests HTTP négatifs, portée synthétique visible, aucun bootstrap et inventaire stable de baseline.

Retour arrière : arrêt de l'hôte puis revert local du commit approuvé après revue ; aucune action destructive ou restauration SQLite implicite. Ne pas livrer un commit ne faisant que neutraliser les guards. Toute impossibilité dans l'inventaire exige revue de portée.
