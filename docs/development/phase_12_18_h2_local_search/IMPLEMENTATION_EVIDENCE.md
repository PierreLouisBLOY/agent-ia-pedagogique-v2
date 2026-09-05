# R1 — Recherche lexicale locale : preuves d'implémentation

## Autorité, périmètre et entrée

H2_LOCAL_LEXICAL_SEARCH_V1 / SEARCH-HTTP-LOCAL-1.0. État : PASS_DANS_LE_PERIMETRE_SYNTHETIQUE_AUTORISE.
Seul R1 est exécuté ; ceci ne clôt ni H2, ni H3, ni la Phase 12.

- Baseline d'entrée : `3f724ca81843b5d45ac534e9654ff16281c55713`.
- Manifest décisionnel : `7e210975e1c64ecc29aa73bbbaf48c2e4b099501625fd061f33f0ef13d8f15f4`.
- Manifest historique READ-15 : `0b21d5ed85751b89c8bd55182392a2de99507b817d351a8211ba9834f54eddb7`.
- Feuille de route externe : `10c7fc1114c4203948cc7be476864810cb5a39fceb66e47851bf57826aea12a4`.
- Accord : message utilisateur explicite autorisant P01–P15, ownership M03, les 30 chemins, G01–G04/U01, les validations synthétiques et un seul commit local cohérent. Aucune heure ni signature propriétaire inventée.
- Les six originaux préparatoires gardent leur statut historique. Le présent document enregistre leur adoption ; aucune régénération ni réécriture des sources.

Avant import applicatif/modification : HEAD exact, index vide, dix SHA PRE conformes, vingt créations absentes, identités des six originaux dans le ZIP et le dépôt conformes, dépendances read-only et documents H1/H1A conformes. Les dix PRE et l'inventaire exact figurent dans le JSON préparatoire hashé, et les identités du nouvel incrément dans le contrat actif.

Inventaire : exactement 30 chemins autorisés, 20 créations et 10 modifications. Les 17 untracked préexistants protégés (11 H1/H1A + six préparatoires) sont conservés hors staging/commit. Ni l'archive ni les documents de pilotage externes n'entrent dans Git. ADR descriptif accepté/relu avant code ; ADR-P12-069 inchangé.

## Réalisation et correspondance P01–P15

| Règles | Réalisation et preuve |
| --- | --- |
| P01 | Découverte de passages indexés, vide explicite, non-RESOURCE visible et non ouvrable. Tests Application + chaîne HTTP synthétique. |
| P02–P04 | Cinq routes exactes, seul GET recherche ajouté, query fermée q/limit, décodage UTF-8 unique, méthode prioritaire. READ-15/assets conservent le rejet des query ; framing/Host/Origin/B04 inchangés. Tests routes et HTTP positifs/négatifs. |
| P05–P06 | SearchText M03 : NFC, séparateurs, 256 points de code, 12 tokens de 64 maximum ; FTS construite par tokens littéraux AND dans le pont outbound. Tests limites exactes, français, contrôles/bidi/surrogates, OR non opérateur. |
| P07–P09 | OP-11 LEXICAL uniquement, contraintes fermées, F2A indépendante pour toute la fenêtre de 100, OP-13 seulement après admission et seulement pour les passages retenus. Ordre bm25/id conservé ; aucune fusion par objet. Tests 100/101 candidats, tous refusés, concordance OP-13, CURRENT/canonicalité, mauvais checksum, fenêtre et refus de matérialisation. |
| P10 | Une connexion readonly/query_only et transaction BEGIN/rollback pour OP-11/F2A/OP-13/OP-03 ; composition responsable du close en finally. Validation M03 puis hash de fixture avant ouverture. Tests écriture refusée, snapshot, hash erroné avant connect, fermeture après panne, bytes/sidecars synthétiques inchangés pendant lecture. |
| P11–P12 | Projection fermée, identifiants logiques, excerpt assaini 320 points, provenance fixe non absolue ; plafond 64 KiB UTF-8 sur l'enveloppe finale avant émission, dépassement 500. Tests exact 65536/+1, doublons, identité/corrélation/effets/événements interdits et erreur minimisée. |
| P13–P14 | Nouveau use case M03 via inbound Application. Seuls RESOURCE + ResourceRef valide + lecture Application exacte donnent OPENABLE. NOT_RESOURCE, INVALID_RESOURCE_REF et RESOURCE_NOT_FOUND distincts ; autres erreurs techniques non masquées. Recherche puis READ-15 et disparition entre requêtes testées, sans cache ni conversion fictive. |
| P15 | Formulaire et liste dans les trois assets : same-origin/credentials omit, textContent, annulation et rejet des réponses tardives, notices fenêtre/non-exhaustivité/non-ouvrabilité. Journaux sans requête, contenu, références, SQL, chemin ou exception. Tests statiques, HTTP, sink défaillant, deadline et redémarrage. |

OP-11/OP-13/OP-03, ResourceRef, GetResourceQuery, contrat READ-15 pur, B03/B04, CLI, configuration, dépendances et contrats agents restent inchangés. Aucun SQL métier recopié. Aucun agent supplémentaire ni capability/workflow génératif introduit.

## Guards et histoire

G01 : égalité stricte AST/registre importé/contrat sur les cinq routes ; assets et scanner hors registre conservés.
G02 : tuple littéral de 30 chemins, baseline fixe d'entrée (pas HEAD), 17 documents protégés individuellement par hash, contrôle du paquet.
G03 : seule assertion du tuple A7 évoluée ; six assertions précédentes préservées.
G04 : ajout exact des huit fichiers M03/inbound autorisés ET contrôle d'inventaire maintenu.
U01 : seule cardinalité 4 → 5 ; autres assertions identiques.

Nouveaux tests positifs et mutations négatives : route/méthode supplémentaire, duplicata/manquante, fichier staged/untracked non listé, document protégé altéré, propriétaire backend supplémentaire. Comparaison AST de toutes les autres fonctions des quatre fichiers contre la baseline R1, sans élargissement d'exceptions. Le guard historique garde `24b7a9850bc4644391dee2307c8a8a31036cd503`.
Les 20 entrées de l'ancien manifest READ-15 sont contrôlées contre les blobs de sa baseline, avec représentation Git LF/working-tree CRLF explicitement prise en compte en mémoire seulement. Les documents historiques eux-mêmes et dépendances read-only sont contrôlés byte-identiques.

## Environnement réellement utilisé

Python 3.12 de l'environnement déjà présent ; aucune installation/résolution. Processus enfant à environnement vidé puis limité à Windows, PATH des outils existants, répertoire temporaire privé neuf et réglages de validation.
Aucun setting seed/runtime/provider/credential hérité. PYTHONDONTWRITEBYTECODE=1, PIP_NO_INDEX=1, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ; UTF-8 explicite. Git safe.directory est lié au seul dépôt dans l'environnement du processus, sans écriture de configuration persistante.

Répertoire de preuves privé hors dépôt : identifiant `projet-v2-r1-04354da001e7412d978f821e650628b9` sous le temp système. Chaque tentative pytest possède un basetemp distinct et un JUnit. Fixtures créées depuis un schéma/texte synthétiques, jamais copiées d'une base réelle. Initialisation fermée avant hash, lecture query-only ensuite. Mutations de scénarios exclusivement en phase séparée de fixtures.

Examen statique de collecte effectué avant suite : tests/conftest.py impose un temp externe, les gates réelles conditionnelles exigent des opt-ins absents. Seule exception autorisée de collecte :
`--ignore=tests/non_functional/test_retrieval_quality_real_gate.py`.
Ce fichier est inchangé. Pas de second ignore, de nouveau skip/xfail, ni d'exclusion mypy.

## Tentatives conservées et corrections ordinaires

| Tentative | Résultat observé | Correction dans ce même incrément |
| --- | --- | --- |
| Typage initial | 2 erreurs de paramètre générique ContractMeta | Construction explicite de la métadonnée OutcomeStatus dans le nouvel inbound ; typecheck suivant réussi. |
| Lint initial | 4 blocs d'imports | Organisation des imports des seuls fichiers autorisés. |
| Ciblée 01 | 216 passed / 10 failed, 46.54 s | 2 constructions de tests incompatibles avec les invariants UseCaseResult ; 8 contrôles Git refusés par ownership du sandbox isolé. Tests corrigés et safe.directory limité au processus. |
| Ciblée 02 | 225 passed / 1 failed, 48.17 s | Comparateur AST nouveau : décodage Git en locale Windows au lieu d'UTF-8. UTF-8 explicite ; diff U01 vérifié : seule cardinalité. |
| Ciblée 03 | 1 erreur de collecte | Noms historiques identiques de tests READ-15 unit/integration : mode pytest importlib au niveau invocation, sans renommage/exclusion. |
| Ciblée 04 | 384 passed / 18 failed, 152.83 s | Un import du helper invocation avait été retiré par erreur dans le nouveau test de projection ; restauré. Aucun échec fonctionnel/guard dans ce passage. |
| Ciblée finale 05 | 402 passed / 0 failed / 0 skipped, 148.007 s (JUnit) | Les 26 fichiers ciblés sont rejoués après corrections, dont 168 cas dans les sept nouveaux fichiers. |

Renforcement ordinaire du code neuf lors de la revue : inbound refusant explicitement outcome incohérent/effets, endpoint refusant événements/erreur d'enveloppe et limit bool/non-int, avec non-régressions. Aucune source hors inventaire modifiée ; aucun delta nécessitant un arbitrage supplémentaire identifié.

## Validation finale

- Tests ciblés : PASS, 402 tests ; contrôle isolé supplémentaire de projection : 19 passed (0.44 s).
- Suite SYNTHETIC_AUTHORIZED : PASS, 5211 passed, 28 skipped, 0 failed, 1 warning, 575.31 s ; 5239 cas collectés (JUnit : 575.120 s).
- Ruff global `python -m ruff check . --no-cache` : PASS.
- Mypy `python -m mypy backend --cache-dir <temp>/mypy` : PASS, 697 sources.
- Compilation `python -m compileall -q backend`, PYTHONPYCACHEPREFIX externe : PASS.
- `python -m pip check` : PASS, No broken requirements found.
- Inventaire/index pré-commit : 30/30 chemins techniques exacts, aucun hors scope ; 50 vérifications d'empreintes protégées/read-only sans écart. git diff --check et git diff --cached --check sans diagnostic ; revue des dix diff et des vingt créations effectuée. Guards exécutés après staging : 54 passed en 5.79 s, aucun skip/échec. Le premier essai d'écriture de l'index a été refusé par le sandbox avant mutation ; la permission d'outil a ensuite permis la même écriture locale bornée, sans changement d'autorité métier.
- Stress 12 cycles recherche réels : PASS, 12 réponses stables et 12 corrélations distinctes, fermeture/flush bornés, même port réutilisable, octets/sidecars synthétiques inchangés. Ce n'est pas le 12/12 historique.
- UI_STATIC_CHECKS = PASS ; UI_MANUAL_ACCEPTANCE = NOT_RUN.
- REAL_SEED_GATE = NOT_RUN / NOT_PASS.

Commande ciblée : Python du venv, `-m pytest -q --import-mode=importlib -p no:cacheprovider --basetemp <temp>/targeted-05 --junitxml <temp>/targeted-05.xml`, puis ces fichiers sans sélection/skip ajouté :

```text
tests/unit/test_local_search_text.py
tests/unit/test_local_search_application.py
tests/unit/test_local_search_http_projection.py
tests/unit/test_local_search_routes.py
tests/integration/test_local_search_sqlite.py
tests/integration/test_local_search_http.py
tests/architecture/test_local_search_product_boundary.py
tests/architecture/test_local_browser_product_boundary.py
tests/architecture/test_resource_ref_contract_fitness.py
tests/architecture/test_security_recovery_observability_e2e_fitness.py
tests/unit/test_local_browser_product_routes.py
tests/architecture/test_local_browser_http_boundary_fitness.py
tests/architecture/test_minimal_local_observability_fitness.py
tests/architecture/test_canonical_contract_boundaries.py
tests/architecture/test_repository_baseline.py
tests/architecture/test_resource_library_application_sqlite_fitness.py
tests/architecture/test_retrieval_admissibility_decoupling_fitness.py
tests/architecture/test_evidence_retrieval_boundary_fitness.py
tests/architecture/test_retrieval_coordinator_fitness.py
tests/architecture/test_active_canonical_semantics_fitness.py
tests/architecture/test_phase_12_17_04e_b09_documentary_handoff.py
tests/unit/test_local_browser_read15_http.py
tests/integration/test_local_browser_read15_http.py
tests/integration/test_local_browser_product_composition.py
tests/unit/test_local_browser_http_contract.py
tests/integration/test_local_browser_http_observability.py
```

Commande globale exécutée : mêmes options d'isolation, `--basetemp <temp>/suite-final --junitxml <temp>/suite-final.xml --ignore=tests/non_functional/test_retrieval_quality_real_gate.py tests`. Aucun autre ignore. Décompte des 28 skips préexistants : 23 gates SQLite sans configuration, 3 gates calibration/sémantique sans opt-in, 2 tests de liens symboliques indisponibles dans le sandbox Windows. Ils ne sont jamais annoncés PASS.

Écart de validation explicitement conservé : la suite globale, exécutée avec PYTHONUTF8=1, a émis un PytestUnhandledThreadExceptionWarning dans `tests/unit/test_local_filesystem_security.py::test_windows_junction_parent_is_rejected_when_supported` : sortie OEM de cmd/mklink décodée en UTF-8. Le test lui-même a passé ses assertions. Ce fichier historique est hors allowlist et reste inchangé. Vérification bornée sans forçage PYTHONUTF8, avec `-W error` : **1 passed, 0 warning, 0 skipped, 0 failed, 0.23 s**. Aucun filtre de warning de masquage ajouté. La suite globale n'est pas présentée comme « zéro warning » et n'a pas été réexécutée pour effacer cette trace.

### Empreintes des rapports JUnit privés

Rapports conservés uniquement dans le répertoire temporaire identifié plus haut, jamais dans Git :

```text
6162d98a2ae714dc620cfb0b4414a59417597031874f90870eb347eb846fe71b  targeted-01.xml
3ec5e866c461e2bbca50aef30eae711a859cf43a1b937497fe73bf658a08685f  targeted-02.xml
a2c0424916d1641a723c0b049df2b10af5e9df7b3bd59558c5522d2026b6ee3b  targeted-03.xml
5e57eb1423c16fe890d1f48e6f9815cce26ed5eadebaffbf084a7b64ffdefe72  targeted-04.xml
e1e3fb1814dee70cc62df771cbb6be2da0802cfca297f2944e09e4a0cf4353ce  targeted-05.xml
3f8f6170b20ac141966f45f78d4acca61247d52ef86911dba3c01e70b9e497f5  suite-final.xml
a3231770b40d0415de2687079ea63e51a1d61f40bd0e9996304314189f0a6c0f  projection-final.xml
8a57b048677079cad03eed799f382643ceb295d771a348e195593045a139b8fc  windows-warning-check.xml
0d2edcbbda87ba5d563fdb725f351353a4e4a56347f6f596aa68a04832118ed7  staged-guards.xml
```

## Limites, livraison et arrêt

USER_DATA_ACCESS = 0 ; USER_DATA_METADATA_ACCESS = 0 ; PROVIDER_CALLS = 0 ; EXTERNAL_NETWORK = 0.
Pas de seed, sidecar ou runtime utilisateur inspecté. Pas de migration utilisateur, configuration persistante, nouvelle dépendance, push/merge/H3. SQLite/logs/caches/bytecode/JUnit restent hors dépôt. Pas de suppression des artefacts préexistants ; les preuves temporaires de ce lot sont conservées localement.

La chaîne techniquement disponible est recherche locale bornée → passages admis → sélection explicitement ouvrable → READ-15. Aucun clic navigateur ni recette sur bibliothèque réelle prétendu. Pas de promesse d'exhaustivité, de pertinence pédagogique, de couverture SCN-02 complète ou de durée FTS réelle.

Ce document est le snapshot pré-commit des validations réussies. Le seul commit local cohérent autorisé comprend ces 30 chemins, après contrôle exact du staging et `git diff --cached --check`. Son SHA et le contrôle post-commit sont communiqués dans la réponse finale, hors manifest et sans auto-référence circulaire. Les 17 documents non suivis restent visibles et protégés.

Prochaine priorité imposée : R2, génération pédagogique conversationnelle (contrôle BTS CG d'une heure, bilan fonctionnel/BFR, sur 20 ; réutilisation AG-01/AG-02/AG-03 et CAP-R02). Puis R3 et R4, sans détour de bibliothèque. Leurs contrats et permissions ne sont pas fournis par R1.
Arrêt de l'exécution après livraison R1.
