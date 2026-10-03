# R2 — Contrat de réalisation de la génération conversationnelle

Statut : PROPOSED_NOT_APPROVED. Préparation documentaire uniquement, 5 septembre 2026.
Baseline exacte : 19c42bc9f4b0b1a97b9bd2d6b880acd7378459f7.
Identifiants proposés : H2_CONVERSATIONAL_GENERATION_V1 / CONVERSATION-HTTP-LOCAL-1.0.
Les règles C01–C18 ci-dessous sont des propositions techniques fermées, pas des permissions déjà accordées.

## C01. Mandat, sources et portée

Un seul incrément R2 réalise demande française → clarification → contexte confirmé → AG01/AG02/AG03 → candidate → lecture de sa version exacte. R1 est livré ; aucun nouveau chantier de bibliothèque. R3 garde la review, les validations déterministes et la modification ciblée ; R4 garde sauvegarde durable, promotion, export et reprise après redémarrage ; R5 garde les données réelles. Aucun H3.

Le mandat entrant et ses sept pièces ont été vérifiés en lecture d'archive : 7/7 empreintes conformes. SHA du ZIP entrant : 884f1b2ac292d692eed2fe546972c67596a8611682d7a92499a86d28c67a77bb ; SHA de son manifeste : 59eb9a34aff3db5fbf68549346ef3dccf9f392eaa9d17d015c12138b058ef4ed. Le prompt n'est pas une preuve de réalisation ni une approbation propriétaire.

Sources effectivement rapprochées :

- Phase 0 originale, PDF fourni dans le bundle H1A antérieur, 19 pages extraites/lues : SHA 8b01991be6ff068c4e3a67fcf9bc4d8943b3cedefde0c6ff706ea760192ba496. Sections 0.1, 0.4, 0.5, 0.8, 0.9 : demande naturelle, contexte, parcours progressif, distinction vérification/conservation. Lecture textuelle, pas certification de mise en page.
- Phase 11 originale du même bundle, corps et tableaux DOCX lus : SHA 9a303daef5fbfd60696d486b6cbb02639e2bb685ad33721a78230678b0b3b293. Sections 2–14 et P11-CORE : quatre agents, effets Application, WF-4, mémoire/evidence/contexte/logs distincts, PermissionScope, budget et unknown.
- Feuille de route complète jointe, SHA 10c7fc1114c4203948cc7be476864810cb5a39fceb66e47851bf57826aea12a4. Son état initial « R1 non implémenté » est historique : la baseline et le mandat courant établissent R1 livré ; l'ordre R1→R2→R3→R4→R5→R6→R7→R8 reste inchangé.
- H1A : 01_SOURCES_ET_ECARTS_RECONCILIES.json et 03_PAQUET_DECISION_ET_PLAN_H2.md ; décisions D-SOURCE/D-GUARD/D-INCREMENT et extension A7 reprises dans ADR-P12-069 et le contrat READ-15. Originaux/manifests historiques inchangés.
- API_HANDOFF.json B09 : CAP-R02 appartient à backend.modules.work_orchestration.application et précède CAP-A01 puis CAP-A02. Le registre runtime contient déjà application.read_production ; la lecture des fichiers actuels confirme l'absence du use case et des ports concrets correspondants. L'étiquette historique NOT_IMPLEMENTED n'est pas utilisée seule comme preuve.
- Contrat/evidence/manifeste R1, ADR lexical et READ-15, ENVIRONMENT, trois locks et sources ciblées listées avec SHA dans la pièce 02. Les résultats R1 restent historiques, non réexécutés.

Les sept annexes Phase 8 manquantes et le livrable exact 12.1 non identifié ne sont pas reconstitués. Ce contrat neuf ne prétend pas restituer les 54 opérations/11 écrans. Aucun accès à une base, à ses sidecars, à une runtime utilisateur ou à leurs métadonnées n'a eu lieu. Le manifeste R1 a également été revérifié sur les octets sources/documentaires courants inchangés : 29/29 conformes ; cela reste un contrôle documentaire, pas une réexécution de R1.

## C02. Owners et réemploi concret

| Responsabilité | Owner et raccordement recommandé | Existant / travail R2 |
| --- | --- | --- |
| Contexte pédagogique | pedagogical_context, chemin M07 de REPOSITORY_STRUCTURE ; contrat DTO et service purs | ContextOrigin existant est technique, pas un contexte pédagogique. Ajouter le DTO confirmé et la normalisation/clarification, ne pas changer son vocabulaire stocké. |
| Demande de création | pedagogical_design.application.commands.create_conversation_draft, M04 | Owner de la création métier proposé ici, pas M03 ni routeur technique. Contrat et ports de création à développer. |
| Conversation et candidate courante | work_orchestration.application.services.conversation, M08 dans la structure du dépôt | Owner de session métier, idempotence et suivi du travail ; ne pas confondre SessionLifecycleStatus existant avec le nouvel état du job. |
| Lecture versionnée | work_orchestration.application.queries.read_production | Matérialiser CAP-R02 selon B09 : DTO, ports, query, read model et inbound C-12/C-13. |
| AG01 | WorkflowSelector → PlanCompiler → PlanExecutor + RoutingPreLaunchGuard/RoutingStepRunner → OrchestrationCoordinator | Réutiliser les classes existantes. Nouveaux bindings concrets en composition ; ni nouveau runner canonique, ni moteur WF local, ni nouvel agent. |
| AG02 | EvidenceAgent.search_evidence/fetch_evidence_item/build_evidence_set ; RetrievalCoordinator et trois ports existants | STRUCTURED + LEXICAL seulement, port F2A explicite ; OP11/OP13 existants derrière adaptateurs injectés. Aucun appel HTTP à R1. |
| AG03 | GeneratorAgent + GenerationCoordinator + GenerationOutputGuard + ProductionCandidate | Générer puis évaluer le guard puis build_candidate ; aucune fabrication HTTP ou substitution par un double en produit. |
| Provider | build_openai_generation_adapter → OpenAIGenerationAdapter → OpenAISDKResponsesTransport | Adaptateur réel présent ; extension opt-in R2 de son mapping, pas un second générateur ni scorer de calibration. |
| Hôte/UI/OBS | local_browser factory, LocalRead15Server/Service, trois assets, LocalObservabilitySession | Même stack stdlib et même serveur ; extension explicitement activée ; journaux OBS_A inchangés. |

Les numéros de module sont indicatifs de REPOSITORY_STRUCTURE ; les chemins de bounded context gouvernent les imports. La docstring de SessionLifecycleStatus mentionne encore « M05-owned » : cette divergence de commentaire n'est ni une nouvelle décision d'ownership, ni une raison de modifier son vocabulaire dans R2.

Frontières : HTTP ne dépend que d'inbounds Application et de DTO de transport. Aucun import backend.modules, SQL, SDK ou outbound dans API. Les modules n'importent pas agent_runtime/SDK/infrastructure. Le port sortant de M04 transporte brief/contexte et vue de résultat neutres ; l'adaptateur outbound traduit vers les contrats AG et projette le vrai C-08. Cette vue n'est pas une seconde définition de ProductionCandidate. M08 n'appelle M04 qu'au travers de son port/contrat public, via le job injecté.

CAP-G01 reste une capacité agentique AG03 : ne pas l'inscrire comme capacité Application dans UseCaseRegistry. Le navigateur entre dans une commande Application typée ; ce use case demande un service technique via son port. CAP-R02 reste routable par l'inbound Application et le registre existant. Pas de nouvel accès agent aux stores ; aucun agent_tools générique, aucune capability inventée.

## C03. Demande, contexte et clarification

Une seule conversation active par processus, utilisateur local unique ; pas de comptes, cookie-session ou ACL multi-utilisateur. Les champs de contexte suivants constituent un contrat R2 neuf et borné, non un alignement inventé avec les valeurs SQLite. Tous sont requis avant génération du contrôle ; aucun défaut pédagogique silencieux.

| Champ | Type et borne R2 proposés | Comportement |
| --- | --- | --- |
| resource_type | chaîne exactement ASSESSMENT | « contrôle »/« évaluation » proposés comme correspondances FR ; autre famille signale R6 hors tranche. |
| level | FIRST_STMG, FINAL_STMG, BTS_CG_YEAR_1, BTS_CG_YEAR_2 | Seul BTS CG sans année reste ambigu. Aucune année déduite automatiquement. |
| discipline | chaîne NFC 1–120 caractères | Déclarée/confirmée, aucune discipline officielle inventée. |
| topics | 1–8 chaînes NFC distinctes de 1–120 caractères | Notions déclarées ; texte conservé, pas résolution d'ID canonique fictive. |
| objectives | 1–6 chaînes NFC distinctes de 1–240 caractères | Objectifs explicitement confirmés, pas de compétences officielles présumées. |
| difficulty | GUIDED, STANDARD, ADVANCED | Vocabulaire produit proposé, non reprise d'un default stocké. |
| duration_minutes | entier strict 5–240, bool rejeté | 1 h → proposition 60 ; incohérence explicite à clarifier. |
| total_points | chaîne décimale canonique >0 et ≤100, au plus 2 décimales | Exemple "20" ; Decimal, pas float binaire ni bool. |
| language | exactement fr | R2 pilote français seulement. |

Message : chaîne non vide, NFC, ≤4 000 points de code et ≤12 KiB UTF-8 ; LF autorisé, CR normalisé vers LF ; NUL, autres contrôles C0/C1 sauf tab/LF, bidi de contrôle et surrogates rejetés. JSON duplicate keys, NaN/Infinity, valeurs de type erroné et propriétés inconnues rejetés. Aucune troncature silencieuse.

Le service déterministe de clarification interprète les formulations nécessaires au pilote, les durées/points et les réponses explicites à une question active ; il n'est pas présenté comme compréhension générale d'un LLM. Extraction = proposition avec citation du message source et statut PROPOSED ; un contrôle de confirmation éditable permet de préciser toute formulation non reconnue. « BTS CG », années contradictoires ou changement « 45 min » après « 1 h » déclenchent clarification. Pas de parsing naïf attribuant la dernière valeur sans l'exposer.

Le message naturel reste la demande principale et l'historique reste visible. L'utilisateur peut compléter « deuxième année, difficulté standard… », corriger un champ et répondre à la clarification sans retaper tout le besoin. Le formulaire sert à confirmer ce contexte, pas à remplacer la conversation par un formulaire de bibliothèque. Toute modification substantielle invalide la confirmation précédente et exige nouvelle révision avant génération.

Les textes utilisateur/evidence/modèle ne peuvent définir capabilities, PermissionScope, profile, modèle, endpoint, coût, deadline, gate, retry ou outil. Une instruction « ignore les permissions » reste non autoritative ; les champs structurés d'autorité sont rejetés.

## C04. Conversation et commandes Application

ConversationView, fermée :

- conversation_id : "conv:" + 32 hex minuscules, généré par Infrastructure à l'ouverture explicite R2 ; jamais choisi par le client.
- revision : entier monotone positif ; messages : au plus 20 messages utilisateur + 20 réponses locales, texte agrégé ≤64 KiB UTF-8.
- Chaque message : message_id ("msg:" + 32 hex), role USER ou ASSISTANT, text, created_at UTC, based_on_revision. Les réponses ASSISTANT locales portent response_kind CLARIFICATION, CONTEXT_SUMMARY, STATUS ou OUT_OF_SCOPE, sans prétendre provenir du modèle.
- current_request_id ; context proposé/confirmé ; missing_fields ; context_revision et confirmed_context_sha256 (ou null).
- current_candidate : null ou paire production_ref/version_ref exacte ; génération ultérieure ne mute jamais cette paire existante.
- active_generation : null ou generation_id, state, error_code, production_ref/version_ref optionnels selon état.
- retention : VOLATILE_UNTIL_PROCESS_EXIT ; expiration : au plus 2 h depuis démarrage. Après échéance aucune nouvelle commande ; arrêt/reprise explicite requis.
- capacité : trois candidates et trois jobs au maximum par session ; budget/autorisation live peuvent imposer moins (pilote = un seul appel). Rejet SESSION_CAPACITY_REACHED sans éviction silencieuse.

Messages App : AddConversationMessage(command_id, conversation_id, expected_revision, text, context_patch?, confirm_context?). context_patch accepte seulement les champs C03 ; confirm_context est false par défaut. Une confirmation true exige tous les champs valides et non ambigus ; le serveur normalise et renvoie le contexte exact confirmé et son digest. Une correction ultérieure le déconfirme. Aucun effet provider dans cette commande.

Génération App : StartConversationGeneration(command_id, conversation_id, expected_revision, confirmed_context_sha256). Elle exige une demande courante, une confirmation exacte, un profil autorisé, des références admises et un budget pré-réservé. Elle consomme l'autorisation de dispatch et crée le job une seule fois ; aucune réponse HTTP perdue ne recrée le job.

Écriture Application seule : les stores reçoivent des DTO neutres validés ; M08 réserve/réconcilie revision et job en compare-and-set. L'insertion de la vue candidate, le passage du job à CANDIDATE_READY et le changement de current_candidate forment une publication atomique dans le store mémoire. En cas d'échec, l'ancienne candidate reste consultable.

## C05. Registre HTTP fermé

Neuf entrées exactes proposées, dans cet ordre ; aucune route générique /execute, /agents, /tools, /save, /validate ou /promote :

| Méthodes | Route | Fonction |
| --- | --- | --- |
| GET | /api/v2/resources/{resource_ref} | READ-15 inchangé |
| GET | /api/v2/search | R1 q/limit inchangé |
| GET | /api/v2/conversation | Lecture de la conversation, contexte, job et nonce déjà créé au démarrage |
| POST | /api/v2/conversation/messages | AddConversationMessage |
| POST | /api/v2/conversation/generations | StartConversationGeneration |
| GET | /api/v2/productions/{production_ref}/versions/{version_ref} | CAP-R02 exact |
| GET, HEAD | / | index.html |
| GET, HEAD | /assets/app.js | app.js |
| GET, HEAD | /assets/styles.css | styles.css |

Les quatre nouvelles routes n'acceptent aucune query, même vide. READ-15 continue de rejeter version_ref/include ; CAP-R02 exige version_ref dans son chemin distinct, pas dans READ-15. GET/HEAD ne démarrent ni generation, ni job, ni recherche supplémentaire, ni résolution de credential. La lecture de conversation retourne un snapshot existant, pas un bootstrap mutateur.

Les paramètres production_ref et version_ref sont opaques, ASCII ; proposition R2 fermée : production_ref = "prod:" + 32 hex minuscules ; version_ref = "ver:" + 32 hex minuscules. Les DTO M08 valident ces chaînes puis réutilisent TypedEntityRef/VersionRef/ObjectVersionRef, avec entity_type PRODUCTION. Rejeter slash, backslash, %, traversal, fragment et query après décodage UTF-8 unique. Ref invalide = 400 ; ne pas appeler store ni provider.

Méthode connue mais non admise pour route = 405, route inconnue = 404 ; OPTIONS reste 403, aucune préflight CORS. HEAD API reste 405 avec zéro corps. Les routes R2 non activées retournent R2_NOT_ENABLED/404 ; leur présence dans le registre fermé n'autorise pas leur effet. Les cinq entrées R1/READ-15 conservent leurs enveloppes et comportement.

## C06. Framing, sécurité locale et autorité

Bornes héritées inchangées : cible ASCII brute ≤8 KiB, headers bruts agrégés ≤64 KiB, CRLF strict, HTTP/1.0 réponse + Connection: close, bind loopback explicite et aucune reverse DNS. Un seul hôte servi ; pas de fichier statique générique.

Bornes nouvelles uniquement sur les deux POST : Content-Length unique, décimal canonique positif, ≤16 384 octets ; absence = 411, dépassement = 413. Lire exactement cette longueur dans le délai global de lecture de 5 s (headers et corps ensemble). Ne jamais réinitialiser le délai à chaque fragment. Corps tronqué, données excédentaires déjà bufferisées ou framing ambigu = 400, aucun dispatch. Fermer la connexion ; ne pas interpréter une seconde requête pipelinée. Sur GET/HEAD et routes anciennes, Content-Length absent/0 seulement, pas de body ; leur rejet antérieur reste inchangé.

Content-Type exactement application/json, ou application/json; charset=utf-8 (comparaison média insensible à la casse, paramètres fermés). Aucun BOM, gzip, multipart, form, transfert chunked ou encodage alternatif. JSON racine objet et profondeur ≤6. Rejeter Transfer-Encoding même avec Content-Length, headers dupliqués y compris identiques, folding, Expect, Authorization, Proxy-Authorization, Cookie et Content-Encoding. Corps illisible : code fermé, pas d'écho.

POST exige simultanément :
1. route exacte déjà résolue comme commande ;
2. Host canonique conforme au bind/port, port explicite hors port 80 ;
3. Origin présent et exactement égal à l'origine de l'hôte autorisé ; Origin absent, null, autre port, autre alias ou valeur multiple refusé ;
4. Sec-Fetch-Site = same-origin lorsque présent, cross-site/same-site/none rejetés pour les commandes ;
5. X-Local-Intent: conversation-v1 et X-R2-Nonce égal au nonce de démarrage (256 bits, comparaison constante) ;
6. schéma, révision/idempotence, permissions Application et autorisation de coût/transfer scope valides.

Pas de cookie ni CORS, même pour une autre origine locale. Le nonce est une protection CSRF de processus et non une identité métier/permission fournisseur. Le navigateur le lit via GET conversation avec X-Local-Intent; SOP et absence de CORS empêchent un site tiers de lire cette réponse. Ce GET exige cet intent, Host valide, Origin exact si présent et Sec-Fetch-Site same-origin si présent ; Origin absent admis pour le GET same-origin usuel. Origin null toujours rejeté. Ce dispositif ne prétend pas protéger contre un processus hostile déjà exécuté sous le compte propriétaire.

Implémenter authorize_command dans LocalBrowserHttpSecurityContract sans changer la sémantique ni le corps de authorize_request existant. Pas de faux GET pour « autoriser » un POST. Le schéma de configuration CORS/stateful_sessions reste inchangé ; conversation Application volatile ≠ session HTTP persistante/cookie. Le contrôle des routes/nonce précède toute résolution de credential et tout port métier sensible. Aucun header X-* ou message ne constitue à lui seul une délégation.

## C07. Requêtes et enveloppes R2

POST messages, propriétés requises : command_id (UUID canonique minuscule, 36 caractères), conversation_id, expected_revision (entier >0), text. Propriétés optionnelles : context_patch (C03), confirm_context (bool). Toute autre clé est interdite, notamment production_ref, version_ref, provider, model, scope, budget, idempotency_override, system_prompt et tools.

POST generations : quatre propriétés exactement, command_id, conversation_id, expected_revision, confirmed_context_sha256 (64 hex minuscules). Pas de prompt/provider/refs libres dans ce corps : la projection est issue de l'état confirmé et des ports autorisés.

Réponse succès messages = 200 ; génération admise = 202 (ne signifie pas produite) ; lectures = 200. Enveloppe nouvelle : data + meta exactement ; meta = correlation_id, contract_id, command_id (null pour lecture). data messages = ConversationView ; data GET conversation = {conversation: ConversationView, transport_nonce: chaîne base64url sans padding de 43 caractères}. Le nonce n'entre jamais dans le DTO métier ni les logs. data génération = conversation_id, revision, generation_id, state. Identités créées côté serveur, pas de copie d'un ID provider brut. Un replay de commande admise conserve son code initial 200/202 et ses IDs ; GET fournit l'état actualisé.

Réponse CAP-R02 : data = production_ref, version_ref, production_kind, content, sections, pedagogical_context, context_sha256, lineage, references, validation_state, limitations, retention. meta = correlation_id, contract_id, command_id=null. validation_state toujours CANDIDATE. Les textes peuvent être affichés mais jamais interprétés/exécutés ; pas de promesse SOURCE_MATCH ni « validé ».

Erreur R2 : error = {code, field_code} et meta (mêmes clés) ; field_code nul ou enum des noms publics, jamais valeur de champ. Pas de message d'exception, stack trace, chemin, SQL, body, prompt ou réponse provider. JSON erreur ≤2 KiB. Tous les succès R2, enveloppe finale incluse, ≤256 KiB UTF-8 ; si dépassement, pas d'émission partielle, erreur APPLICATION_FAILURE/500. Snapshot conversation ≤96 KiB ; contenu brut de candidate ≤64 KiB ; sections cumulées ≤64 KiB, pour que content + sections + contexte/provenance restent sous 256 KiB.

Codes/statuts fermés :
- 400 VALIDATION_REJECTED, REQUEST_FRAMING_REJECTED, CONTEXT_INVALID, UNKNOWN_FIELD.
- 403 LOCAL_INTENT_REJECTED, ORIGIN_REJECTED, HOST_REJECTED, TRANSFER_NOT_AUTHORIZED, GENERATION_NOT_AUTHORIZED.
- 404 R2_NOT_ENABLED, CONVERSATION_NOT_FOUND, PRODUCTION_NOT_FOUND, PRODUCTION_VERSION_NOT_FOUND.
- 405 METHOD_NOT_ALLOWED ; aucune méthode supplémentaire n'est admise par ce code.
- 409 REVISION_CONFLICT, IDEMPOTENCY_CONFLICT, CONTEXT_NOT_CONFIRMED, GENERATION_IN_PROGRESS, GENERATION_OUTCOME_UNKNOWN, SESSION_CAPACITY_REACHED.
- 410 CONVERSATION_EXPIRED (conversation actuelle expirée connue ; ancien identifiant après restart = 404).
- 411 LENGTH_REQUIRED ; 413 REQUEST_TOO_LARGE ; 415 MEDIA_TYPE_REJECTED.
- 422 CONTEXT_CLARIFICATION_REQUIRED, INSUFFICIENT_EVIDENCE.
- 503 PROVIDER_NOT_CONFIGURED, PROVIDER_UNAVAILABLE, BUDGET_UNAVAILABLE, JOB_UNAVAILABLE.
- 500 APPLICATION_FAILURE, GENERATION_OUTPUT_INVALID.

Les familles M08 restent celles de B09 : validation → VALIDATION_REJECTED ; deux absences distinguées → NOT_FOUND avec sous-code ; erreur technique → APPLICATION_FAILURE. Les codes de transport ne changent pas BusinessError/ApplicationFailure existants. Les erreurs POST ne réemploient pas public_error READ-15.

Précisions de schéma fermé : request_id = "req:" + 32 hex ; generation_id = "gen:" + 32 hex ; timestamps ISO-8601 UTC suffixe Z. current_request_id est null avant le premier message accepté, puis désigne la demande courante. context_revision vaut 0 au départ, puis entier croissant ; missing_fields est la liste ordonnée des noms C03 manquants/ambigus. context = {status: EMPTY|PROPOSED|CONFIRMED, values: objet partiel C03, provenance: tableau de {field, message_id, source_kind: EXTRACTION|EXPLICIT_PATCH|CONFIRMATION}} ; provenance au plus 40 entrées, une par champ et message au maximum. confirmed_context_sha256 est null hors CONFIRMED. Le SHA porte uniquement sur values complet, JSON UTF-8 NFC à clés triées, séparateurs virgule/deux-points sans espace, ensure_ascii=false, valeurs Decimal déjà sérialisées en chaînes C03, sans LF terminal. Il ne dépend ni du timestamp ni de l'ordre de saisie. Toute clé facultative absente est omise, pas convertie implicitement en null.

Dans active_generation, les cinq champs generation_id/state/error_code/production_ref/version_ref sont toujours présents : références null sauf CANDIDATE_READY, error_code null sauf état d'échec/UNKNOWN. current_candidate = null ou {production_ref, version_ref}. production_kind du read model R2 = ASSESSMENT ; content = chaîne de texte structurée non vide ; sections = cinq objets {section_id, text}, section_id dans l'ordre C10, text non vide. pedagogical_context = values confirmé complet C03 ; lineage = exactement les sept champs C11, parent_production_ref null pour création. references = au plus trois objets {evidence_id, source_ref, version_ref, checksum_sha256, locator, provenance_label, declared_used}, issus des trois références transmises, declared_used bool. source_ref/version_ref/locator sont les identifiants synthétiques contrôlés, jamais un chemin ou URL libre ; chaque chaîne ≤240 caractères, SHA64 hex. limitations = au plus 16 chaînes publiques ≤500 caractères, construites par projection fermée et non copie d'une exception/metadata provider ; retention = VOLATILE_UNTIL_PROCESS_EXIT. Une représentation technique fournisseur hors de ces champs n'est pas publiée.

## C08. Durée, concurrence, interruption et idempotence

Choix recommandé : POST court/202 + travail dans un unique sous-processus stdlib non interactif + polling GET conversation. Pas de SSE/WebSocket, broker, queue distribuée, nouvelle dépendance ou ThreadingHTTPServer illimité. Le serveur HTTP reste mono-requête, mais ne bloque pas sur l'appel fournisseur.

Composition injecte un GenerationJobPort ; son adaptateur système est seul propriétaire de subprocess/IPC. Le worker exécute l'Application M04 et la chaîne runtime, pas le serveur. Un enfant actif au maximum, aucune file d'attente, aucun fanout. Launch via executable Python existant, liste argv fermée, sans shell ni fenêtre visible ; stdin/stdout privés au parent, JSON encadré ≤256 KiB, stderr supprimé/minimisé. Aucun secret dans argv ou IPC. Aucun pickle/unpickle. Payload/candidate en mémoire seulement.

Temps proposés : admission/clarification ≤2 s hors débit réseau ; lecture HTTP ≤5 s ; SDK call timeout 90 s ; deadline globale génération 120 s, incluant recherche et startup enfant ; plus aucune soumission après expiration. Le tick non bloquant de service_actions, toutes les 50 ms nominales, récolte le résultat et publie atomiquement via M08. Le watchdog du job est indépendant d'une requête HTTP lente ; un seul superviseur borné en Infrastructure, aucune thread par requête. Le plafond est testé sur horloge injectée et enfant bloqué. L'arrêt du serveur ferme le job puis OBS, flush ≤2 s ; arrêt complet avec enfant ≤5 s proposé, pas réécriture de la limite OBS.

Timeout global/arrêt : demander arrêt de l'enfant, attendre ≤1 s, terminate puis kill si nécessaire et join ≤2 s au total ; vérifier absence d'enfant survivant. État UNKNOWN si un appel a pu partir. Le kill local ne prétend pas annuler la facturation/traitement distant. Refuser tout nouvel appel après UNKNOWN, sans attendre un redémarrage pour oublier l'incertitude.

Conserver l'enfant jusqu'à collecte bornée, sans pipe plein pouvant bloquer le parent ; entrée/sortie de taille maximale vérifiée avant publication. Le worker ne peut pas lancer d'autre worker ; pas de spawn à l'import. Les tests emploient un worker double et aucune API.

Idempotence : index (conversation_id, command_id), hash canonique du corps normalisé, opération et digest du contexte confirmé. Réservation CAS avant dispatch. Même clé/même contenu → retourner même command/job, aucun second appel, même si expected_revision ancienne ; vérifier la clé avant conflit de révision. Même clé/différent contenu/opération → 409. Autre clé pendant IN_PROGRESS → 409. Une réponse 202 perdue ou AbortController client n'est jamais une annulation du travail : GET l'état, ne pas renvoyer POST automatiquement.

L'index d'idempotence est borné à 64 commandes admises par conversation ; un message/une génération invalide avant admission n'y est pas inscrit. Aucune éviction silencieuse ; capacité atteinte = SESSION_CAPACITY_REACHED, zéro effet. Les textes supplémentaires pendant IN_PROGRESS sont refusés par GENERATION_IN_PROGRESS ; les lectures restent disponibles. Le nonce et la révision ne sont pas des clés autorisant une nouvelle tentative provider.

États : CLARIFYING → READY → IN_PROGRESS → CANDIDATE_READY, FAILED_NO_EFFECT, FAILED_OUTPUT ou UNKNOWN. READY exige contexte confirmé ; les changements après une candidate restent une nouvelle demande, sans révision corrective de l'ancienne. Message « modifie le dossier 3 » → réponse OUT_OF_SCOPE R3, maintien de current_candidate, aucun appel masqué. Client peut arrêter l'attente, pas commander un retry/annulation fournisseur fictive.

## C09. Evidence : recherche au service de la génération

Le pilote utilise une fixture SQLite neuve synthétique hors dépôt, explicitement injectée, jamais copie/attachement du seed. Elle sert à la fois la compatibilité READ-15/R1 et les adaptateurs OP11/OP13 d'AG02. Son hash est vérifié avant toute ouverture ; mode query-only/read-only et aucun sidecar utilisateur. Autorisation de lecture synthétique et autorisation de transfert restent distinctes.

Recherche AG02 : request max_items=3 ; policy channel_limit=10, final_limit=3, enabled_channels=(STRUCTURED, LEXICAL), required_channels identiques ; EvidenceAdmissibilityPort explicite obligatoire. La présence dans le résultat STRUCTURED seule ne remplace pas F2A. Pas de canal sémantique, embedding, expansion, reranker ou enrichissement R1. Même snapshot de lecture pour recherche/admission/contenu ; fermer avant la génération distante, afin de ne pas garder une transaction pendant 90 s.

AG02 matérialise un EvidenceSet réel : evidence_id/source_ref/locator/checksum/version, couverture, conflits, limites, label UNTRUSTED. Les 320 caractères UI R1 ne sont pas re-promus en corpus : lire via OP13 les passages admis nécessaires, chacun ≤1 000 caractères, total ≤3 000 ; pas de document entier. Conserver les labels de contenu, assessments et provenance jusqu'à GenerationPreparationRequest ; les références du ProductionRequest correspondent exactement aux éléments transmis. Le contexte confirmé reste pedagogical_context, pas une note noyée dans resolved_inputs.

Absence, refus d'admission, version différente, passage disparu, dépassement ou contenu hostile non isolable : bloquer avant provider avec INSUFFICIENT_EVIDENCE. Pour R2 le mode unsourced n'est pas proposé : ni fallback sur connaissances supposées, ni référence officielle inventée. Les trois notes synthétiques proposées ne constituent aucune preuve d'alignement officiel BTS ; l'UI affiche cette limite.

Résultats fournis vs utilisés : conserver séparément les références admises/transmises et evidence_refs_used déclarées par la génération. Extension opt-in du mapping OpenAI uniquement si output_contract.id = R2-ASSESSMENT-SECTIONS-1.0 : nouvelle propriété evidence_ids_used, tableau distinct d'IDs proposés par le caller, tous dans la liste injectée, pas d'URL/provider-ref. Le parser résout vers les ContractRef d'origine, exige unicité/subset, puis le coordinateur revalide. Liste vide bloque le guard grounding_required. Les références ne sont jamais toutes marquées « utilisées » par défaut. « Utilisée » signifie déclarée par le modèle et validée en portée, non vérification factuelle indépendante R3.

Le schéma legacy outcome/sections/warnings/uncertainties et les autres opérations GENERATE/TRANSFORM/CORRECT restent inchangés lorsque l'opt-in est absent. Ajouter les tests dédiés sans réécrire les tests historiques pour accepter des sorties plus faibles.

## C10. Orchestration et génération réelle

M04 valide le besoin → port sortant neutre → adaptateur de pont → WorkflowRequirements. Ambiguïté : sélection WAITING_HUMAN/WF-10 observée sans compiler/dispatch. Besoin confirmé avec evidence : WF-4 AG02→AG03. Pas de review, correction, promotion, validation ou variantes dans ce Plan ; pas de faux succès WF-11.

PlanCompiler reçoit deux PlanStepBinding fermés : EVIDENCE/CAP-E01/AG02 et GENERATE_TRANSFORM/CAP-G01/AG03, dépendance stricte. Le binding AG02 matérialise le mandat evidence par ses opérations CAP-E01/E02/E03 existantes ; les trois capacités sont explicitement dans la délégation plafonnée, pas dans le texte utilisateur. Au plus trois fetch et un build, comptabilisés ; aucune sous-délégation. CAP-R02 se relit hors génération par Application. La permission Application lecture n'implique aucune permission d'effet.

RoutingStepRunner et RoutingPreLaunchGuard sont les seules implémentations runtime canoniques réutilisées. Les nouveaux fichiers de composition fournissent RuntimeRoutingResolverPort, AgentStepExecutionPort, les scopes et l'évaluateur de complétion. Les handlers de doublure tests ne sont pas importés en produit ; les routes tools/gates non utilisées sont explicitement non liées/refusées, pas des lambdas accordant ALLOW.

Même CapabilityAuthorizationPolicy partagée par agent/tool/usecase routers ; DENY l'emporte ; Scope explicite temporaire lié à run/step, payload/projection et approbation. Les contextes actor/correlation/delegation/security sont générés hors du texte et vérifiés. Budgets via resolve_effective_budget_limits, BudgetState et BudgetAccountingPolicy existants ; aucun second algorithme de budget. Overlay R2 peut seulement réduire à deux steps agentiques, une génération provider, un enfant, zéro retry, zéro replan, zéro review, zéro correction et deadline 120 s. Les appels OP13 bornés sont suivis sans créer des appels fournisseur supplémentaires.

AG03 appelle une fois GenerationPort. Puis GenerationOutputGuard(policy structurée, required/allowed payload "sections", section_container_key="sections", grounding_required=true) et build_candidate existants. REPAIR_REQUIRED/ABSTAIN/REJECT arrêtent sans réparation automatique payante. PARTIAL/ALLOW_WITH_WARNINGS peuvent être affichés comme candidate avec limites explicites, jamais « contrôle prêt à distribuer ».

ProductionDemand attend un véritable sujet exploitable : consignes, cas fictif et annexes chiffrées, trois dossiers avec questions, durée/points demandés. Sections ordonnées exactement : CONSIGNES, CONTEXTE_ET_ANNEXES, DOSSIER_1, DOSSIER_2, DOSSIER_3. Le premier dossier classe/reconstitue, le deuxième calcule FRNG/BFR/trésorerie, le troisième analyse ; les questions et points sont proposés, pas validés. Section vide/générique de type « exercice à compléter » n'est pas preuve de contenu substantiel. Le contrat structurel ne certifie ni calculs ni total pédagogique exact ; leur vérification et correction appartiennent à R3. Aucun corrigé professeur/export ajouté implicitement au pilote.

## C11. Stockage minimal et CAP-R02

Choix soumis à décision : véritable store volatile de processus, pas SQLite pour les productions R2. Il conserve la candidate courante et jusqu'à trois candidates immuables de cette conversation, pendant sa durée bornée. C'est une limite produit explicite, pas un fake de démonstration. Aucun schéma/migration utilisateur ; la candidate est perdue à l'arrêt, comme annoncé dans l'interface.

AG03 conserve son unique ProductionCandidate et production_id. Le pont produit une vue neutre ; M08 ajoute une version opaque immuable indépendante, la référence exacte du contexte, la conversation et le run/step de lineage. Aucun ajout de champ au C-08 ni reconstruction d'une ProductionCandidate dans M08/HTTP. Format de stockage logique : clé (production_ref, version_ref) → ProductionReadView ; index production_ref → ensemble des versions, conversation_id → références autorisées. Publication atomique et refus de collision : une même clé ne peut écraser des octets différents.

ReadProductionQuery.execute(ReadProductionRequest, contexte d'accès de conversation injecté) appelle le port de lecture seul. Ref inconnue dans la conversation → PRODUCTION_NOT_FOUND ; production connue mais version inconnue → PRODUCTION_VERSION_NOT_FOUND ; store indisponible/incohérent → APPLICATION_FAILURE. Version exacte, pas latest/v1 implicite, pas « seule version donc fallback », aucun rappel AG03/provider/READ-15. Deux lectures rendent les mêmes octets métier et lineage, hors correlation. Ancienne production d'une autre session ne fuite pas ; lire avec mauvaise conversation ne révèle pas son existence.

Lineage public limité : source_run_id, source_step_id, source_request_id, conversation_id, context_sha256, evidence_set_ref, parent_production_ref=null pour création. Aucun path, raw metadata provider, checkpoint interne, ACL, secret, prompt système ou pensée privée. La version courante ne remplace pas la lecture exacte. La conservation durable et la révision vN+1 corrective ne sont pas revendiquées en R2.

## C12. Modèle, profil, endpoint et limites proposées

Source locale : PHASE_12_16_C_PROVIDER_MODEL_SELECTION_MATRIX.md sélectionne OpenAI gpt-5.6-terra pour GENERATION ; PHASE_12_16_D décrit l'adaptateur. Le transport actuel est désormais backend/adapters/outbound/openai/transport.py, pas les anciens chemins generation/openai/transport.py de D. Locks actuels : openai==3.8.0 et Python 3.12 ; aucune installation ni import SDK effectué pendant cette préparation.

Recommandation : réutiliser le profil documentaire openai.gpt-5.6-terra.generation avec une configuration effective R2 éphémère, explicitement liée au contrat et sans fallback ; aucune modification de routes runtime persistantes. Modèle exact gpt-5.6-terra, reasoning effort LOW (extension opt-in mapping R2 vers OpenAIResponsesRequest.reasoning_effort existant), max_output_tokens=4096, call_timeout=90000 ms, une requête Responses non stream/background, store=false, tools=[], tool_choice=none, SDK max_retries=0.

Destination proposée : HTTPS api.openai.com:443, chemin /v1/responses. Aucun Anthropic, embedding, fichier-upload, batch ou navigation modèle. Aucun alias automatique ou serveur compatible custom. L'enfant doit démarrer dans un environnement allowlisté sans OPENAI_BASE_URL, proxy, projet/organisation ou credential non autorisé ; SDK configuré uniquement par les objets explicitement approuvés. Si son endpoint effectif ne peut être prouvé sans override ambiant, fail-closed, pas repli. Conserver le transport existant ; pas de nouveau client HTTP.

Credential : contrat ProviderProfileConfig.credential_ref → ProviderSecretResolver.resolve → ProviderSecretValue → transport. Nom proposé de référence : openai.r2.generation ; source de résolution à confirmer par le propriétaire (réemploi configuré ou autre mécanisme déjà admis). Aucun secret, valeur, présence, compte/quota ou workspace n'a été lu/vérifié. La résolution et l'import/configuration live ne sont permis qu'après les permissions séparées C14.

Input_json ≤12 288 octets UTF-8 ; corps technique total prévisible (instructions, schéma, input et paramètres) ≤24 576 octets. Hypothèse prudente de pré-budget : maximum 32 768 tokens d'entrée facturables, incluant 8 192 tokens de marge pour framing ; output ≤4 096 incluant reasoning facturable. Cette majoration doit être justifiée pour le tokenizer/framing du modèle par documentation officielle avant live : ce n'est pas une mesure vérifiée aujourd'hui. Ne pas appliquer une estimation caractères/4 pour autoriser une dépense.

Tarifs historiques de C, vérifiés dans cette source au 2026-08-28 : 2 USD/MTok input, 12 USD/MTok output ; note locale cache write à 1,25×. Calcul prudent proposé : 32 768 × 2,50 / 1 000 000 + 4 096 × 12 / 1 000 000 = 0,131072 USD. Plafond financier recommandé à soumettre : 0,140000 USD pour un seul appel, sans économie de cache supposée. BudgetSpec/ProviderCostLimit utilisent Decimal et ce plafond, pas floats.

Ces prix, l'existence/disponibilité effective du modèle, le support LOW/schema avec SDK verrouillé, les règles de facturation et la majoration tokens ne sont PAS revérifiés à date. Le calcul est documentaire et conditionnel, pas un plafond live autorisé. Aucun crédit historique ni ancienne calibration n'est réutilisé. Tant que le prix et la borne input ne sont pas confirmés, LIVE_PLAN_FULLY_AUTHORIZABLE=FALSE. Ce point n'empêche pas de livrer ici tout le contrat local, tous les fichiers et tests.

## C13. Projection synthétique pilote prête à finaliser

Demande initiale exacte : « Crée un contrôle BTS CG de 1 h sur le bilan fonctionnel et le BFR, noté sur 20. »

Parcours proposé, réponses de test et non décisions du propriétaire :
1. Réponse locale : « Pour quelle année de BTS CG ? Quels objectifs et quelle difficulté souhaitez-vous ? »
2. Réponse synthétique de fixture : « BTS CG deuxième année ; analyse financière ; identifier les emplois et ressources stables, calculer le FRNG et le BFR, interpréter la trésorerie nette ; difficulté standard. »
3. Récapitulatif confirme 60 minutes, 20 points, les deux notions, les objectifs ci-dessus, fr, ASSESSMENT ; bouton « Confirmer le contexte » puis « Générer une candidate » distinct. L'année 2 n'est pas un défaut appliqué à la demande réelle.

Trois passages synthétiques de référence, à inscrire dans la seule fixture de recette, avec cette provenance exacte « SUPPORT_SYNTHETIQUE_R2 — aucune source officielle attestée » :

- r2.synth.bilan : « Le bilan fonctionnel regroupe les postes selon leur fonction : emplois stables, ressources stables, actif circulant d'exploitation, passif circulant d'exploitation et trésorerie. Le dossier fournit les règles de classement et toutes les données nécessaires. »
- r2.synth.bfr : « Pour le cas fictif sans éléments hors exploitation : FRNG = ressources stables - emplois stables ; BFR = actif circulant d'exploitation - passif circulant d'exploitation ; trésorerie nette = FRNG - BFR. Les données doivent permettre de confronter calcul et interprétation. »
- r2.synth.cas : « Entreprise fictive Atelier Horizon. Montants en milliers d'euros : emplois stables 180 ; ressources stables 220 ; actif circulant d'exploitation 85 ; passif circulant d'exploitation 60 ; trésorerie active 18 ; trésorerie passive 3. Aucun retraitement, valeur manquante ou élément hors exploitation n'est à supposer. Créer des questions progressives en trois dossiers, sur 20 points et 60 minutes. »

Ces contenus sont une proposition de fixture, pas une approbation de transfert ni une production modèle. Ils ne viennent d'aucune base utilisateur. Les résultats attendus des calculs peuvent servir à la recette R3 mais ne sont pas ici une validation automatisée R2. Les IDs de registry synthétique sont techniquement admissibles dans la fixture ; cette canonicalité de test n'est pas une source officielle BTS.

Transfert proposé : brief confirmé synthétique, champs C03, ces trois passages admis, leurs IDs/version/checksum synthétiques, expected_sections et output_contract technique. Aucun historique complet de conversation, ancien output, contenu R1 utilisateur, document entier, chemin, seed, sidecar, données personnelles ou secret supplémentaire. Les seules instructions techniques fixes sont celles du mapper revu. La sérialisation effective finale doit être produite offline après implémentation, hashée avec le modèle/profil/schema/pricing et présentée pour l'autorisation live ; aucun hash futur inventé dans ce paquet.

## C14. Permissions distinctes, non accordées

L'approbation éventuelle du paquet pourra autoriser ensemble l'implémentation des 60 fichiers, les évolutions de guards listées, tests Python/HTTP sur loopback, fixture SQLite synthétique neuve, mémoire et logs privés temporaires, sous-processus borné, configuration process-only, contrôles globaux et un commit local cohérent. Cette autorisation n'est pas donnée par le présent texte.

Permission séparée de vérification documentaire réseau : uniquement pages publiques officielles OpenAI de modèle, pricing, Responses, Structured Outputs, limites/tokenisation et rétention ; aucune donnée pédagogique transmise, aucun credential/API modèle, téléchargement de dépendance ou compteur provider consommé. Demande précise, pas nouvelle recherche générale de fournisseurs. Statut NOT_AUTHORIZED.

Permission live distincte après code/validation/identités finales : un appel OpenAI de génération du pilote, baseline exécutable exacte, profil/modèle/effort/output/schema, projection SHA, pricing SHA et plafond final approuvés ; résolution de la seule référence credential choisie ; destination unique ; transfert exact C13 ; reçu one-shot, aucun retry/rerun/second appel. Statut NOT_AUTHORIZED. Les signatures/horodatages restent null dans la pièce 02.

Le reçu technique privé, hors dépôt et hors base, est créé exclusivement par l'adaptateur système à l'aide des primitives filesystem sécurisées existantes : clé = hash de l'autorisation, états RESERVED/DISPATCHED/CONSUMED/UNKNOWN, coût réservé/observé, IDs techniques et timestamps. Aucun contenu, credential ou chemin dans le reçu. Création exclusive et verrouillage avant la première tentative ; jamais effacé automatiquement. Redémarrage avec le même reçu refuse un nouveau dispatch. Erreur avant tentative consignée, pas auto-retry ; échec réseau après dispatch consomme la permission même si résultat absent. C'est une protection d'effet/coût, pas la sauvegarde pédagogique R4.

## C15. Affichage, confidentialité et observabilité

UI dans les trois assets actuels. Demande et historique lisibles, clarification et contexte confirmé visibles, état « génération en cours » réel, ancienne candidate préservée, statut CANDIDATE / NON VALIDÉE bien visible ; bouton de lecture exact-version. Ni bouton « modifier » inopérant, ni bouton « valider/exporter » non raccordé. Pas de Markdown HTML non assaini : textContent/replaceChildren seulement ; aucun lien d'evidence arbitraire actif.

AbortController peut arrêter le polling ; afficher « l'attente est arrêtée, le traitement peut continuer ». Rafraîchissement UI récupère l'état existant et la même version via CAP-R02 sans effet. Pas de localStorage/sessionStorage/IndexedDB/service-worker/cache de prompt, pas d'URL contenant le contenu ni de console.log.

OBS_A inchangée : local NDJSON, rotation 5 MiB, cinq fichiers, rétention 14 jours, flush ≤2 s. Logs HTTP : méthode, route_template, statut, durée, correlation uniquement. Événements runtime existants : IDs techniques/codes/coût/tokens autorisés par leurs schémas ; pas de nouvelles dimensions ou texte libre. Logs ≠ contenu/prompt/réponse provider. Ni nonce, ni pédagogie, ni métadonnée brute fournisseur, ni exception/path/SQL/chain-of-thought. Si un événement existant ne peut porter un champ, ne pas étendre son schéma par opportunité : conserver le reçu technique privé minimal. Une panne de sink ne transforme pas une génération en succès ni en retry.

## C16. Guards, histoire et inventory

Pièce 02 : inventaire exact de 60 fichiers futurs (45 CREATE absents, 15 MODIFY hashés), 10 évolutions de guards dans cinq fichiers et tous tests/protections associés. Aucun « etc. », préfixe de module entier ou voie libre au handler API. Deux POST et deux GET nouveaux seulement. AGs, capabilities, workflows, GenerationPort/C-08, ResourceRef, OBS et locks restent inchangés.

Le contrat R1 et ses 30 chemins sont une preuve historique à 19c42bc9... ; l'inventaire courant R2 s'appuie sur cette baseline fixe, jamais sur HEAD mouvant. Le guard actif ne réécrit pas l'ancien manifest ; les assertions byte-identical qui visent des composants explicitement évolués sont remplacées par double preuve : octets historiques Git à la baseline historique + PRE/POST R2 exact et régressions actives. Les autres assertions sont conservées.

Les 17 fichiers non suivis H1/H1A/préparation R1 restent tous à leur SHA réel. Les quatre nouveaux fichiers préparatoires R2 sont une catégorie séparée, liée au manifeste fourni au propriétaire, hors futur commit d'implémentation. Aucun compteur « 17 » n'est augmenté artificiellement, aucun wildcard documentaire. Les nouvelles preuves d'implémentation sont en phase_12_18_h2_r2_generation, pas dans les originaux.

## C17. Validation future et niveaux de preuve

Tous les tests du paquet sont proposés, NOT_RUN. Les contrôles effectués maintenant sont exclusivement documentaires (archives, SHA, JSON, cohérence/chemins/diff). Ne pas appeler 5211 tests R1 une réussite R2. Les compétences/calculs/qualité restent R3/R8.

La pièce 02 relie T01–T11 aux fichiers futurs et aux guards existants : dialogue, références et vraie chaîne avec doubles, version exacte, Host/Origin/framing, budget/nonce/no retry, enfant bloqué, logs minimisés, routes anciennes, inventaire/AST et imports.

Après autorisation technique : tests ciblés positifs/négatifs, puis SYNTHETIC_AUTHORIZED global avec seule exclusion explicitement approuvée de tests/non_functional/test_retrieval_quality_real_gate.py. Opt-ins réels absents dans l'environnement enfant ; aucun second ignore/skip/xfail ajouté. Les skips préexistants restent nommés et non PASS. Ruff, mypy, compileall, pip check offline selon ENVIRONMENT, caches/JUnit/bytecode hors dépôt, aucun pip install/réseau.

Recette manuelle navigateur distincte de tests HTTP/assets statiques. Génération réelle distincte de double : preuve uniquement après accord live C14 et observation du contenu retourné. Succès structurel/candidate lisible ne vaut pas validation pédagogique ni production distribuable. Sans appel réel autorisé et réussi, livraison R2_SYNTHETIC_WIRING_ONLY, pas R2_PRODUCT_COMPLETE.

## C18. Critères de sortie et arrêt

R2 réel : demande pilote clarifiée, contexte confirmé, evidence synthétique admissible et honnêtement étiquetée, une candidate réellement issue du modèle, identité/lineage/références déclarées conservées, exact-version read sans provider, erreurs/arrêts/no retry prouvés, guards et validations exécutés avec succès, preuves séparées et commit cohérent autorisé. La prochaine priorité reste R3, sans bibliothèque intercalée.

État présent : R2_PACKAGE_PREPARED ; IMPLEMENTATION_NOT_STARTED ; TECHNICAL_TESTS=NOT_RUN ; PROVIDER_CALLS=0 ; NETWORK_CALLS=0 ; CREDENTIAL_RESOLUTION=0 ; USER_DATA_ACCESS=0 ; USER_DATA_METADATA_ACCESS=0 ; CODE_GUARD_LOCK_CONFIG_CHANGES=0 ; STAGING_COMMIT_PUSH_MERGE=0 ; H3_STARTED=FALSE. Aucune approbation propriétaire préremplie.
