# R3 — Contrat de réalisation proposé

Statut : PROPOSED — aucune approbation propriétaire ni implémentation.
Baseline : `817ad474d93c78c602a22bd30cf77fe7621e68b1`.
Scope : `H2_CONVERSATIONAL_REVIEW_MODIFY_V1`.
Transport : `REVIEW-MODIFY-HTTP-LOCAL-1.0`.
Corpus de calcul : pilote synthétique BTS CG, bilan fonctionnel/BFR, 60 minutes, /20.

## 1. Point de départ vérifié et limites

Le rapport R2 et le reçu CONSUMED ont été relus et leurs SHA vérifiés :
`c207cc9bff53a9b090f6321b89bdc48e6b42b1edd8e35f7a710c2ca70d200150` et
`4a64c0c07b07d3180e41fd64e90e7ab821c2e1e02af4b02792121e6125487f17`.
Ils attestent R2_LIVE_GENERATION=PASS, R2_PRODUCT_PROOF=OBTAINED et l'empreinte
`6003b6f55258c47d77efab2c864138b91afc715dec82ad94f8b637c691bfc7dc`.
Cette dernière est une identité historique rapportée, non un contenu relu aujourd'hui.
La candidate était volatile et a disparu à l'arrêt. Le grant R2 est consommé.
Aucune reconstruction depuis un hash, nouvelle génération ou réutilisation du grant.

La lecture ciblée établit 12 composants réutilisables et 8 composants nouveaux,
énumérés dans 02. EXISTS signifie présent dans les sources, pas testé aujourd'hui.
CAP-A01 existe au registre mais son implémentation métier du pilote manque :
le module validation_control ne fournit pas encore ces contrôles.
R2 fournit cinq sections textuelles et une projection CAP-R02 fermée ; ni les
questions/corrections ni les critères de barème ne sont actuellement typés.
Les anciennes sources et leurs manifests ne sont pas réécrits.

## 2. Ownership et raccordement

| Responsabilité | Propriétaire et raccordement proposé |
|---|---|
| Sujet, questions, correction, barème et delta pédagogique | M04 pedagogical_design : DTO/politique/commande Application nouveaux |
| Vérification déterministe CAP-A01 | M09 validation_control : contrat et fonction pure, sans agent/provider |
| Session, commandes, idempotence, versions, rapports | M08 work_orchestration via ports ; seul Application décide la publication |
| Critique sémantique | AG04 existant, CAP-V01 ; pont outbound traduit son ReviewResult vers un DTO neutre M08 |
| Proposition de transformation | AG03 existant, CAP-G02 ; pont outbound M04, sans accès au store métier |
| Lecture sujet exact | CAP-R02 existant, inchangé ; jamais latest |
| HTTP et UI | Adaptateurs inbound → frontière Application ; aucun import métier/SDK dans API |
| Processus et stockage volatile | Infrastructure/adaptateurs injectés ; aucune persistance durable |

Les modules n'importent pas agent_runtime. Les ponts traduisent les contrats de chaque
côté ; ils ne redéfinissent pas ReviewPort, GenerationPort, Finding ou ReviewResult.
Aucun nouvel agent, capability ou workflow global. Aucune route provider changée.
AG03/AG04 ne lisent ni SQL, ni fichier métier, ni repository, ni credential.
Ils reçoivent une projection déjà résolue et bornée depuis Application.
Les données ou instructions contenues dans un sujet restent UNTRUSTED.
Aucune instruction pédagogique ne confère une autorité de validation/promotion.

## 3. Modèle de version et contrat du bundle

### 3.1 Identités

- production_ref stable ; version_ref exact, nouvel identifiant opaque attribué par Application.
- V1/V2 sont des libellés UI, jamais des alias de résolution.
- VersionKey = (production_ref, version_ref), avec appartenance à la session obligatoire.
- Chaque objet embarque contract_id, VersionKey et subject_sha256.
- bundle_sha256 lie sujet, structure, correction, barème, contexte, références,
  données de calcul et lineage. SHA-256 du JSON UTF-8, clés triées, séparateurs
  compacts, ensure_ascii=false, allow_nan=false ; pas de normalisation silencieuse
  du texte. Les hashes sont calculés par la frontière technique, non par le provider.
- Le parent de V2 est le couple exact V1 + son bundle_sha256.
  Le champ fermé R2 lineage.parent_production_ref reste inchangé/None.
  Le parent versionné R3 appartient au bundle R3 ; aucun détournement du DTO R2.

### 3.2 R3-ASSESSMENT-BUNDLE-1.0

Champs obligatoires, aucun champ inconnu :
contract_id, production_ref, version_ref, subject_sha256, subject,
pedagogical_context, context_sha256, questions, correction, marking,
case_data, references, lineage, limitations.

| Champ | Structure fermée |
|---|---|
| subject | content et les cinq sections R2, mêmes ids/ordre : CONSIGNES, CONTEXTE_ET_ANNEXES, DOSSIER_1, DOSSIER_2, DOSSIER_3 |
| questions[] | question_id, dossier_id, locator(section_id,start,end,exact_text), instruction, expected_skill, calculation_refs |
| correction | production_ref, version_ref, answers[] ; chaque réponse : question_id, expected_answer, rationale, calculations[] |
| marking | production_ref, version_ref, total_points, dossiers[] ; chaque dossier : dossier_id, duration_minutes, questions[] ; chaque question : question_id, points, criteria[] ; critère : criterion_id, description, points |
| case_data | currency=EUR, base_case et scenarios[] ; composants stables/circulants/trésorerie identifiés, totaux et calculs attendus |
| references[] | Reprise des références R2 exactes présentes en session ; aucune résolution à partir d'un chemin/URL |
| lineage | operation_ref, command_id, source_capability, parent_version_ref/null, parent_bundle_sha256/null, instruction_sha256, changed_locators[], dependency_changes[] |
| limitations[] | codes et explications bornés, sans statut officiel inventé |

Tous les montants et points sont des chaînes décimales canoniques à deux décimales,
converties en Decimal, jamais des float. Montant absolu maximal : 999999999.99 EUR.
Points d'un critère >0 et <=20.00. Aucun NaN, Infinity, bool numérique ou expression
exécutable. Les calculs sont un petit AST de données : valeur référencée, ADD ou SUB ;
pas d'eval, de code, de formule Excel ni d'appel dynamique. Profondeur <=4,
<=16 opérandes par expression, <=60 calculs. Arrondi au centime explicite ; les seules
opérations du pilote ADD/SUB ne doivent pas produire d'écart d'arrondi.

Bornes proposées : trois dossiers, <=30 questions, <=8 critères par question,
<=10 scénarios de calcul, <=32 findings/review, <=8 rapports par version, trois
versions par session (borne R2 conservée). Un bundle <=128 KiB UTF-8, sujet <=64 KiB ;
enveloppe HTTP <=256 KiB. Rapport <=32 KiB. Si l'ensemble des résumés excède la borne,
réponse explicite de capacité, pas de troncature silencieuse des findings.
Les textes libres restent non fiables même lorsqu'ils respectent le schéma.

### 3.3 Compatibilité avec une candidate R2 en session

R3 ne suppose pas qu'une candidate R2 possède déjà un bundle complet.
Sans bundle, la lecture CAP-R02 fonctionne ; CAP-A01 renvoie FAIL/ASSESSMENT_BUNDLE_MISSING.
La review de l'ensemble et la modification sont refusées tant que les suppléments
manquent, afin de ne pas appeler un provider sur un dossier incomplet par défaut.

La commande explicite PREPARE_SUPPLEMENTS produit questions structurées,
correction et barème à partir du sujet exact disponible, sans changer ses octets.
Elle matérialise UNE FOIS un artefact auxiliaire immutable, lié au même VersionKey.
Elle ne remplace pas le sujet, ne change pas la version courante et ne consomme
pas un emplacement de version supplémentaire. Une seconde préparation ne remplace
jamais la première : même command_id/payload => réponse mémorisée ; autre commande
=> ASSESSMENT_ALREADY_PRESENT. Corriger des suppléments déjà publiés exige une
nouvelle version, pas un écrasement ; le pilote ne propose pas une commande générique
supplémentaire pour cela.

Les rapports d'absence de bundle restent liés à subject_sha256 et à
bundle_sha256=null. Ils ne deviennent jamais des validations du bundle apparu ensuite.
Les nouveaux rapports portent son empreinte exacte ; l'UI ne confond pas les deux.

Un provider ne peut inventer une question absente : les locators/extraits doivent
correspondre au sujet conservé. Le parseur valide la couverture structurelle ;
une équivalence sémantique des textes ne peut être prouvée uniquement par des locators.
La revue humaine reste nécessaire lorsque cette limite est signalée.
Si le sujet existant ne permet pas un barème cohérent /20, la préparation échoue ;
elle ne répare pas discrètement le sujet.

## 4. Review AG04 — critique indépendante

Commande : conversation_id, command_id, expected_revision, production_ref,
version_ref, bundle_sha256 et dimensions. Dimensions autorisées : les neuf enums
existants REV-ACC, REV-COV, REV-PED, REV-INS, REV-STR, REV-SRC, REV-CON, REV-FMT, REV-RSK.
Le serveur résout le VersionKey en session et vérifie les empreintes AVANT réservation.
Le client n'envoie pas de copie du sujet ou d'evidence payload arbitraire.

Projection au port : ReviewPortRequest existant, operation=SEMANTIC_REVIEW,
capability=CAP-V01, source_step_id, target_production_ref exact, target_content /
target_payload bornés, criteria/coverage_context, evidence_refs résolues,
output_contract et budget seulement après autorisation live distincte.
ReviewCoordinator.prepare/execute puis ReviewerAgent.build_review_result restent
les étapes canoniques. Aucun appel direct au transport contournant AG04.

Rapport produit neutre M08 : review_ref, operation_ref, VersionKey, subject_sha256,
bundle_sha256, status, findings, overall_assessment, coverage, limitations,
evidence_refs_used, created_at et usage technique non sensible.
Mapping sans perte des statuts completed/incomplete/failed ;
sévérités info/minor/major/blocking ; catégories = ReviewDimension.
Un finding contient id, catégorie, sévérité, description, locator exact,
rationale courte, correction_required, evidence_refs et suggestion bornée.
Une référence ou un locator inconnu invalide la sortie, au lieu de viser latest.
Aucune chaîne de pensée privée ni réponse brute provider dans le rapport.

overall_assessment=acceptable ne signifie ni CAP-A01 PASS, ni VALIDATED, ni promotion.
REVIEWED veut seulement dire rapport completed disponible pour cette empreinte.
Un rapport completed peut contenir des défauts blocking.
La review ne modifie ni sujet, ni bundle, ni version courante.
V2 ne récupère pas automatiquement les statuts ou findings de V1.

## 5. CAP-A01 — validation déterministe locale

Input : VersionKey, subject_sha256, bundle_sha256 ou null, snapshot M04 immutable,
références autorisées de session et, pour une révision, snapshot parent exact.
Application appelle M09 directement par son port inbound, sans agent ni provider.

Output : validation_ref, contract_id=R3-DETERMINISTIC-VALIDATION-1.0, VersionKey,
subject_sha256, bundle_sha256, checks[], overall_status, evaluated_at.
Chaque check : check_id, status PASS/FAIL/WARNING, reason_code, locators[],
expected/observed minimisés. Aucun texte d'exception ou chemin privé.
La liste fermée A01–A16 est normée dans 02 et comprend :
liaisons exactes, structure, questions, corrections, barème, total /20, domaine
numérique, composants, FRNG, BFR, TN, contexte, provenance, delta, réponses et couverture.

Priorité : au moins un FAIL => FAIL ; sinon au moins un WARNING => WARNING ; sinon PASS.
Un prérequis manquant ne fait jamais PASS : FAIL/PRECONDITION_MISSING avec ses
checks dépendants explicitement NON_EVALUABLE comme reason_code et status FAIL.
WARNING concerne uniquement une limite non déterminable par les règles du pilote,
pas un contournement d'une erreur de calcul ou de référence.

FRNG = ressources_stables - emplois_stables.
BFR = actif_circulant_hors_tresorerie - passif_circulant_hors_tresorerie.
TN = FRNG - BFR = tresorerie_active - tresorerie_passive.
Les totaux doivent aussi correspondre à leurs composants et au bilan du cas.
Chaque scénario D3 a ses propres entrées/identifiant, sans mélanger un montant de
base et un résultat de scénario. Les nombres structurés et les réponses chiffrées
sont reliés à des locators exacts du corrigé ; texte libre non formalisé => WARNING.
La qualification pédagogique réelle « plus difficile » ne devient pas un théorème
de CAP-A01 : structure de complexification vérifiée, confirmation pédagogique par review/humain.

CAP-A01 PASS ne vaut pas validation officielle ni adoption d'un seuil de release.
Statut de production = CANDIDATE dans tout R3. Badge NON VALIDÉE maintenu,
y compris si review completed et validation PASS. Promotion CAP-A02 absente.

## 6. Modification ciblée et atomicité

Commande fermée :
conversation_id, command_id(UUID), expected_revision(entier),
production_ref, base_version_ref, base_bundle_sha256,
operation=HARDEN_DOSSIER_3, instruction="Rends le dossier 3 plus difficile.".
Aucun changement de cible à partir d'une heuristique ou d'un latest.
Les variantes linguistiques non reconnues demandent clarification sans appel.
Le champ cible D3 est explicite dans l'opération ; pas de commande générique libre.

Préconditions : contexte confirmé, V1 en session et version courante, bundle complet,
CAP-A01 du même bundle sans FAIL, pas de travail R2/R3 actif, capacité disponible,
idempotence/CAS, puis job autorisé. Une review est disponible au pilote, mais
« acceptable » n'est pas une permission. Un travail live exige encore son grant.

Politique du pilote : D1/D2, consignes, contexte de base, niveau, durée, total /20 et
références sont inchangés. Seuls D3, ses questions, ses corrections, son allocation
interne de critères et ses scénarios de calcul peuvent changer.
Les points et durées totaux par dossier sont conservés.
Une dépendance nécessitant de changer D1/D2 est décrite précisément dans le résultat
DEPENDENCY_CHANGE_REQUIRES_APPROVAL et refuse la publication. Le pilote ne l'applique
pas, même avec une justification provider : décision propriétaire distincte requise.

Le provider propose seulement un delta D3 typé, pas un nouveau sujet complet faisant
autorité. M04 le fusionne avec les blocs V1 conservés par Application, construit
correction/barème complets, puis CAP-A01 contrôle le candidat assemblé.
Une réponse partielle, mal formée, hors périmètre ou avec FAIL ne publie rien.
Un WARNING est visible dans le résultat ; ne devient jamais une validation pédagogique.

La publication réussie est une SEULE transaction mémoire :
nouvelle ProductionReadView compatible R2 + bundle R3 + parent/trace + rapport
déterministe + pointeur current_candidate + résultat de commande + revision+1.
V1 reste dans _versions avec les mêmes octets/hashes. Les ids prod/ver ne viennent
pas du provider. Aucun half-commit sujet seul puis corrigé après coup.

R3Store partage le RLock et la session de ConversationMemoryStore, pas un store
concurrent indépendant. La réservation possède operation_ref, command digest,
base revision/version et lease. Les publications R2 concurrentes sont refusées
avec le code R2 existant GENERATION_IN_PROGRESS avant dispatch ; aucune nouvelle
autorité n'est ajoutée au service R2.
La complétion vérifie à nouveau lease + version courante + révision de réservation.
CAS échoué => aucun effet de publication, aucune répétition provider.
Un autre idempotency key avec le même texte n'autorise pas un deuxième live.

État opération : RESERVED → RUNNING → SUCCEEDED | FAILED_NO_EFFECT |
FAILED_OUTPUT | UNKNOWN. Aucune transition UNKNOWN→retry.
Même command_id + payload canonique identique => même opération/résultat, pas de
nouvel effet ; même id + payload différent => IDEMPOTENCY_CONFLICT.
Les GET lisent uniquement ; harvest séparé du GET, supervisé par composition.
Un crash après envoi, avant résultat certain, devient UNKNOWN, pas FAILED_NO_EFFECT.

Trace volatile minimisée : refs, instruction_sha256, changed_locators, parent hash,
correlation_id, statut, codes, usage. L'instruction pédagogique est dans la commande
de session, jamais dans les logs opérationnels. Pas de prompt/réponse brute ni de
copie du sujet dans les preuves Git.

## 7. Mapping génération et jobs — choix explicite sans retoucher R2

PREPARE_SUPPLEMENTS et HARDEN_DOSSIER_3 utilisent AG03 CAP-G02 / TRANSFORM,
target_ref versionné et resolved_inputs en mémoire. Ce n'est pas CAP-G03 :
le cas pilote est une transformation demandée par l'utilisateur, pas une
CorrectionRequest canonique issue d'un mécanisme de correction automatique.

Les quatre fichiers OpenAI/transport R2 suivis et les deux hashes du mapping/adapter
restent intacts. Réutiliser le format générique GenerationPort :
expected_sections = ("R3_RESULT_JSON",). Cette section textuelle contient un objet
JSON R3 fermé, sans Markdown, analysé strictement par le NOUVEAU pont R3.
PREPARE retourne questions/correction/marking/case_data/limitations pour le sujet figé ;
MODIFY retourne seulement dossier_3/questions_d3/answers_d3/marking_d3/scenarios_d3/
limitations. Les refs parent et l'operation sont recoupés hors contenu provider.

Cette solution réutilise le schéma externe générique de sections déjà présent ;
elle ne prétend pas que le provider impose nativement le schéma interne R3.
Validation locale stricte obligatoire : clés exactes, doublons interdits, limites,
références et politique M04/CAP-A01. Invalid JSON => FAILED_OUTPUT, zéro auto-réparation.
Les doubles doivent emprunter le même encodage/décodage que ce pont.
Si l'implémentation démontre une incompatibilité du port, rapporter le delta précis ;
aucun patch silencieux de l'adaptateur OpenAI gelé.

Trois types d'étapes éventuellement provider : préparation des suppléments,
review, modification. CAP-A01, lectures, rendu UI et comparaison de hashes sont locaux.
Un provider review et une transformation sont deux grants séparés, jamais un fanout
implicite. Le processus doit vérifier une autorisation avant réserve et avant dispatch.
Dans P_R3_IMPL, seule une injection explicite de ports fake peut exécuter ces étapes ;
configuration de production par défaut = NOT_AUTHORIZED.

Worker stdlib supervisé, une opération active maximum par session, durée maximale
90 s, frame JSON <=256 KiB, fermeture bornée, pas de restart automatique.
Ne pas réutiliser le bootstrap/count runner/grant R2 comme runner R3.
Aucun import de tests/support dans le produit ; les tests injectent les doubles.
Absence de credentials, de port ou de grant => refus avant toute tentative réseau.
Le futur choix de modèle/tokens/coût reste à vérifier et approuver, non fixé ici.

## 8. HTTP fermé

Sept nouvelles RouteSpec et neuf conservées = 16 ; trois assets toujours.
La liste H1–H7 exacte se trouve dans 02. Les six routes métier R1/R2 et leurs
paramètres ne changent pas. CAP-R02 GET exact reste la lecture du sujet.
GET .../assessment ajoute le bundle et des résumés de rapports exacts sans élargir
les clés de ProductionReadView. Aucune route générique dispatch/action/capability.

Toutes les POST incluent conversation_id, command_id, expected_revision et la
VersionKey ou base VersionKey appropriée ; unknown fields refusés.
Review ajoute bundle_sha256/dimensions ; validation ajoute bundle_sha256 nullable ;
préparation ajoute subject_sha256 ; modification suit la section 6.
Le serveur ne reçoit pas de payload pédagogique arbitraire sur ces commandes.

Réutiliser Host/Origin loopback, Content-Type et Content-Length stricts, anti-transfer-
encoding/duplicate headers, nonce X-R2-Nonce et X-Local-Intent=conversation-v1.
Ces noms sont une compatibilité de transport, pas une réutilisation d'autorisation R2.
Aucun CORS permissif, méthode implicite HEAD/OPTIONS, encodage traversant, query
libre ou alias latest. review_ref/operation_ref = préfixe fermé + 32 hex minuscules ;
production_ref/version_ref suivent les regex R2 existantes.
La session est vérifiée pour chaque lecture ; nonce renouvelé au redémarrage.

Réponses : 202 réservation async ; 200 résultat/rapport exact ; 400 schéma/cible
absente ; 403 action/transfert non autorisé ; 404 session/production/version/rapport
inconnu ; 409 CAS/idempotence/job actif/bundle déjà présent/capacité ;
410 session expirée connue ; 422 prérequis pédagogiques/bundle invalide ;
503 provider/job indisponible ; 500 erreur interne sûre. CAP-A01 FAIL est un résultat
HTTP 200 explicite, distinct d'une requête invalide. Erreurs sans echo de texte,
payload, chemin, credential ou message provider.

## 9. UI et cycle de vie

Vue du sujet exact avec choix V1/V2 et onglets sujet/correction/barème ; préparation
du corrigé seulement si bundle absent ; boutons Review, Vérifier les calculs,
Rendre D3 plus difficile. Afficher production/version courantes, parent, review
exacte, VALIDATION_STATUS et CANDIDATE — NON VALIDÉE.
V1 consultée n'est pas automatiquement V2 courante ; modification d'une ancienne
version => conflit explicite, pas de rebase silencieux.
État REVIEWED séparé de VALIDATION_STATUS. V2 a sa propre review NOT_RUN jusqu'à
une commande distincte. Le résultat pédagogique réel nécessite lecture humaine.

POST ne se répète pas automatiquement. Poll GET avec intervalle 1 s et arrêt après
90 s/terminal ; panne réseau => état inconnu, consultation manuelle possible,
jamais renvoi automatique du POST. DOM textContent, pas de innerHTML/évaluation,
stockage local/sessionStorage, cookie durable, download/export ou réseau externe.

Session R2 de deux heures conservée ; trois versions maximum, aucune éviction
silencieuse de V1. Stop : tuer/fermer le travail borné puis libérer la mémoire.
Restart : nouvelle session vide, aucun sujet/rapport récupéré depuis disque.
Un ancien id absent dans le nouveau processus renvoie 404 (pas de fausse mémoire
permettant de promettre un 410 après restart). Pas de promesse de reprise live.
R4 seulement ultérieurement peut traiter la persistance/export.

## 10. Critère de livraison et arrêt

Ce paquet est complet DOCUMENTAIREMENT ; il ne prouve ni tests ni produit R3 PASS.
Une future livraison synthétique réussie doit rester R3_SYNTHETIC_WIRING_ONLY.
R3_PRODUCT_COMPLETE est interdit sans la preuve réelle distinctement autorisée
et une évaluation pédagogique honnête. Aucune activation live ou R4/H3 automatique.
