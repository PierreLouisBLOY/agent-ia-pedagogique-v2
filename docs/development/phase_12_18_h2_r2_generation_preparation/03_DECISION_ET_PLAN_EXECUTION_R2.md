# R2 — Décision commune et plan d'exécution conditionnel

Statut : PROPOSITION_COMPLÈTE / AUCUNE_APPROBATION_PRÉREMPLIE.
Baseline : 19c42bc9f4b0b1a97b9bd2d6b880acd7378459f7.
Scope proposé : H2_CONVERSATIONAL_GENERATION_V1 / CONVERSATION-HTTP-LOCAL-1.0.

## 1. Résultat recommandé

Réaliser un seul incrément R2 : l'enseignant formule sa demande dans la conversation locale, complète le contexte manquant, confirme ce contexte, déclenche une génération bornée, puis consulte une ProductionCandidate non validée et sa version exacte via CAP-R02.

Le pilote reste : « Crée un contrôle BTS CG de 1 h sur le bilan fonctionnel et le BFR, noté sur 20. » L'année de BTS, les objectifs et la difficulté ne sont pas inventés ; ils sont clarifiés. L'exemple « deuxième année » de la fixture n'est pas la réponse du propriétaire.

La recommandation conserve la stack, les agents, les capacités, les ports et les mécanismes canoniques existants. Ce n'est ni une nouvelle bibliothèque ni une génération texte directement placée dans un handler. Les nouvelles pièces sont un contrat produit proposé, pas une reconstitution des annexes Phase 8 absentes.

Le paquet contient exactement :

1. 01_CONTRAT_R2_GENERATION_CONVERSATIONNELLE.md — règles C01–C18.
2. 02_INVENTAIRE_GUARDS_TESTS_PERMISSIONS_R2.json — inventaire exact, SHA PRE, réemplois et gaps, assertions avant/après, tests T01–T11, permissions et proposition live.
3. 03_DECISION_ET_PLAN_EXECUTION_R2.md — cette décision et le mandat conditionnel de réalisation.
4. MANIFEST_SHA256.txt — SHA-256 des trois pièces, sans auto-référence.

Le SHA du manifeste est livré séparément du SHA du ZIP. Le ZIP ne contient aucun code, fixture binaire, secret, donnée runtime ou approbation. Les quatre originaux documentaires restent dans phase_12_18_h2_r2_generation_preparation ; ils ne remplacent aucun contrat actif.

## 2. Arbitrages réunis dans cette seule décision

Toutes les lignes suivantes sont RECOMMENDED / PENDING_OWNER_DECISION.

| Objet | Choix proposé | Justification et limite |
| --- | --- | --- |
| Dialogue | Demande française, extraction locale bornée, contexte proposé puis confirmé, continuation conservée | Pas d'appel payant pour clarifier ; reconnaissance du pilote honnêtement limitée, correction manuelle du contexte possible. |
| Ownership | M07 contexte, M04 création, M08 conversation et CAP-R02 | Chemins canoniques des bounded contexts ; ni M03 par proximité R1, ni agents propriétaires de stores. |
| Chaîne | WF-4 AG02 → AG03, sélection AG01 et runtime existants | Bindings concrets en composition ; pas de second runner, budget engine, catalogue ou ProductionCandidate. |
| Evidence | Trois passages synthétiques via OP11/OP13 et admission F2A | Ne pas transformer un résultat de recherche UI en source ; blocage si insuffisant ; aucune source officielle BTS prétendue. |
| HTTP | Deux POST et deux GET supplémentaires, neuf routes exactes | GET sans effet génératif ; CAP-R02 requiert production/version, READ-15 ne récupère pas version_ref/include. |
| Sécurité | Host/Origin fermés, nonce processus, intent, JSON/framing bornés, CAS et mandat Application | Loopback/nonce seuls ne donnent aucun droit provider. Ancien authorize_request intact, authorize_command distinct. |
| Travail long | Un enfant stdlib supervisé, POST202 et polling GET | Serveur mono-requête toujours disponible ; pas de ThreadingHTTPServer illimité. Délai HTTP5s distinct SDK90s/job120s/arrêt5s. |
| Candidate | Vrai store volatil limité à trois candidates, durée maximale2h | Lecture exacte et contexte conservés pendant la session ; perte au redémarrage annoncée, pas sauvegarde R4. |
| Provider produit | Adaptateur OpenAI existant, profil génération Terra, opt-in R2 sections/références/effortLOW | Pas le scorer Anthropic de calibration, pas de client neuf ni changement de lock. Disponibilité actuelle non vérifiée. |
| Sortie | Cinq sections substantielles, statut CANDIDATE, références déclarées utilisées et lineage | Pas de validation de calculs/barème, review, correction complète ou distribution prétendue : R3. |
| UI | Trois assets actuels, texte non actif, demande/contexte/candidate visibles | Recette navigateur distincte du contrôle de sources HTML/JS ; pas de bouton « modifier/exporter » factice. |
| Guards | G01–G10, cinq fichiers, avant/après et contre-exemples exacts | Pas d'exemption générique, toutes autres assertions conservées ; manifests historiques vérifiés sur leurs blobs. |
| Test et preuve | Ciblés, global SYNTHETIC_AUTHORIZED, navigateur, puis génération réelle séparée | Résultats actuels NOT_RUN. L'exclusion unique réelle doit être réapprouvée pour R2. |
| Coût live | Un appel ; plafond proposé 0,140000 USD, conditionnel | Calcul historique prudent 0,131072 USD ; prix et borne tokens à vérifier avant autorisation, pas promesse actuelle. |

Les limites de taille/mémoire sont nouvelles et explicitement proposées : elles visent un seul sujet d'une heure et empêchent croissance non bornée, traitement arbitraire ou attente HTTP bloquante. Elles ne remplacent aucun vocabulaire/default SQLite.

La conservation d'un reçu technique one-shot externe est strictement une protection de dépense/replay, pas une persistance de contenu. Une perte de connexion ne prouve jamais l'annulation côté fournisseur.

## 3. Inventaire fermé et portée de guards

60 fichiers futurs : 45 créations dont l'absence a été contrôlée, 15 modifications liées à leur SHA PRE complet. La pièce JSON est l'autorité de chemins, owners, rôles et liens Cxx/Txx ; aucune liste implicite additionnelle.

Répartition pratique :

- F01–F07 : HTTP et inbounds Application.
- F08–F13 : contexte M07 et commande de création M04.
- F14–F23 : conversation, ports/stores/job et lecture CAP-R02 M08.
- F24–F33 : store réel volatile, pont génération, enfant, bindings et composition, extension OpenAI opt-in.
- F34–F36 : interface dans les trois assets existants.
- F37–F41 : cinq fichiers de guards évolués.
- F42–F54 : onze fichiers de tests et deux supports synthétiques.
- F55–F59 : ADR, contrat actif et preuves d'implémentation neufs.
- F60 : CLI locale, activation R2 et fichier d'autorisation explicite ; mode READ-15/R1 inchangé par défaut.

Aucun nouveau __init__.py, dépendance, lock, schéma de configuration, migration, table utilisateur, registry agentique ou module de shared_kernel n'est prévu. Les ports/DTO neutres sont placés dans les packages existants ; les imports utilisent leurs chemins explicites.

| Guard | Delta proposé seulement |
| --- | --- |
| G01 | Registre AST/documenté/importé identique à l'oracle littéral neuf routes, quatre noms de templates neufs. |
| G02 | Inventaire courant fixe sur 19c42..., liste exacte60 ; groupe17 historique intact + groupe4 préparatoire hashé séparément. |
| G03 | Ancien fichier security pure : double preuve historique/PRE/POST et AST authorize_request intact ; schéma HTTP et autres anciens contrôles inchangés. |
| G04 | Seule égalité finale de l'ancien A7/G03 ResourceRef, tuple neuf routes ; six assertions précédentes inchangées. |
| G05 | Un node Phase F, chemins backend R2 exacts en plus des historiques ET inventory_violations. |
| G06 | Cardinalité5→9 dans un seul node unitaire ; reste du corps et des tests conservé. |
| G07 | Cardinalité active9 avec maintien explicite des cinq routes R1 historiques. |
| G08 | R1=30 vérifié sur diff historique fermé ; R2=60 et baseline fixe contrôlés avant/après commit. |
| G09 | Comparaison AST à deux étages : R1 historique puis R2, sans autoriser d'autres nodes. |
| G10 | Deux seuls anciens réemplois read-only qui évoluent : API local_browser.py et CLI local_browser.py ; les31 autres restent byte-identical. |

Les helpers nouveaux de preuve historique sont dans T11, pas ajoutés aux anciens fichiers pour contourner leurs ensembles de fonctions. Les ajouts de constantes/imports des cinq guards se limitent à ceux explicités dans le JSON. Le nouveau guard vérifie lui-même l'allowlist de nodes et l'inventaire contre les constantes approuvées, pas contre une liste librement régénérée depuis le code.

Les 17 documents H1/H1A/préparation R1 sont ceux de la preuve R1, SHA actuels vérifiés17/17 ; ils restent hors commit. Les quatre pièces R2 sont une catégorie séparée. Pour l'implémentation, leur manifeste réellement livré et approuvé sera épinglé par le guard ; aucun compteur17 ne devient21 par substitution silencieuse.

Les manifests READ-15/R1 ne changent pas. Une empreinte de fichier destiné à évoluer ne se « répare » pas rétroactivement : preuve des anciens blobs Git aux baselines de leur phase, PRE R2 sur19c42..., puis nouveau manifeste de réalisation. Les SHA futurs restent null avant création réelle.

## 4. Permissions à décider séparément

### P_IMPL — implémentation et validations synthétiques

Décision propriétaire : non renseignée.

Objet proposé : les60 chemins et G01–G10, ADR revu avant implementation, boucle locale, Python3.12 et outils déjà installés, un sous-processus supervisé, fixtures SQLite neuves strictement synthétiques hors dépôt, mémoire de travail et logs privés externes, reçu technique de tests externe, configuration limitée aux processus, validations ciblées/globales et un commit local cohérent après succès.

L'accord doit couvrir explicitement la seule exclusion :
tests/non_functional/test_retrieval_quality_real_gate.py.
La gate réelle reste NOT_RUN / NOT_PASS. Aucun autre ignore/skip/xfail ajouté, aucune ancienne exclusion reconduite par simple habitude.

Aucune permission données utilisateur, même stat/exists/hash/découverte d'alias/sidecars ; aucune configuration persistante, installation, réseau externe, fournisseur, résolution de credential, push, merge ou H3. La recette navigateur synthétique peut être incluse, sans génération réelle.

### P_DOC_NETWORK — vérification distante documentaire ciblée

Décision propriétaire : non renseignée.

Lecture uniquement des pages publiques officielles OpenAI nécessaires : modèle/profil Terra, pricing, Responses/schema structuré, effortLOW, limites/tokens, store/rétention et paramètres supportés. Aucun API call de génération, authentification, test live, transfert pédagogique ou téléchargement de dépendance.

Ce n'est pas une nouvelle sélection générale de modèles. Source locale historique retenue datée2026-08-28 ; vérification actuelle non faite. Si cette vérification prouve une incompatibilité, rapporter le delta exact (modèle, paramètre, borne, coût) ; aucune substitution automatique ni réouverture d'un chantier bibliothèque.

### P_LIVE — démonstration de génération réelle

Décision propriétaire : non renseignée ; aucune ancienne approbation réutilisable.

Préconditions de décision : baseline de code exécutée/validée figée, profil et code/contrat exacts, serializer final offline, projection et pricing hashés, preuve de compatibilité et borne tokens, mécanisme de credential choisi sans exposer sa valeur, plafond recalculé et approuvé, reçu one-shot prêt.

Proposition chiffrée, non autorisée : un appel à https://api.openai.com:443/v1/responses, gpt-5.6-terra, effortlow, output4096, timeout90s, job120s, storefalse, toolsnone, zéro retry/fallback/rerun. Les données proposées sont exclusivement les champs confirmés et trois passages synthétiques C13. Pas de transfert d'historique, seed, base, document complet, réponse historique ou secret supplémentaire.

Le plafond proposé0,140000 USD n'est pas validé à date : le calcul0,131072 USD utilise le prix documentaire historique et une borne prudente d'entrée de32768 tokens qui doit être justifiée. Si cette preuve ne peut être établie avec les paramètres proposés, ne pas autoriser le dispatch. Ne jamais faire un appel gratuit supposé pour mesurer l'entrée.

Le mécanisme de credential doit être explicitement choisi (réemploi configuré ou autre source déjà autorisée). La référence proposée openai.r2.generation n'affirme ni qu'un secret existe ni qu'il est accessible. Le processus enfant live n'hérite pas d'un endpoint/proxy/credential ambiant. Après tentative, permission consommée, même échec/timeout/effetinconnu ; aucune relance.

Les champs owner, signature, timestamp, hashes futurs et approbations restent null dans la pièce02. Les phrases descriptives de ce document ne sont pas des signatures.

## 5. Ordre de réalisation, un seul jalon R2

Les étapes ci-dessous sont internes à R2 et non de nouveaux lots publics.

1. Vérifier les permissions effectives, le SHA du manifeste approuvé, HEAD19c42..., diff technique,45 absences,15 SHA PRE,17 historiques et4 pièces. Aucun reset/stash/clean. Bloquer sur un vrai drift en indiquant les paths/digests exacts, pas nouvel audit général.
2. Rédiger/revoir F55 selon les décisions approuvées et créer F56. Établir l'oracle de routes/inventaire/guards et les contrats neutres avant d'implémenter ; ne pas committer une suppression de guard seule.
3. Réaliser contexte confirmé M07, entrée création M04, conversation/jobs/idempotence M08, store volatile et CAP-R02 exact. Testables avec doubles, sans exposer ces doubles dans le produit.
4. Raccorder AG01/runtime/policies, EvidenceAgent/admission/OP13, GeneratorAgent/GenerationCoordinator/guard et C08 via bindings/composition. Ajouter uniquement l'opt-in R2 au mapping OpenAI. Aucun éditeur de registry, runner parallèle, import calibration ou preuve source inventée.
5. Réaliser commandes HTTP, framing/nonce/Origin, enfant et watchdog bornés, factory/CLI opt-in, interface conversation et lecture de candidate. Préserver les comportements R1/default. Le produit sans grant ne génère rien et affiche une erreur explicite.
6. Exécuter T01–T11 et non-régressions réemployées, puis suite globale synthétique, lint, typecheck, compileall et contrôles de livraison. Corriger les défauts ordinaires à l'intérieur des60 fichiers dans ce même incrément. Recette navigateur séparée.
7. Finaliser offline F58 : projection exacte issue des fixtures C13, profil/output-contract/cost-policy/calllimit, hashes et preuves de compatibilité disponibles. P_DOC_NETWORK, si accordé, sert seulement à terminer cette vérification documentaire ciblée. Sans cet accord, conserver la valeur non vérifiée ; pas de faux LIVE_READY.
8. Après validations synthétiques réussies et accord de commit explicite, produire un unique commit local cohérent F01–F60, code+tests+guards+ADR+preuves. Les17+4 préparatoires restent hors index ; pas d'autre fichier. F57 mentionne honnêtement live/browser NOT_RUN lorsque nécessaire, F59 ne s'auto-référence pas. Vérifier ensuite hashducommit, diff fixe, statut et gates documentées autorisées.
9. L'autorisation P_LIVE ultérieure est liée à ce commit concret, pas à un SHA imaginé ici. Après accord seulement : une démonstration du même R2, reçu externe, candidate réellement générée, UI/références/versionexacte vérifiées. Les nouvelles preuves live/réception sont privées hors dépôt et minimisées ; pas de second commit automatique pour les intégrer, pas de contenu généré dans Git. Un complément documentaire suivi, si souhaité, demanderait son autorisation exacte. Cette distinction évite un cycle de hash commit/manifeste/autorisation.
10. Livrer le résultat réel avec preuve séparée ; ou annoncer R2_SYNTHETIC_WIRING_ONLY si live non autorisé/indisponible/échoué. Arrêter. R3 reste la prochaine priorité, aucun chantier bibliothèque, R4/R5/H3 non démarrés.

Une validation synthétique suffisante pour figer le code ne vaut pas clôture du produit réel. Un échec technique live ferme l'autorisation et le résultat reste incomplet ; la réponse est un diagnostic borné, pas un retry.

## 6. Validation exécutable future — ne pas lancer maintenant

Procédure limitée aux dépendances présentes. Aucun pip install de ENVIRONMENT n'est autorisé par cette préparation ni par le seul accord synthétique proposé ; l'installation nécessite son droit propre si l'environnement manque. Ne pas rechercher une clé ou une base pour rendre la suite verte.

L'exécutant choisira le Python3.12 déjà installé et des nouveaux sous-dossiers du temp système hors dépôt. Les commandes ci-dessous sont des gabarits, pas des commandes exécutées ; les marqueurs de chemin doivent être résolus vers ces seules cibles temporaires autorisées.

- python --version puis python -m pip check, hors réseau.
- python -m pytest -q -p no:cacheprovider --import-mode=importlib --basetemp <temp-cibles> <11-fichiers-T01-T11> <guards-évolués-et-conservés> <tests-de-réemploi>.
- python -m pytest -q -p no:cacheprovider --import-mode=importlib --basetemp <autre-temp-global> --ignore=tests/non_functional/test_retrieval_quality_real_gate.py.
- python -m ruff check . --no-cache.
- python -m mypy backend --cache-dir <temp-mypy>.
- python -m compileall backend avec PYTHONPYCACHEPREFIX externe.
- git diff --check, statut tracked/index/untracked, inventaire fixed-baseline, historique/PRE/POST/manifeste, contrôles de secrets/données runtime sur le seul diff autorisé.

Les listes concrètes de tests sont la réunion sans doublon de test_plan.path, des cinq paths guard_evolutions, des tests existants de reuse_wire_implement_gap et de preserved_architecture_guards. Les tests non exécutés, skips préexistants et avertissements ont leurs propres comptes et explications ; aucun « tous PASS » si des catégories restent NOT_RUN.

L'environnement de tests doit être construit pour l'enfant à partir d'une allowlist minimale, sans affichage/inspection préalable des valeurs de credentials ou de chemins métiers. Aucun opt-in réel hérité. PROJET_V2_CANONICAL_DB, PROJET_V2_RUNTIME_DB, les alias legacy et les flags RUN_F2B_OFFLINE_R1 / RUN_F2B_LIVE_SEMANTIC_BENCHMARK / RUN_PEDAGOGICAL_LIVE_CALIBRATION ne sont pas transmis. Les fixtures injectent leurs seules cibles temporaires synthétiques au niveau test ; ne jamais remplacer le seed réel par une fixture dans la configuration de l'utilisateur.

Motif précis de l'exclusion unique : test_retrieval_quality_real_gate.py n'a pas de skip d'entrée ; il charge la configuration, appelle is_file sur le seed puis snapshot/inspect. Les autres gates consultées ont des opt-ins ou skip sur absence de variable avant accès au fichier. Ne pas activer ces variables, même pour « voir si la base existe ». Revalider statiquement l'absence d'autres accès incontrôlés avant exécution ; si un risque réel subsiste, rapporter le delta exact, sans exclusion cachée ni tentative.

Aucun log/cache/bytecode/JUnit/fixture dans le dépôt. Les données candidate peuvent être rendues et gardées en mémoire du processus conformément à C11 ; elles ne peuvent pas être copiées dans les logs de preuve. OBS reste5MiB×5/14jours/flush≤2s.

## 7. Prompt d'implémentation conditionnel complet

Le bloc suivant est le mandat futur, non activé par la demande actuelle. Il n'autorise pas lui-même une action.

> Implémente intégralement R2 H2_CONVERSATIONAL_GENERATION_V1 / CONVERSATION-HTTP-LOCAL-1.0 sur la baseline19c42bc9f4b0b1a97b9bd2d6b880acd7378459f7, uniquement si le propriétaire a réellement approuvé P_IMPL et le SHA du manifeste de ce paquet. N'interprète pas un champ null, une recommandation ou une ancienne approbation comme un accord.
>
> Commence par vérifier l'approbation, les trois pièces/hash du manifeste, le HEAD/diff et tous les SHA PRE/45 absences. Conserve les17 documents historiques hashés et les4 pièces préparatoires séparés/hors commit. N'effectue ni reset, stash, clean, découverte de données privées ni élargissement d'inventaire.
>
> Réalise le résultat C01–C18 avec exactement les60 chemins de la pièce02 et G01–G10. Adopte le nouvel ADR approuvé avant de modifier l'architecture. Implémente le dialogue français et le contexte confirmé M07, la création M04, la conversation/CAP-R02 M08, les stores volatils et les contrats neutres. Ne déplace pas l'ownership vers M03, HTTP ou les agents.
>
> Réemploie les symboles REUSE et fournis les bindings WIRE, puis les composants IMPLEMENT/GAP prévus : WorkflowSelector/PlanCompiler/PlanExecutor/RoutingStepRunner/prelaunch/policies/budget, AG02 avec admission et contenu OP13, AG03/GenerationCoordinator/GenerationOutputGuard et ProductionCandidate. Aucune autre définition C08, aucun AG05, runner/budget/catalogue parallèle, import tests/calibration en produit ou capability supplémentaire.
>
> Le serveur stdlib accepte seulement le registre neuf routes fermé, les deux POST protégés par Host/Origin/nonce/intent et les corps JSON bornés. GET ne génère ni credentiallookup ni état nouveau. READ15/search demeurent inchangés, version_ref/include toujours dépréciés sur READ15. L'enfant supervisé est unique, non interactif, IPC borné, deadline120s, SDK90s, aucun retry, arrêt≤5s. UNKNOWN et reçu one-shot empêchent tout rappel.
>
> La demande pilote passe par clarification explicite, confirmation, evidence synthétique admise, candidate structurée substantielle, affichage non actif CANDIDATE/NON VALIDÉE, puis lecture production/versionexacte sans appel provider. Les références déclarées utilisées sont contrôlées comme sous-ensemble des transmises ; aucune fausse source officielle. Le stockage en mémoire est réel, borné et perdu au redémarrage ; R3 review/correction/validation et R4 durable/export ne sont pas implémentés.
>
> Teste d'abord avec les doubles exclusivement dans les supports autorisés. Exécute T01–T11, les tests réemployés, les guards anciens/nouveaux et les outils ENVIRONMENT dans l'environnement isolé prescrit. La suite globale n'exclut que test_retrieval_quality_real_gate.py si P_IMPL le couvre explicitement ; aucun nouveau skip/ignore/xfail. Utilise uniquement fixtures SQLite neuves synthétiques et temp/logs/caches hors dépôt, aucun accès aux données utilisateur même métadonnées ou sidecars.
>
> Corrige dans ce même incrément les défauts ordinaires qui restent dans les60 chemins et G01–G10. Un besoin vraiment hors scope doit être rapporté sous forme de paths/assertions/permissions delta exacts, sans réaudit général, nouveau dossier de préparation ou route de contournement.
>
> Le produit réel conserve l'adaptateur OpenAI déjà présent avec son extension opt-in R2. Sans grant valide, credential/source choisie, prix et borne input attestés, aucun dispatch. Pas de mock caché. P_DOC_NETWORK doit être accordée séparément pour la vérification officielle ciblée ; sinon la compatibilité distante reste non vérifiée. P_LIVE doit être accordée séparément, sur les identities finales et le plafond exact ; aucune calibration ou autorisation B05/R1 n'est réutilisable.
>
> Après tests synthétiques/lint/typecheck et contrôles du diff réussis, et seulement si le droit de commit est explicite, réalise un seul commit local cohérent des60 chemins. Pas de commit isolé neutralisant un guard. Laisse les17+4 préparatoires inchangés et hors commit ; livre les SHA et preuves. Aucune sortie générée, base, secret ou runtime dans Git.
>
> La génération réelle n'est effectuée qu'après approbation one-shot P_LIVE liée au commit concret, profil/schema/pricing/projection et borne tokens vérifiés. Un appel maximum, transfert minimalC13, aucun Anthropic/fallback/retry/rerun. Toute tentative consomme le droit ; erreur/timeout ferme la séquence. Conserve reçu et preuves minimisées hors dépôt, ne lance aucun second commit automatique.
>
> Annonce séparément tests synthétiques, recette navigateur, génération réelle, limites pédagogiques et statut de CAP-R02. Sans preuve réelle réussie, R2_SYNTHETIC_WIRING_ONLY, jamais R2_PRODUCT_COMPLETE. Arrête après livraison R2, sans push/merge/H3/R3 automatique ni perfectionnement de bibliothèque.

## 8. État de cette intervention et réserves utiles

Préparation seule : code/guards/locks/config inchangés ; pas de tests techniques, import applicatif, serveur, SQL, donnée utilisateur même métadonnée, réseau, fournisseur, credential, staging, commit, push ou merge. Les contrôles réalisés sont documentaires : archive/SHA, lecture ciblée, listes de paths, JSON, empreintes PRE/protection et diff.

Cette décision clôt la préparation demandée, pas le produit R2. Le JSON contient les absences concrètes avec leur solution dans l'inventaire, pas une demande de deuxième audit.

Réserves explicites :

- Les sept annexes Phase8 et le livrable exact12.1 restent non identifiés ; les originaux0/11 disponibles ont été lus. Aucun contenu manquant n'a été inventé.
- CAP-R02 et le contexte/conversation Application n'existent pas encore sous leur forme requise ; le paquet fournit leurs owners, ports, DTO, fichiers et tests. Les anciens états NOT_IMPLEMENTED restent des preuves historiques inchangées.
- L'adaptateur OpenAI actuel ne prouve pas quelles références ont été utilisées ; l'opt-in R2 est un delta explicite nécessaire, pas une attribution automatique de toutes les références.
- Le profil/modèle/pricing/support et la majoration tokens ne sont pas revérifiés à date. LIVE_PLAN_FULLY_AUTHORIZABLE=FALSE jusqu'à la vérification/liaison/approbation ciblée. Le plafond0,140000 USD est une recommandation conditionnelle, aucun budget accordé.
- Une chaîne synthétique fonctionnelle n'est pas une génération réelle ; un sujet généré n'est pas une validation pédagogique. Les deux distinctions restent des critères de livraison.
