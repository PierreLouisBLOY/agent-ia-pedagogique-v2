# Proposition de recherche locale — livrable de préparation

PROPOSITION_COMPLETE = TRUE

IMPLEMENTATION_AUTHORIZED = FALSE

CONTRACT_STATUS = PROPOSED_NOT_APPROVED

H3_STARTED = FALSE

## Recommandation directement soumettable à décision

Sur HEAD 3f724ca81843b5d45ac534e9654ff16281c55713, proposer GET /api/v2/search?q=...&limit=... : q obligatoire, 1..256 points de code, 1..12 tokens ; limit=10 par défaut, maximum 20 ; fenêtre de 100 candidats, extrait de 320 points de code, corps JSON de 64 KiB maximum. Recherche LEXICAL seulement, tous les termes littéraux, admission indépendante F2A, ordre bm25 puis passage. Aucun paramètre de recherche ajouté à READ-15.

Présents : FTS5 OP-11, admission SQLite F2A, accès OP-13, ressource OP-03/READ-15, hôte HTTP stdlib, trois assets et OBS_A. Absents : use case/inbound/port de recherche produit et projection HTTP/UI. L’incrément proposé comporte donc du développement M03 et un nouveau pont outbound, pas uniquement du raccordement.

Un hit est un passage d’un objet du registre, pas nécessairement une ressource. Le bouton READ-15 n’existe que si type RESOURCE, ResourceRef valide et lecture exacte OP-03 via Application réussie. Les autres résultats restent explicitement non ouvrables. Aucun rang/score/disponibilité n’invente la canonicalité ni la qualité pédagogique.

## Étendue future exacte

30 fichiers : 20 créations, 10 modifications ; liste exhaustive, responsabilités et SHA PRE dans 03_INVENTAIRE_FICHIERS_ET_GUARDS.json et tableau intégral du document 04. Décomposition : 15 production/assets, 11 tests, un nouvel ADR descriptif et trois pièces d’exécution. Les six présentes pièces et les 11 documents H1/H1A sont des entrées protégées, hors ce futur diff.

Quatre évolutions de guards dans trois fichiers d’architecture :

- G01 : test_local_browser_product_boundary.py, oracle de route_contract_violations et contrat actif vers les cinq routes exactes ; contre-exemples A7 conservés.
- G02 : même fichier, inventory_violations lié à la baseline recherche fixe et aux 30 paths ; hash des entrées documentaires ; BASELINE historique des autres assertions conservée.
- G03 : test_resource_ref_contract_fitness.py, seule assertion ROUTE_SPECS de test_read15_keeps_one_field_and_deprecations_without_http_implementation ; les six assertions antérieures du nodeid restent inchangées.
- G04 : test_security_recovery_observability_e2e_fitness.py, assertion test_later_provider_work_preserves_phase_f_backend_owners : huit chemins exacts nouveaux, inventaire strict maintenu.

Une assertion unitaire : U01, test_local_browser_product_routes.py, len(ROUTE_SPECS) de 4 vers 5, autres assertions intactes. Anciens guards B04/B03 conservés, aucun framework/SQL/API ou accès aux données exempté. PRE/POST exacts et hashes dans le JSON ; nouveaux tests positifs/négatifs listés sans revendiquer leur exécution.

## Tests et permissions futurs

Après accord global seulement : tests de texte/query/projection, Application avec doubles, FTS5 et provenance sur fixtures synthétiques temporaires, chaîne HTTP loopback puis READ-15, Host/Origin, zéro fuite de q/extraits/références dans les logs, port occupé, stop/restart/flush, hash/readonly, absence de découverte des chemins utilisateur. Réutiliser les tests READ-15 et les guards existants ; pytest/lint/typecheck/compile selon ENVIRONMENT.md, sans installer de dépendance.

Les preuves de transport et assets ne valent pas recette navigateur : l’UI manuelle reste un résultat distinct à documenter. La suite réelle/seed reste NOT_RUN / NOT_PASS. Le plan de suite synthétique nomme explicitement le test réel non exécuté et n’en masque pas le statut.

Approbation future nécessaire : contrat P01..P15, ownership M03 proposé, 30 fichiers, G01..G04/U01, fixtures/logs/caches hors dépôt, sockets loopback et un commit local cohérent après contrôles. Rien n’autorise maintenant ces actions. Aucun choix indispensable n’est laissé TO_DEFINE ; la seule décision restante est approuver ou réviser CE paquet complet.

## Écarts et limites conservés

1. La preuve READ-15 mentionne encore LOCAL_COMMIT_PENDING car elle est pré-commit ; HEAD et les 20 entrées du manifest correspondent à la livraison. Pas de reconstruction ou réécriture historique.
2. Les chiffres reçus (186 ciblés, 5043 passed/28 skipped, stress 12/12) sont historiques, pas des tests recherche.
3. L’ancien incident is_file() de métadonnée runtime reste consigné ; aucun nouvel accès à ces chemins dans la préparation.
4. Recherche non exhaustive : ressources non indexées ou objets sans mapping direct non garantis ouvrables. FTS5/schéma/index de la bibliothèque réelle non vérifiés.
5. Sources Phase 8/12.1 absentes non recherchées à nouveau ; aucun faux original. Le nouveau contrat est une proposition bornée.
6. CAP-R02 → CAP-A01 → CAP-A02, accès réel, migration, services IA, packaging et H3 restent séparés et non démarrés.

## Contrôles documentaires et livraison

Six fichiers seulement créés dans le dossier de préparation. JSON/inventaire/hashes/PRE, UTF-8 sans BOM, LF final unique, diff et absence de mutation de l’index contrôlés avant remise. Aucun code/test/guard/ADR accepté/config/lock modifié ; aucune exécution de test technique, serveur, CLI, factory, import applicatif, SQLite, socket, credential ou réseau ; aucun staging/commit/push/merge.

MANIFEST_SHA256.txt couvre exactement les cinq autres sorties, pas lui-même. Son SHA-256 communiqué dans la réponse constitue le hash du paquet final. Les sources et documents historiques sont vérifiés sans normalisation ni modification. Aucune déclaration de réussite technique du futur incrément.
