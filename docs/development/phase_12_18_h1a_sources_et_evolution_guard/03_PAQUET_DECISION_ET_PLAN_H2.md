# 12.18-H1A — Paquet unique de décision et plan H2

## Résultat soumis à revue

**READY_FOR_SINGLE_OWNER_REVIEW — NOT_APPROVED. H2 non démarré.**

L'autorisation reçue porte sur la préparation documentaire H1A, pas sur l'évolution du code. Trois décisions nouvelles sont rassemblées ci-dessous ; aucune approbation, date d'attestation ou autorité d'exécution n'est renseignée au nom du propriétaire.

### Décisions nouvelles proposées ensemble

| ID | Proposition précise | Pourquoi une décision reste nécessaire |
| --- | --- | --- |
| D-SOURCE | Retenir la réconciliation des 14 sources, la décision navigateur EXT-S13 et les handoffs locaux B05/B06. Approuver pour le seul premier incrément le **nouveau contrat READ15-HTTP-LOCAL-1.0** défini dans l'ADR proposée, à matérialiser en READ15_HTTP_LOCAL_V1.json ; ne pas le substituer aux originaux Phase 8. | Les sept annexes techniques n'ont pas été retrouvées ; elles ne peuvent être inventées à partir du DOCX. Le livrable exact 12.1 reste non identifié. |
| D-GUARD | Approuver **ADR-P12-069**, les six changements d'assertions A1–A6 dans les trois fichiers identifiés, et l'inventaire futur exact de son §4. | L'interdiction globale historique rejette aujourd'hui le serveur, les routes et le frontend ; les invariants durables ne sont pas remis au vote. |
| D-INCREMENT | Retenir **H2_READ15_LOCAL_STDLIB_V1** : un hôte Python 3.12 stdlib, une opération GET READ-15, trois assets locaux HTML/CSS/JS, point d'entrée CLI et lifecycle OBS_A ; tests sur runtime synthétique temporaire hors dépôt. | Le choix concret de serveur/UI et l'enveloppe transport ne sont pas encore acceptés. Cela ne livre ni l'ensemble API, ni les workflows absents, ni le package/recette H3. |

Le périmètre complet et les remplacements exacts sont dans [la proposition d'ADR](02_PROPOSITION_EVOLUTION_GUARD.md). Les fichiers futurs n'existent pas encore. Si le propriétaire préfère retrouver l'OpenAPI original ou une autre stack, ne pas appliquer silencieusement la proposition : produire une seule révision de ce paquet avec le contrat réellement choisi.

### Décisions déjà acquises, sans nouveau vote de principe

Mode LOCAL_BROWSER, loopback et port explicite ; aucun .exe/MSI obligatoire ; aucune dépendance à Drive pour stockage/runtime. Séparation Domain/Application/Adapters et absence d'autorité métier des agents. READ-15 via Application, ResourceRef opaque ASCII borné, quatre champs actuels avec **availability_status**, disponibilité et canonicalité indépendantes, rejet version_ref/include/inconnus. OBS_A locale 5 MiB × cinq fichiers au total, 14 jours, flush ≤ 2 s. Seed immuable et runtime distincte. Les providers restent facultatifs et fail-closed en leur absence.

Ces décisions ne prouvent ni un lancement réussi, ni une migration utilisateur, ni une recette. L'absence de stockage cloud obligatoire ne signifie pas une interdiction générale de futurs services IA dûment autorisés ; il n'existe simplement aucune autorisation provider dans H1A ou dans cet incrément proposé.

## 1. Bindings connus et contrôlés

Tous les hashes sont SHA-256 sauf les commits Git. La matrice lie les 14 originaux, les six fichiers H1, les trois guards, les contrats conservés et les références locales ; elle n'importe aucune source binaire.

| Objet | Identité |
| --- | --- |
| Baseline de revue | `24b7a9850bc4644391dee2307c8a8a31036cd503` |
| Bundle H1A | `a4ae5268736afc8d5b7ac9f0eda1c24ff123bface3a7a2d10416d2d7bb78ccbd` |
| 01_SOURCES_ET_ECARTS_RECONCILIES.json | `a8dd8edc13d505e504a3983bf5598a834f2fb57ba4fead0d3545f1d2848448d3` |
| 02_PROPOSITION_EVOLUTION_GUARD.md | `f019d1e74e079ca2ecfc48f77da8ef3bee6904affa59346b48b59d8d9840a80c` |
| Manifeste des six H1 préservés | `259a50779d6c75231e3a3cad8f5d78dc69442b696613719c128fcb4320674ab3` |
| Manifeste B07 de clôture | `8dd32e9eda71dc86ba3bd3dd740291b85f172630bd979807d9558d8b686fde5b` |
| Guard B04 | `d324d383351cce3039225a8439338f6059abbd2b34bebf286b0e29b8933d56e6` |
| Guard B03 | `87adef3498b85d2bf9f9c462b8b493b29b4d6a474c36976ba775297fde249d7e` |
| Guard F | `9b7d9a25430a41dd5a1c6696b11d582dbfe37d7b5cf425ccc0946d6baf37b501` |
| Contrat pur HTTP conservé | `cc7ee88ebbb41d17feb301c9707d1ab05efe3d1fa3118be8612c1b4c735d1148` |
| Schéma HTTP conservé | `511336250f3a3274fe4f2f17f328771111250b0ec916a4e18723abc6b4ecf298` |
| Lock runtime | `47540b39687a39f627c76e138596abfa752792fa54cef439660c5daba9665a63` |
| Lock dev | `30a3ceec14d10432cd45f4ddddcd54868dd6da55001c8a74c6d125eac97a6c65` |
| Lock calibration | `e044cdb328a65f0d24ad4e82868171c6f96f7ef1e6cbcd6be78d402e3e8d7960` |

La future acceptation porte sur ces octets, pas sur un document homonyme. Les identités futures de contrat matérialisé, code, tests ou commit sont inconnues, donc non inventées. Le manifeste final lie ce paquet mais exclut sa propre empreinte ; aucune dépendance circulaire. Toute dérive réelle de baseline/guard/proposition exige relecture avant action, pas re-liaison implicite.

### Réponse propriétaire préparée, non émise

Pour accepter la proposition, la réponse peut référencer les deux hashes ci-dessus et confirmer ensemble D-SOURCE, D-GUARD et D-INCREMENT. État présent des champs :

```text
OWNER_H1A_DECISION = NOT_RECEIVED
BASELINE_COMMIT = 24b7a9850bc4644391dee2307c8a8a31036cd503
SOURCE_RECONCILIATION_SHA256 = a8dd8edc13d505e504a3983bf5598a834f2fb57ba4fead0d3545f1d2848448d3
GUARD_PROPOSAL_SHA256 = f019d1e74e079ca2ecfc48f77da8ef3bee6904affa59346b48b59d8d9840a80c
D_SOURCE = PENDING
D_GUARD = PENDING
D_INCREMENT = PENDING
PROPOSED_CONTRACT = READ15-HTTP-LOCAL-1.0
PROPOSED_ADR = ADR-P12-069
PROPOSED_INITIAL_SCOPE = H2_READ15_LOCAL_STDLIB_V1
H2_EXECUTION_AUTHORIZED = FALSE
REAL_USER_DATA_ACCESS_AUTHORIZED = FALSE
USER_MIGRATION_AUTHORIZED = FALSE
EXTERNAL_NETWORK_AUTHORIZED = FALSE
PROVIDER_CALLS_AUTHORIZED = 0
H3_EXECUTION_AUTHORIZED = FALSE
OWNER_ATTESTATION = NOT_RECEIVED
OWNER_ATTESTATION_TIMESTAMP = UNSET
```

Ce bloc est une fiche d'état, pas une attestation à appliquer. Une confirmation réelle pourra être consignée telle que reçue, avec son horodatage réel lorsqu'il est fourni/requis ; aucune heure inventée ni approbation déduite de « prends note ». Pas de nouvel aller-retour pour redemander ResourceRef, OBS_A ou le mode navigateur déjà décidés.

## 2. Plan minimal du premier incrément, seulement après approbation

Il s'agit d'un ordre de dépendances, pas d'une nouvelle chaîne de gates génériques. Un même incrément cohérent peut contenir les travaux ci-dessous. Le commit envisagé est **une proposition**, jamais une autorisation H1A de staging/commit.

### Préparer le contrat et la preuve d'évolution

- Sources/écarts : EXT-S06 Z07/Z10, EXT-S08 §§5/8/18, EXT-S13, handoffs B05/B06 ; S01, I01, I03, I05.
- Fichiers : promouvoir l'ADR proposée vers le chemin exact de son §4 après contrôle du numéro libre ; créer le nouveau READ15_HTTP_LOCAL_V1.json dans le dossier H2 proposé. Lier PRE/POST des trois guards sans changer leurs anciens manifests.
- Contrat : une opération, trois assets, enveloppes/erreurs, bornes et inventaires §3/4 de l'ADR ; maintenir absence de commandes et d'autorité nouvelle.
- Tests : test_local_browser_product_boundary.py et test_local_browser_product_routes.py, plus les trois guards B03/B04/F conservant les autres assertions. Positifs et fixtures négatives ; aucune exemption globale.
- Paquets/locks : aucun. Accès SQLite, réseau, provider : aucun pour ce travail statique.
- Acceptation : contrat fermé versionné explicitement distinct des sept originaux absents, décision propriétaire liée, différence historique expliquée et six assertions seulement changées.
- Commit envisagé : intégrer dans le commit d'incrément ci-dessous, pas un commit isolé neutralisant d'abord les guards.

### Câbler READ-15, hôte, interface et cycle de vie

- Sources/écarts : READ-15 B05/B06, EXT-S06 et S13 ; I01/I02/I03/I07, partie de I08. I04 et les commandes I05 restent hors incrément.
- Fichiers : les huit créations code/assets et cinq créations de tests de l'ADR §4 ; les trois seuls guards à modifier. Aucun fichier applicatif existant ni config/lock n'est à modifier.
- Réutilisation : ResourceLibraryUseCaseInbound ; GetResourceQuery, IP-03 et port de lecture resource existants ; factory SQLite et session observabilité existantes, injectées depuis la composition dédiée. Pas de réimplémentation métier et pas de store exposé aux handlers.
- Composition : runtime synthétique existante, préparée exclusivement dans l'espace temporaire de test hors dépôt, injectée sans bootstrap utilisateur ni migration implicite. Fermeture des connexions, du serveur et de la session ; stop/restart ; URL explicite, pas de navigateur lancé par effet d'import.
- Tests : cinq nouveaux fichiers ; tests B03/B04, Application READ-15, ResourceRef et séparation ACTIVE/CANONICAL cités en ADR. Intégration HTTP réelle sur loopback avec référence trouvée/absente/invalide ; erreurs sans données internes ; logs sans payload ; port occupé ; shutdown/flush ; absence totale de credential/provider.
- Paquets/locks : aucun nouveau paquet, aucun changement des trois locks. Réseau proposé : **boucle locale uniquement** pour tests HTTP, jamais index/artifact/provider/externe. SQLite proposée : fixtures synthétiques temporaires seulement ; aucune ouverture du seed/sidecars/runtime utilisateur.
- Acceptation : trajet UI → HTTP → inbound Application → port → adaptateur runtime prouvé ; quatre champs exacts ; aucune commande, élévation de canonicalité, effet fournisseur ou migration utilisateur. READ-15 n'est déclaré recetté que pour le mode effectivement testé.
- Validation : tests/lint/typecheck applicables selon ENVIRONMENT.md, diff complet, inventaire untracked, absence de secrets/runtime en Git. Aucune preuve B07 simplement rebaptisée preuve H2.
- Commit local envisagé, après contrôles et autorisation d'exécution appropriée : `feat(local-browser): wire bounded READ-15 with preserved safety guards`. Aucun futur SHA annoncé. Aucun push/merge.

## 3. Parcours produit restants : ne pas confondre câblage et développement

| Parcours H1 | État et dépendance réelle | Suite minimale, hors premier incrément |
| --- | --- | --- |
| REC-01 / SCN-01 consultation READ-15 | **Application prête à câbler** ; transport/UI à créer, recette absente. | Incrément proposé, puis preuve sur cible réelle seulement après autorisation d'accès ; ne pas déduire 002. |
| REC-02 / SCN-02 recherche locale | Composants retrieval/SQLite présents ; **composition produit et contrat HTTP manquants**, recette absente. | Contrat de requête/résultat/provenance borné ; brancher Application et ports existants ; ni embedding réseau implicite ni endpoint inventé. |
| REC-03 / SCN-03..08 génération, review/correction, assessment/QCM | Pipelines/adaptateurs et doubles existent ; **composition/workflows produit incomplets**. Owners CAP-R02/A01/A02 encore à matérialiser, commandes HTTP manquantes. | Développer les owners réels dans l'ordre ci-dessous, conserver génération/validation/qualité/promotion distinctes ; contrat de commandes versionné avant transport ; recette avec doubles explicitement nommés. |
| REC-04 exploitation locale | B02/B03/B04 implémentés isolément ; **lifecycle produit et preuve de recette manquants**. | Premier raccordement et tests synthétiques ; ensuite package/lanceur et configuration locale portables en H3A, dix contrôles S13 en H3B. |
| REC-05 services IA live | Adapters et calibrations historiques existent ; **aucune autorisation live actuelle ni preuve de recette produit**. | Seulement si requis : nouvelle autorisation ciblée de modèles, appels, plafond, transfert et arrêt ; aucune résolution de credential avant celle-ci. |

Ces REC-xx restent des identifiants de préparation H1, pas de nouvelles gates canoniques. Les 54 opérations/52 paths/93 schemas et 49 liaisons UI/11 écrans décrits par EXT-S08 ne sont ni annulés ni déclarés implémentés par READ-15. Avant toute revendication de conformité exhaustive, retrouver les originaux ou obtenir une disposition/contrat versionné pour la surface effectivement retenue.

### Owners absents : ordre préservé, aucune sonde promue en implémentation

Source exacte : `docs/development/phase_12_17_04e_b09_legacy_review_api_handoff/API_HANDOFF.json`.

| Capacité / écart | Fichiers/owners et ports déjà désignés | Dépendances, tests et acceptation futurs | Paquets, données et commit envisagé |
| --- | --- | --- | --- |
| CAP-R02 / I04 | `backend/modules/work_orchestration/application/` ; application.read_production ; inbound query, typed production read outbound port | Contrats production_ref + version_ref, projection typée minimisée ; version exacte, absence production/version, frontière transport, pas de SQL inbound. Aucun fallback READ-15. | Aucun nouveau paquet identifié ; lock inchangé tant qu'aucune décision contraire. Runtime temporaire pour tests, cible réelle séparément autorisée ; réseau/provider 0. Envisagé : `feat(application): implement versioned production read owner`. |
| CAP-A01 / I04/I05 | `backend/modules/validation_control/application/` ; application.run_deterministic_validation ; inbound command port | Après contrats d'entrée typés/owner précédent ; déterminisme, input fermé, outcome préservé, absence provider. Le routeur n'interprète pas le résultat. | Aucun besoin de paquet établi ; pas d'installation autorisée. Fixtures temporaires, aucune migration utilisateur. Envisagé : `feat(application): wire deterministic validation owner`. |
| CAP-A02 / I04/I05 | `backend/modules/lifecycle_promotion/application/` ; application.request_promotion ; inbound command, promotion persistence et effect ledger ports | Après contrats/décision de gate fiable ; clé idempotente obligatoire, gate absente/rejetée bloque, effet inconnu réconcilié avant replay, aucune auto-approbation ou retry implicite. | Persistance des effets à concevoir/tester hors données réelles ; migration éventuelle à décider séparément. Provider/réseau 0 dans ce développement. Envisagé : `feat(application): implement gated promotion owner`. |

Les noms des nouveaux fichiers internes/DTO de ces trois capacités ne sont pas encore fixés par leur handoff (`TO_MATERIALIZE`). Ils ne sont donc ni inventés, ni inclus dans l'allowlist exécutable du premier incrément. Leur contrat de réalisation exact et le contrat HTTP de commandes doivent être arrêtés avant un lot de code correspondant. L'ownership et l'ordre déjà approuvés ne sont pas remis en cause.

De même, le câblage retrieval/workflows s'appuiera sur les ports existants et la politique F2A/ADR-P12-061 ; sa liste exacte de handlers dépend d'un contrat supplémentaire, absent de la présente proposition. Tests futurs : provenance stable, admission fermée, scénarios/doubles vs live distingués, gates positives/négatives et absence de droits SQL/provider de l'agent. Commit envisagé seulement après ce contrat : `feat(composition): wire approved pedagogical workflow ports`. Aucun paquet ou lock changé par anticipation.

## 4. Runtime réelle, configuration et recette : autorité séparée

I06 reste **USER_RUNTIME_NOT_VERIFIED_IN_H1_OR_H1A**. La preuve B04 concerne des copies ; sa sauvegarde temporaire nettoyée n'est plus disponible. B07 n'a ni migré ni configuré durablement le lanceur utilisateur.

Travail ultérieur proposé, non exécuté et non inclus dans D-INCREMENT :

1. Faire identifier/autoriser la cible exacte, les opérations et la configuration process-only. Vérifier le SHA attendu **avant toute ouverture du seed**, read-only + immutable si sa lecture est autorisée. Ne pas ouvrir les sidecars ou la base « pour voir ».
2. Examiner la runtime distincte par le chemin d'accès autorisé ; prouver son état de migration, sans déduire 002 de l'existence du runner. Points de réutilisation : `backend/infrastructure/composition/factories/sqlite.py` et loader actuel ; pas de changement nécessaire présumé.
3. Si migration requise, demander l'autorisation correspondante et établir une **nouvelle sauvegarde réelle**, recovery testé et identité PRE/POST. Migrations 001/002 inchangées, seed et sidecars intacts. Tests/ports déjà validés B04/B07 réutilisés ; ne pas ouvrir un environnement réel pour lancer indistinctement la suite.
4. Consigner résultat minimisé et configuration portable sans chemin privé/secret dans Git. Aucun paquet, réseau/provider nécessaire à la vérification locale ; commit de preuves envisagé uniquement avec autorisation : `docs(integration): record authorized runtime readiness evidence`.

Identités historiques, pas nouveaux relevés physiques H1A :

- seed : `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` ;
- migration 001 : `5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102` ;
- migration 002 : `e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893`.

ContextOrigin reste UNKNOWN ; disponibilité ne vaut pas canonicalité ; RELEASE_THRESHOLD reste NONE ; droits live historiques consommés. Aucun flag B05/B07 ancien ne vaut autorisation persistante.

## 5. Articulation avec 12.18 et limites de clôture

EXT-S12 est la macro historique où Phase 3 était courante, Phase 13 = Tests/recette et Phase 14 = Déploiement/stabilisation. Elle est conservée comme source historique ; H1A ne supprime, ne relance, ne recrée ni ne clôt ces phases.

EXT-S13 adapte la fin de Phase 12 : H1 audit, H2 intégration backend/frontend/API/SQLite/configuration, H3A package/lanceur, H3B recette, H3C livrable complet. Ses cinq gates sont LOCAL_BROWSER_EXECUTION, BACKEND_STARTUP, FRONTEND_ACCESS, LOCAL_DATA_RUNTIME, END_TO_END_ACCEPTANCE ; **aucune n'est déclarée PASS produit par H1A**.

H3B conserve les dix contrôles : lancement local ; backend ; navigateur/URL ; interface ; runtime ; seed intact ; scénario pédagogique complet ; arrêt ; redémarrage ; indépendance Drive. Le premier incrément READ-15 prépare des preuves bornées, pas automatiquement ce scénario complet ni une fermeture globale de 12.18.

H3A/B/C ne sont pas démarrés. La clôture 12.17.8 B07 reste acquise sur ses preuves ; le statut global 12.17 rapporté en H1 reste NOT_CLOSED_NO_ADDITIONAL_AUTHORITY, sans nouvelle gate intermédiaire créée ici. Aucune clôture de Phase 12 ou du projet n'est déduite du présent paquet.

## 6. Prochain geste unique

Revoir ce paquet et ses deux pièces liées, puis confirmer ou réviser **D-SOURCE + D-GUARD + D-INCREMENT** ensemble. Aucune approbation de guard abstrait n'est demandée : fichiers, hashes, six assertions, routes, enveloppes, dépendances, données et exclusions sont explicités.

État : préparation documentaire prête pour cette revue ; original 12.1 et sept annexes Phase 8 restent manquants/non identifiés selon la matrice. H2 n'est ni autorisé ni commencé. Tout élargissement futur de scope, données réelles, commandes HTTP, stack, réseau ou provider reste distinct.
