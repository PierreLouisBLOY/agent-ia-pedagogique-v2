# LU-PRODUIT-01 — proposition locale d'intention P0

État : PROPOSED_FOR_DISTINCT_REVIEW, 11 octobre 2026.
Base : `89ef3edc5f9d09e5f769862833ffa2c1b175c8fb`.

## Décision proposée

Ajouter une query Application pure `ProposeP0Intention`, consommée par le companion
fermé `POST /api/v2/p0/intention`. Réutiliser le serveur P0 et ses contrôles locaux
Origin/Host/nonce/taille/JSON. Conserver sans modification `P0_ROUTE_SPECS`, le
registre historique R2/R3/R4, les DTO P0Context existants et le pilote R2.
La nouvelle route a son registre distinct `P0_INTENTION_ROUTE_SPECS` et son contrat
de résultat `P0-INTENTION-PROPOSAL-1.0`. Aucun nouveau framework ni service externe.

## Contrat exact

Corps JSON fermé : `command_id` (32 caractères hex minuscules), `intention`
(texte 1–4000 caractères, <=12 KiB UTF-8, contrôles Unicode existants).
La query est stateless : mêmes octets normalisés, même proposition ; aucun effet
à rejouer, aucun stockage parallèle et aucun droit de génération induit.

Résultat fermé : `contract_id`, `state`, `command_id`, `intention_sha256`,
`proposal`, `extracted_fields`, `missing_fields`, `ambiguities`,
`institutional_selection`, `unsupported_operation`, `implementation`,
`confirmation_required`, `provider_attempts`, `authority`.

`proposal` contient exactement : `family`, `resource_type`, `question_mode`,
`level`, `topics`, `objectives`, `difficulty`, `duration_minutes`, `total_points`,
`language`, `audience`, `teaching_hint`.

- Les six familles sont COURSE, EXERCISE, OPEN_QUESTIONS, QCM, QUIZ, ASSESSMENT.
- Les quatre niveaux sont ceux du P0 existant ; BTS sans année reste manquant.
- Extraction générique française et bornée : noms de famille, niveau explicite,
  phrase « sur/concernant/à propos de », verbes de capacité, durée, points,
  difficulté et public explicites. Aucun nom de notion ni ID M01–M07 codé en dur.
- Les valeurs absentes sont nulles ou listes vides. Langue `fr` est une convention
  de l'interface, à confirmer, pas une propriété officielle extraite.
- Plusieurs familles/niveaux/durées/barèmes/difficultés/publics incompatibles
  produisent une ambiguïté `{field, candidates}` et aucune sélection silencieuse.
- Le niveau et un `teaching_hint` ne valent ni sélection ni admission d'un cadre.
  `institutional_selection=EXACT_CATALOG_CONFIRMATION_REQUIRED` toujours.
- `state` : CONTEXT_PROPOSED ou CLARIFICATION_REQUIRED selon les champs
  indispensables (famille, niveau, sujets, objectifs, difficulté et, pour une
  évaluation, durée et points) ; OUT_OF_SCOPE pour une demande explicite de
  modification/review/export qui appartient à la version active et non à cette
  query de préparation.

Les durées/barèmes demandés hors ASSESSMENT sont conservés comme propositions de
contraintes. Le DTO courant ne permet pas de les injecter dans ce contexte P0 :
une telle limite reste visible dans `missing_fields` (application de contrainte),
sans effacement de la demande ni promesse d'exécution. Une extension de contexte
requise relève d'une décision séparée coordonnée, pas d'un assouplissement ici.

## Responsabilités et autorité

L'inbound ne fait que parser/transporter ; la proposition appartient à Application.
Le frontend affiche et fait confirmer la proposition, corrige les champs ambigus,
puis sélectionne l'enseignement/capacités/notions exacts depuis le catalogue
Application. Il n'invente ni source officielle ni relation institutionnelle.

Aucun fournisseur/COUNT/credential/retrieval de base n'est invoqué par cette query.
Elle ne modifie pas la production active et n'ouvre aucune gate. Les refus provider
existants restent applicables aux commandes CREATE/REVIEW ultérieures. Le résultat
nomme `DETERMINISTIC_APPLICATION_PROPOSAL`, `confirmation_required=true`,
`provider_attempts=0`, `authority=NONE`. Cette capacité ne mesure pas l'intelligence
LLM ni ne remplace l'enseignant.

## Vérifications requises et retour arrière

Cas positifs sur six familles/quatre niveaux, sujet hors matrice et variantes
d'identifiants/contenus. Mutations : famille/niveau/BTS-année ambiguës, défauts
de données, demandes d'export/modification, payload JSON inconnu/dupliqué,
nonce/Origin refusés, route encodée/query/trailing slash/méthode non admises,
longueur/Unicode/command_id invalides, durée et points contradictoires.

Maintenir les oracles littéraux des registres historiques et tester le companion
distinct. Retirer ce companion et la query restaure la voie structurée existante
sans toucher un record, une base, un grant ou une référence institutionnelle.
