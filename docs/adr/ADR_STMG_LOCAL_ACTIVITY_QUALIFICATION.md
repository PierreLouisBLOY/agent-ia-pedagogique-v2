# ADR — qualification locale STMG distincte de l'admission fournisseur

Statut : successeur local après revue préalable distincte ; composition désactivée par défaut.

## Constat

Le contexte P0 exige le niveau et la discipline du cadre institutionnel sélectionné.
La résolution native et l'admission locale transmissible exigent leurs propres preuves.
Un choix pédagogique local de préparation ou de réactivation n'accorde aucune de ces autorités.
Une fondation SGN de Première peut servir à une réactivation en Terminale, sans devenir
une question ni une capacité institutionnelle de Terminale.

## Décision

Ajouter les contrats STMG-LOCAL-ACTIVITY-CHOICE-1.0 et STMG-LOCAL-ACTIVITY-OWNER-SCOPE-1.0,
une query de readiness pure, un wrapper Application inbound et une factory normale explicite.
La factory vérifie les octets et l'empreinte du reçu technique injecté, puis son item et sa
proposition liés au scope. Il s'agit d'une transcription technique, pas d'une signature humaine.
La liste triée exacte des empreintes des choix est liée à un scope dont l'empreinte attendue
est injectée par la composition de confiance. Le SHA d'un reçu seul ne suffit pas à élargir
la liste des choix. Aucune preuve, configuration ou allowlist ne vient de la requête utilisateur.

La composition utilise uniquement des projections Application injectées ; aucun SQL, repository,
filesystem métier, secret ou fournisseur n'est ouvert par ces nouvelles surfaces.
L'activation exige un booléen réel ; le défaut OFF ne lance aucun callback et n'expose aucun choix.
La requête inbound reçoit uniquement l'empreinte du choix et un sous-ensemble de capacités locales.

Le résultat garde le positionnement d'enseignement et le niveau de l'appui séparés.
La seule réactivation entre niveaux acceptée est une fondation de Première vers un
positionnement Terminale. Les identités, versions, documents, textes et empreintes restent liés.
L'autorité disciplinaire UNKNOWN est conservée ; les contenus privés, oracles et références
enseignantes sont exclus. Un support incomplet demeure LOCAL_CONTEXT_CONTENT_INSUFFICIENT.
Un support limité à la préparation peut être LOCAL_CONTEXT_SUPPORTED_FOR_PREPARATION,
sans qualification de génération, d'exactitude de la sortie ou de recette enseignante.

Les phrases de capacités contenues dans une question admise peuvent être projetées comme
LOCAL_EXTRACTED_FROM_ADMITTED_QUESTION. Leur identifiant local dépend du texte exact,
de la question, du document et de la version ; leur identifiant natif reste null. Les pages sont
les locators techniques de la projection source, sans revendication d'une pagination imprimée.
metadata expose ces capacités et prepare refuse toute sélection native, empruntée ou dupliquée.
Cette projection ne crée aucun objet institutionnel et ne modifie aucune résolution native.

## Limites et contrôles

Toujours provider_dispatch_allowed=false, transmission_admission=NOT_ADOPTED,
native_relationship_status=NOT_ADMITTED_FOR_POSITIONING et teacher_acceptance=NOT_PERFORMED.
Aucun CREATE, sauvegarde, réouverture, export, grant, slot, réservation ou budget n'est créé.
P0Context, P1, les résolveurs, RESOLVED_ADMITTED et les admissions transmissibles restent inchangés.
Les aliases de recette, captures et décisions exactes restent dans le dossier privé de qualification.
Le source et les tests ne contiennent aucun reçu, source runtime, production ou chemin privé.

Tests synthétiques ciblés : default OFF, booléen strict, scope exact, preuve/proposition falsifiée,
contexte local et niveaux séparés, insuffisance, mutations et exclusions de source, projection
de capacités et sélection réelle par la factory/inbound, absence d'autorité de dispatch.
Ruff et mypy sont exécutés pour le delta ; les résultats réellement exécutés sont conservés
dans le dossier de qualification externe. Aucun résultat de prototype ne vaut qualification source.

## Delta et retour arrière

DTO pedagogical_context ; query work_orchestration ; wrapper inbound Application ; factory de
composition ; tests unitaires synthétiques ; cet ADR. Aucun adaptateur SQL ou fournisseur propre.
La factory est raccordable par le produit normal, indépendamment du compilateur de preuve.
Une interface locale future peut consommer metadata/prepare, sans bouton d'envoi fournisseur.
Une activation fournisseur future dépend d'une admission et d'un binding distincts.
Retirer l'injection ou laisser OFF ferme ce parcours ; aucun rollback SQL ou migration de record.
