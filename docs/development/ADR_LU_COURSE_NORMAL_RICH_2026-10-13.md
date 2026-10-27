# Proposition ADR — raccord COURSE riche au parcours normal

Date propriétaire : 13 octobre 2026, Europe/Paris.
Statut : DÉCISION TECHNIQUE LOCALE RETENUE APRÈS REVUE PRÉALABLE. Aucun succès de test ou de génération attesté par cette note.
Périmètre : même LU-PRODUIT-01, PR #5 ; aucun nouveau lot A06.
Auteur : sous-agent de conception `/root/rich_course_contract_design`, passe technique en lecture seule des sources. Les écritures se limitent à ce dossier technique externe au source tree.

## 1. Identité et mandat

Source examinée : `produit-integre-final-r2`, branche attendue `codex/produit-integre-post-fusion`.
HEAD effectivement lu : `fafe6b11400d24b60beb9962e93323b55e762db3`. `git status --short` était vide pendant cette passe.
Mandat lu : `01_CONTINUATION_MEME_LOT_COURSE_RICHE_M02_M04.md`, Downloads, complété par le message propriétaire du 13 octobre.
AGENTS.md et ENVIRONMENT.md de cette copie lus. Aucune donnée privée de sortie n'est copiée dans Git. Aucune base, ledger, secret ou bibliothèque métier n'est ouvert directement par le sous-agent.

Les anciens CREATE, cours, descendants et inspections restent acquis pour leurs identités exactes. Le chapitre local est un témoin du besoin ; il n'est pas assimilé à une génération fournisseur et n'est pas recopié comme fixture publique.

## 2. État réel du trajet existant

| Étape | Composant | Constat |
|---|---|---|
| UI | `frontend/app.js::p0Context` | Sélection STMG/BTS institutionnelle produit actuellement P0-CONTEXT-2.0 ; aucun choix de format COURSE. |
| Préparation | `P0CreationService._prepare` | Résout le contexte et la référence via Application ; crée les identités et la lignée localement. |
| Plan | `p0_agentic.effort_plan` | COURSE institutionnel reçoit toujours COURSE-EXPLAINED-1.0. |
| Projection fournisseur | `p0_content.build_p0_content_request` | Six champs ; COURSE impose questions/corrections/marking vides et cinq sections expliquées. |
| Autorisation | `p0_product._snapshot`, `p0_normal._check` | P1 et G1 comparent source/package/profil, schéma, préparation, contexte, références et corps exact. |
| AG-03 | `p0_normal_agents` | Parseur, préparation et garde imposent le jeu constant CONTENT_FIELDS. Aucun assouplissement global du scanner n'est nécessaire. |
| Réception | `P0CreationService._receive_generated` | Reprend toutes les identités du dispatch, vérifie les contrôles et publie Application. |
| Contrat riche | `CourseChapter` / `P0Production` | Documents/questions/liens/réponses existent ; sections de compatibilité dérivées et validées. |
| Vues / éditions | `P0ProductionReadView`, UI, `apply_course_edits` | Voies élève/professeur et édition locale COURSE existantes. |
| Export | `ExportSavedCommand`, `CourseOOXMLWordWriter` | Voie chapitre explicite existante ; réponse professeur retirée des projections élève. |

Cause bornée : le contrat riche n'est jamais demandé ni lié dans la voie normale fournisseur. Plus de prose dans le schéma six champs ne répare pas cette incompatibilité.

Deux insuffisances à fermer dans le nouvel embranchement :
- `CourseChapter` contrôle la forme de `documents.provenance.source_ref`, pas son appartenance au jeu de références fourni.
- `CreateP0Candidate.validate_content` examine aujourd'hui sections/questions/corrections ; vigilance/remediation du professeur et certaines cellules de chapitre ne sont pas comprises dans ce scan d'affirmations institutionnelles.

## 3. Décision proposée : un embranchement explicitement versionné

Ajouter `P0-CONTEXT-COURSE-3.0` au DTO P0Context, exclusivement pour resource_type COURSE, avec les champs institutionnels existants et un seul champ supplémentaire `course_format` fermé : CHAPTER ou EXPLAINED.

- Les contextes historiques 1.0 / 2.0 et leur projection fournisseur restent inchangés ; ils restent EXPLAINED pour COURSE.
- Le nouveau contexte exprime le format choisi et participe au SHA du contexte, de la préparation et du wire.
- UI : choix visible pour COURSE ; « Chapitre riche » peut être le choix initial de la nouvelle demande STMG, jamais une conversion d'un travail sauvegardé.
- CHAPTER exige un contexte STMG effectivement résolu/admis. L'enseignement, sa version, sa composante et la question restent ceux de la sélection.
- CHAPTER requiert `local_progression.chapter` exactement conforme à `^[1-9][0-9]?$`, soit un texte décimal de 1 à 99. Le champ existant devient requis et numérique dans ce mode. Application valide également, sans titre libre interprété ni défaut automatique.
- EXPLAINED conserve le champ de progression libre et facultatif.
- Aucun contrôle de permission, délégation Windows, source ou budget n'est acquis par ce seul choix UI.

Pourquoi ce choix : l'état de génération doit identifier le contrat attendu avant dispatch ; une bascule uniquement dans l'adaptateur serait invisible dans le contexte et ne permettrait pas de refuser une sortie expliquée présentée comme riche.

## 4. Périmètre de niveaux

Le CourseChapter actuel attend un header STMG (frame/theme/question) et ne sait lier que Première/Terminale STMG.
Le raccordement minimal reste STMG. Ne pas prétendre que cette implémentation qualifie un chapitre riche BTS.

Pour BTS :
- la voie expliquée historique reste disponible dans son périmètre admis ;
- une demande CHAPTER doit recevoir un refus explicite de contrat non couvert, avant autorisation/dispatch ;
- aucun processus/activité BTS n'est renommé « question du programme » afin de franchir le garde.
Une extension BTS ultérieure exige un vrai header adapté et ses propres critères/qualification ; elle n'est pas une conséquence implicite de ce lot.

## 5. Sortie fournisseur riche fermée et statique

Conserver le schéma historique six champs. Ajouter un schéma COURSE riche distinct et statique, identifié par le contexte COURSE3/CHAPTER, le contrat d'entrée COURSE2, la politique riche et les empreintes exactes du schéma et du corps, validé par le validateur OpenAI strict existant. Le nom de format fournisseur reste `p0_pedagogical_content` pour les deux voies ; il ne constitue pas leur identité de contrat ni une autorisation.

Racine proposée, tous champs requis, additionalProperties=false :
- `title`
- `course_chapter`
- `limitations`

`course_chapter` contient seulement le contenu pédagogique :
- context {title, text}
- documents [{id, title, function, text, table, provenance}]
- parts [{id, title, document_ids, observation, analysis, concept_ids, reinvestment}]
- questions [{id, number, prompt, document_ids, capability_ids, response}]
- concepts [{id, notion, definition, explanation, example}]
- knowledge_check [question_id]
- transfer {title, document_ids, question_ids}
- synthesis
- teacher_answers [{id, expected_answer, rationale, vigilance, remediation}]

Objets fermés partout ; table null ou {columns, rows}. Réponse fermée {kind, lines, table}. Les bornes du contrat existant restent l'autorité de validation locale ; le schéma exprime les bornes compatibles du sous-ensemble strict.
Les identifiants D/Q/N/P/C sont des liens internes de contenu, pas des identités de production. Leur forme est bornée et tous leurs liens sont validés. Les tailles maximales ne sont pas des nombres exigés universellement.

Le fournisseur ne reçoit aucun droit de produire :
- contract_id Application, production_ref, version_ref, lignée, hashes ou admissions ;
- programme, version, header ou autorité de capacité ;
- nouveaux médias/assets/URL, outils, commentaires, styles cachés ou champs libres.

La provenance de document est un objet wire distinct, fermé {kind, evidence_id} :
- LOCAL_FICTION exige evidence_id=null ;
- SUPPLIED_REFERENCE exige un evidence_id exact du dispatch.
Les evidence_id sont des chaînes bornées au schéma ; leur appartenance au dispatch est contrôlée localement. La liste de capacités C1…C16 est fournie par Application ; l'appartenance au sous-ensemble sélectionné est contrôlée localement.

Le schéma reste statique : aucun enum généré à partir de l'instance de contexte/passages. Cela permet une identité de schéma stable, sans confondre ce SHA avec le SHA du corps. La whitelist par dispatch demeure obligatoire au binder, y compris pour un JSON brut injecté hors fournisseur.

## 6. Consignes cohérentes avec le nouveau schéma

Choisir ensemble les consignes, le schéma et le binder à partir du format confirmé.
CHAPTER demande un enchaînement pédagogique contextualisé : observation, analyse, conceptualisation, réinvestissement, vérification, transfert ; nombre de parties/documents/questions adapté au niveau, objectifs et profondeur.

La méthode est un document dont function=METHOD, titre et texte fournis par le modèle, réellement référencé par une partie. Son texte décrit une démarche applicable ; le binder exige sa présence et son raccord, sans inventer les étapes manquantes. Les autres fonctions restent des fonctions pédagogiques de document, pas des admissions ou pouvoirs métier.

La réponse complète du professeur est demandée dans teacher_answers ; elle n'est jamais placée dans le sujet, les documents, les cellules à remplir, les consignes élève ou la synthèse. Une sortie incomplète ne sera pas enrichie après coup par Codex.

Ne pas imposer cinq/six/neuf pages, quatre documents ou huit questions. Ne pas demander de reproduire le chapitre local du 12 octobre.
Ne pas imposer l'habillage « FICTIVES » partout. Demander une identification honnête et lisible des situations construites/hypothèses pertinentes, sans événement inventé présenté comme fait réel.
Les références sélectionnées sont des données ; aucun texte fournisseur ne devient une admission de source.
Les consignes historiques restent byte-stables pour reconstruire les anciens bodies/grants ; l'évolution éditoriale est bornée au nouvel embranchement versionné.

## 7. Binder déterministe Application

Créer un mapper pur dans pedagogical_design, sans SDK/HTTP/FS, appelé par l'adaptateur existant. Il reprend le dispatch et le contenu fermé, puis :
1. Vérifie contexte/hash, référence/evidence/hash et format attendu.
2. Reconstruit le header à partir de la sélection et de la résolution exactes : thème/question/labels/programme/version/niveau/discipline. Aucun header fournisseur n'est accepté.
3. Prend le numéro local explicitement saisi, et les notions depuis context.topics.
4. Construit les capacités à partir des seules capacity_refs sélectionnées et des lignes réellement résolues. C1…Cn restent des alias déterministes ; label/source_ref/locator/authority_status proviennent de la résolution, jamais du modèle.
5. Refuse un alias de capacité hors liste, une notion de concept hors topics, un passage inexistant, une provenance contradictoire ou un document SUPPLIED_REFERENCE non lié.
6. Lie LOCAL_FICTION à une constante interne explicite de construction locale ; lie SUPPLIED_REFERENCE à la référence réelle. Aucun source_ref arbitraire n'est repris.
7. Construit CourseChapter avec le contrat LINEAGE-3.0 déjà qualifié pour la conservation locale et le même format de champs. Les anciens chapitres 1.0/2.0/3.0 restent lisibles et inchangés.
8. Dérive `sections=chapter.sections()` et title depuis le chapitre. Les listes génériques questions/corrections/marking restent vides pour COURSE ; les activités du cours sont dans course_chapter.
9. Reprend production_ref/version_ref/context/references/lineage sans modification. Ajoute localement le statut candidate dans limitations comme aujourd'hui.
10. Passe par P0Production, CreateP0Candidate et la publication Application existants.

Contribution locale explicite : reprise du header/capacités/notions/identités, aliasage, projections et statut candidate. Aucun texte substantiel de document, question, notion, réponse ou méthode n'est fabriqué au binder pour combler une sortie fournisseur manquante.

## 8. Réception, gardes et contrôles

- Une préparation CHAPTER exige une sortie riche ; la sortie historique six champs est rejetée, même si elle contient une prose très longue.
- L'embranchement EXPLAINED exige sa sortie historique ; il ne peut absorber un chapitre riche par hasard.
- Parseur duplicate keys/nonfinite/tailles conservé. Sélectionner le jeu de champs attendu depuis le dispatch. L'appel sans dispatch conserve le parseur historique pour ses usages/tests existants.
- AG-03 et GenerationOutputGuard conservent leurs politiques de sécurité partagées. Seuls les champs du contrat attendu changent au point d'appel.
- response.status=incomplete, sortie tronquée, JSON invalide, liens/couverture/réponses manquants : refus ; aucune réparation de contenu, découpe multi-appels, retry ou fallback.
- Source_usage NOT_IN_OUTPUT_SCHEMA demeure la limite du contrôle historique. La provenance SUPPLIED_REFERENCE peut attester une déclaration documentaire bornée dans le nouveau schéma, pas un raisonnement interne du modèle ni une suffisance globale.
- Option minimale : conserver le contrat de contrôle existant et sa réserve, en documentant cette portée limitée. Si une déclaration globale evidence_refs_used est ajoutée ultérieurement, versionner ensemble le contrôle, son persistage et ses consommateurs ; ne pas réécrire la déclaration historique.
- Étendre les contrôles d'affirmations institutionnelles aux champs professeur attendus/justification/vigilance/remédiation et à tout texte visible du nouveau chapitre. Ce scan vérifie les revendications fermées effectivement couvertes par require_supported_claims ; il ne prouve pas la concordance sémantique de toute phrase avec un texte officiel déjà admis. Header/capacités/identités sont liés exactement par le mapper. La fidélité des autres affirmations libres reste une vérification observable séparée et une réserve de relecture pédagogique, sans faux refus universel annoncé.
- Refuser le recopiage exact de blocs de réponse professeur dans les champs élève ; vérifier aussi cellules de tableau et espaces de réponse. La règle doit borner explicitement le bloc contrôlé (texte normalisé substantiel ou champ complet), sans rejeter une courte réponse numérique déjà présente légitimement dans les données ni une définition enseignée qui revient dans une réponse. Les fixtures de fuite utilisent des sentinelles uniques substantielles. Distinguer identité exacte observable et garantie sémantique : une absence de duplication détectée ne prouve pas l'absence de toute réponse indirecte.
- Aucun champ caché/commentaire ou alternative de média n'existe dans le schéma riche minimal. Les XML de l'export doivent néanmoins être vérifiés contre les sentinelles professeur, pas uniquement document.xml.

Les nouvelles contraintes de provenance/anti-duplication s'appliquent au successeur demandé, sans invalider rétroactivement tous les anciens chapitres locaux lors de l'ouverture d'une bibliothèque.

## 9. Consommateurs et conservation

Réutiliser les vues élève/professeur existantes, l'éditeur de chapitre local, le stockage SavedProduction, la reprise locale et les exporteurs CourseOOXMLWordWriter/product-v7.
Leur branche est sélectionnée par présence de course_chapter ; aucune nouvelle API ou port n'est nécessaire.

À vérifier par impact :
- vue élève sans teacher_answers et sans provenance interne ;
- vue professeur avec la liste exacte et séparée ;
- réponse HTTP persistée et reprise locale gardent bundle/record/version ;
- deux exports déterministes propres à cette version ; source/histoire sans mutation ;
- aucune activation de promotion, aucune autorité restaurée à la réouverture ;
- barème pour COURSE n'est pas une évaluation : ne pas étendre le chapitre aux familles QCM/QUIZ/OPEN_QUESTIONS/ASSESSMENT.

Les anciennes inspections Word restent acquises seulement pour leurs octets. Les exports du nouvel embranchement reçoivent une inspection technique propre, sans réécrire leurs ancêtres.

## 10. P1, enveloppe et activation

Aucune modification de max_output_tokens=4096, modèle gpt-5.6-terra, reasoning low, tier default, endpoint /v1/responses, tokenizer/tarif, plafonds, max_calls, store/stream/background/outils ou single-flight.

Les SHA context/preparation/body/schema/source/package/profil changent ; les anciens G1/P1 ne couvrent pas ce nouvel effet.
P1 1.0 porte un unique output_schema_sha256 : ne pas accepter silencieusement plusieurs schémas, ni omettre sa comparaison.
Une décision de rattachement groupée peut limiter la qualification à COURSE riche et à son schéma statique exact ; les autres familles restent dans leurs portées historiques, sans hériter du nouveau package par défaut.

Avant live : candidate/package stabilisés, revue distincte, corps prévu exact, données réellement transmises et nouvelles admissions éventuelles, borne locale calculée, rattachement explicite et consentements V2.
Conserver SID/stores, namespace/LOCK/slots/reservations/reçus et enveloppe cumulative. Aucun solde actuel déduit d'un résumé daté ; aucune remise à zéro/quota nouveau/ancien grant rejoué.
Le binder et le preview local sont testables sans permission live. Aucun appel fournisseur n'est autorisé par cet ADR.

## 11. Fichiers d'implémentation probables

| Fichier | Intervention bornée |
|---|---|
| pedagogical_context/contracts/dto/p0_context.py | Variante context COURSE3, format, STMG/numéro explicite. |
| pedagogical_design/contracts/dto/course_policy.py | Politique choisie par contexte ; legacy expliqué identique. |
| pedagogical_design/application/mappers/course_provider_content.py (nouveau pur) | Binding rich déterministe, source/capacity whitelist. |
| adapters/outbound/generation/openai/p0_content.py | Sélection legacy/rich, consignes/schéma statique, projection input/binder. |
| adapters/outbound/generation/openai/p0_normal_agents.py | Champs/parse/garde choisis par dispatch ; legacy par défaut. |
| adapters/outbound/generation/openai/p0_normal.py | technical_result transmet dispatch au parseur choisi. |
| work_orchestration/application/services/p0_agentic.py | Plan affiche le contrat demandé, pas EXPLAINED universel. |
| work_orchestration/application/services/p0_creation.py | Réception refuse format divergent ; gardes contrôles conservés. |
| pedagogical_design/application/commands/create_p0_candidate.py | Claims sur professeur et autres champs du nouveau chapitre. |
| validation_control/application/commands/validate_p0.py | Format attendu concordant ; succès structurel non pédagogique. |
| frontend/index.html + frontend/app.js | Choix visible, numéro requis CHAPTER, refus BTS riche explicite. |

CourseChapter/P0Production/ReadView/exporteurs : réutiliser ; changer seulement si un invariant du successeur ne peut être garanti au binder/commande. Toute modification partagée exige régressions de ses consommateurs.
P1policy/ledger, transport, credentials et scanner partagé : aucune modification prévue.

## 12. Matrice minimale de preuves à exécuter après implémentation

| Impact | Preuves synthétiques exactes |
|---|---|
| Context / UI | CHAPTER choisi explicitement ; EXPLAINED ancien compatible ; champ numéro absent/libre/0/100/bool refusé ; 1/99 acceptés ; BTS CHAPTER refusé avant dispatch. |
| Wire pur | Même contenu/context/source donne même wire malgré prod/ver aléatoires ; riche statique même hash sur deux contextes admissibles ; aucun oracle/private teacher fixture dans input ; anciens bodies/6 familles byte-stables. |
| Schéma | additionalProperties=false récursif, strict-validator PASS réel, profondeur compatible, tous champs attendus ; pas de champs locaux d'autorité ni source inventable acceptée. |
| Parsing / garde | doublons/nonfinite/oversize/unknown field/mauvais format/incomplete/tronqué refusés ; garde partagé inchangé ; plus de questions/corrections génériques pour COURSE riche. |
| Binding | header/capacités/notions/IDs locaux exacts ; source inconnue, provenance contradictoire, notion hors contexte, cap hors sélection et links/couverture/réponses invalides refusés ; document METHOD présent et relié à une partie, absence/texte vide/orphelin refusés sans réparation. |
| Claims / fuite | revendications professeur réellement détectables/interdites par require_supported_claims refusées (admission non établie, citation officielle malgré IMPLICIT, année BTS présentée comme prescription) ; sentinelles professeur absentes de toutes les projections/sections/cellules élève et de tous les XML/relations de DOCX ; source_ref interne non visible. |
| Application vrai chemin | double transport déclaré synthétique → AG-03/garde/binder → CreateP0Candidate → ValidateP0 → publication → save/open/exports ; aucun ReframeCourse/ad hoc requis. |
| Conservation / reprise | version/sha exacts, ancêtres inchangés, authority NONE_RESTORED, statuts distincts ; deux démarrages hors fournisseur si le changement impacte la reprise normale. |
| Régressions familles | COURSE EXPLAINED, EXERCISE, QCM, QUIZ, OPEN_QUESTIONS, ASSESSMENT restent leurs contenants/validations ; aucun cours riche imposé aux autres familles. |
| Permissions | ancien schema/package grant refusé, aucune réservation/credential/transport déclenchée par preview non autorisé, budget/namespace inchangés ; pas de retry/fallback. |
| Consommateurs | suites CourseChapter/plain-lineage/media/édition/readcompat/word et P0context/create/content/normal/P1/HTTP selon diff. |
| Qualité générale | Ruff, mypy et diff/hygiène applicables exécutés ; pas de global inventé pour cette note. |

Les fixtures publiques sont entièrement synthétiques. Les preuves du chapitre privé restent externes, liées par identités si utiles.
Les tests de mutateurs n'accèdent qu'à leurs racines temporaires synthétiques, pas aux sources/runtime/bibliothèque propriétaires.

## 13. Limites et retour arrière

Cette passe ne constitue ni revue indépendante de l'implémentation future, ni exécution des tests, ni validation pédagogique, ni autorisation live.
Le périmètre M02–M04 est examiné parallèlement par le parent ; aucune admission ou réaffectation institutionnelle proposée ici n'est présumée acquise.

Retour arrière du code/package : conserver le package/checkpoint fafe6b1 et les lecteurs qualifiés, désactiver le nouveau choix pour nouvelles demandes si nécessaire ; aucun rollback/migration/effacement métier.
Un nouveau chapitre 3.0 sauvegardé ne doit pas être effacé pour rendre un ancien lecteur compatible ; conserver son lecteur qualifié associé et refuser l'ouverture par un lecteur non compatible.
Les historiques/reçus ne sont jamais réécrits.

La recette enseignante reste NOT_PERFORMED et dernière étape. Pas de merge, release ou déploiement par cet ADR.


## Rattachement de la revue préalable

Proposition exacte SHA-256 032a2c1276bd6844719c3edbc53408742b937ce7d98f3deefaf5e14a030bbf38, relue par /root/p1_preparation_review avant implémentation, avis FAVORABLE_LIMITED du 13 octobre. Les preuves techniques privées restent hors Git. Cette décision locale découle de la consigne propriétaire de poursuivre le raccordement hors fournisseur ; elle ne vaut aucun droit live. La continuité P1/LOCK/slots après consommation reste un point distinct à instruire sans réécriture.

Addendum de compatibilité du nom fournisseur SHA-256 `0096d087651a3bab3a15e2def7485b0aaffe82c9266c10b1d279234997e3f830`, avis distinct ciblé SHA-256 `894b37125ff635f63555592e7f527dc00d29ac171229646a4eeabc6afb0e9b6a`. Les comparaisons strictes de schéma/corps/grant restent inchangées ; parseur, garde et binder se sélectionnent depuis le même contexte confirmé. Ce détail ne qualifie pas le trajet complet.

Limite d'activation réelle : le ledger P1 existant lie ses octets LOCK et chaque slot à l'empreinte de permission originale ; les grants consommés gardent leurs anciennes identités source/package/schéma. Un rattachement de nouvelle candidate ou de nouveau schéma seul divergerait de ces contrôles et doit STOP. Aucune substitution de permission, réécriture LOCK/slot, restitution de budget ou remise à zéro n'est implémentée ici. Une continuité versionnée explicitement décidée et qualifiée est nécessaire avant de rendre le futur effet live exécutable.
