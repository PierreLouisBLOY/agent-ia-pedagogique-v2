# ADR LU-S5 — Média versionné des productions P0 et diffusion produit

Statut : PROPOSED_FOR_REVIEW. Lot LU-PRODUIT-01, base 89ef3ed.

## Constat et décision proposée

Les MediaAssetWorker, VisualBrief et CourseChapter existants rendent, valident et
conservent des PNG bornés pour COURSE. Les cinq autres familles et les cours
expliqués P0 ne disposent pas de liaison durable aux médias. Leur WordDocument
interdit un média sans CourseChapter. Les profils de diffusion historiques
doivent conserver leur comportement et leurs preuves.

Ajouter un successeur fermé `R6-P0-PRODUCTION-MEDIA-3.0`, conservant les champs
P0 existants et ajoutant `media_plan`. La read view successeure
`R6-P0-PRODUCTION-VIEW-MEDIA-3.0` ne reçoit que les assets élève accessibles,
jamais le plan privé ou les variantes professeur. Les contrats 1.0 et COURSE-2.0 restent
lisibles sans réécriture. Le plan `PRODUCTION-MEDIA-1.0` lie la version exacte et
au plus huit entrées ; chaque entrée lie un VisualBrief 1.0, son MediaAsset 1.0
éventuel, l'exigence de présence, une raison d'omission explicite et les hashes
de dépendances de contenu. Il ne réintroduit pas une source ou un moteur.

Les dépendances sont des sections, questions ou réponses de correction exactes
de la production. Le contexte, l'identité de production et les références
institutionnelles sont vérifiés lors de la liaison. Le média dépendant d'une
correction est réservé au professeur. Les labels et textes alternatifs d'un
média élève ne peuvent reprendre une réponse professeur. Les données chiffrées
restent du texte/tableau natif ; aucun nouveau graphique quantitatif ni réalisme
photographique n'est revendiqué par les renderers locaux présents.

Le service Application prépare un enfant et emploie MediaAssetWorker pour les
octets locaux ou fournis/admis. Il ne charge aucun chemin, URL, credential, SQL
ou fichier métier et ne possède pas d'autorité d'admission/promotion. La
sauvegarde emploie le store canonique existant. Une modification d'une dépendance
sans actualisation du plan est refusée comme média périmé. Un média requis
absent interdit l'export pour son public ; un média facultatif absent garde sa
raison dans le dossier et est omis de la projection pédagogique.

Une projection média de WordDocument, additive et nommée `production_media`,
lie chaque asset à une rubrique visible unique. Un profil successeur explicite
`product-v7` emploie les styles/tableaux A4 actuels, conserve la projection du
bon public, insère le PNG natif et retire les notes techniques de diffusion.
Les profils historiques et les archives restent inchangés. Les identités et
statuts demeurent dans Application et les reçus ; aucun diagnostic technique
n'est ajouté au texte élève/professeur.

Le chapitre riche COURSE garde son contrat, ses projections, son exporter et
ses assets. Le service commun couvre les P0 sans chapitre riche ; un tel service
ne convertit pas un cours expliqué en chapitre inductif qualifié. Le choix des
deux voies et leur compatibilité restent explicites.

## Portée, sécurité et retour arrière

Objets : DTO P0/plan média/WordDocument, service et inbound Application local,
exporteur/profil successeur, tests dédiés. Aucun SDK, dépendance runtime,
fournisseur, scanner global, mutateur SQL, seed ou source privée ajouté.
Plafond déclaré du successeur : huit entrées, 64 Kio par PNG, 256 Kio pour
la production encodée entière, enveloppe sauvegardée inchangée à 512 Kio.
Une collection de huit images n'est donc pas forcément admissible si le budget
total est dépassé. Ce plafond est une limite technique explicite, pas quota ni
revendication d'adoption propriétaire de toutes les conventions V1.1.
L'admission d'un asset importé reste celle de son reçu existant ; sa seule
présence ne l'admet pas. GENERATED_ADMITTED ne déclenche aucun fournisseur.

Retour arrière : ne pas activer `product-v7` et ne pas appeler l'inbound de
préparation. Les anciens bundles/profils restent valides. Conserver les enfants
déjà créés et leurs preuves ; pas de mutation rétroactive de bibliothèque.

## Vérifications prévues

Six familles par contextes/identifiants synthétiques déclarés, présence native
PNG/OOXML, exactitude des octets et légendes, visibilité élève/professeur,
raison d'omission facultative, refus du média requis absent, refus de hash de
dépendance changé/du mauvais public/de la mauvaise version/source/capacité,
préservation du parent et passage sauvegarde/réouverture via Application.
Contrôles de régression des contrats COURSE et des profils historiques. Tests
de mutation des données et des champs de projection ; Ruff et mypy sur le delta.
Les contrôles internes OOXML ne valent ni inspection Word ni recette enseignante.
