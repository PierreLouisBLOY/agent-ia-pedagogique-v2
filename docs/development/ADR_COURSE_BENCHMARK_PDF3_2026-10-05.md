# ADR COURSE Benchmark PDF3

## Décision relue avant implémentation

Mandat propriétaire : PROJET_V2_BENCHMARK_COURS_PDF3, reçu le 5 octobre.
Entrée : 790230f7a9762e61ef22800b9fcbeb8f59e221af, après résolution du sélecteur
des questions sans thème. Le PDF de référence est fourni par le propriétaire.

Le modèle COURSE-EXPLAINED-1.0 représente un texte expliqué. Il ne représente
pas les documents, activités, réponses élèves et version professeur demandés.
Une nouvelle structure versionnée COURSE-CHAPTER-1.0 est donc nécessaire.

## Responsabilités et compatibilité

- Pedagogical Design possède le contrat de chapitre et ses contrôles de liens.
- Un successeur fermé R6-P0-PRODUCTION-COURSE-2.0 ajoute course_chapter au bundle.
  Le contrat historique 1.0 demeure lisible et exportable sans réécriture.
- Les questions d'apprentissage et réponses professeur sont dans le chapitre.
  Les champs d'évaluation du bundle restent vides pour COURSE.
- La projection élève enlève les réponses et la provenance interne des documents.
  La projection professeur ajoute réponses, justification, vigilance et remédiation.
- ReframeCourseInbound crée le nouveau M01 comme enfant local, résout le même
  programme Management Première via Application et ne consomme aucun grant.
- Materialization Export projette le chapitre et rend un DOCX original via
  un adaptateur OOXML déterministe, sans dépendance runtime supplémentaire.
- La validation structurelle, le rendu visuel, l'admission institutionnelle et
  l'acceptation pédagogique demeurent distincts.

## Portée et activation

Le successeur est explicitement choisi pour M01. Il n'est pas propagé aux anciens
cours ni au dispatch fournisseur normal avant acceptation du prototype.
Le contrat et ses contrôles sont utilisables localement. Les anciens cours sont
signalés incomplets au regard du benchmark, sans changer leur preuve historique.
La projection fournisseur normale et ses anciens grants ne sont pas modifiés
dans ce travail hors ligne. L'activation ultérieure exige une requête exacte
et les autorisations applicables.

## Données et autorités

Le benchmark SGN inspire l'architecture, jamais le cadre institutionnel de M01.
Le thème et la question 1.1 de Management sont vérifiés dans le programme public
du ministère. Les capacités travaillées sont rattachées à ce programme en audit,
sans fabriquer des CAPACITY dans SQLite. Le snapshot et ses CONTENT_GAP demeurent.
Les données du cas sont inventées localement et leur provenance est conservée
dans le chapitre et les preuves privées ; la diffusion n'affiche pas de jargon
technique ni de faux témoignage provenant d'une organisation réelle.
Les données chiffrées, noms et documents du PDF ne sont pas copiés.

## Contrôles à exécuter

- Champs fermés, bornes, unicité et ordre des questions/corrigés.
- Identités programme, version, question et thème liées au contexte exact.
- Documents et capacités référencés, progression observation/analyse/formalisation/
  réinvestissement, synthèse, connaissances et transfert.
- Absence des réponses et métadonnées internes dans élève et DOCX élève.
- Rejet des chapitres incomplets et mutations de liens/identités/projections.
- Sauvegarde, réouverture, validation et deux exports via Application, parents
  inchangés et aucune autorité active restaurée.
- Rendu et inspection de toutes les pages, comparaison au PDF exact, audit
  des limites institutionnelles, recette enseignante explicitement en attente.
- Succession versionnée des pins avec prédécesseur 790230f conservé, lint,
  typecheck, tests et inventaire d'exclusion avant commit local.

Relecture : aucun accès agent à SQL, repository métier, secret ou filesystem métier ;
aucun assouplissement de gate, aucune migration seed, aucune promotion implicite.
Les changements de contrats restent bornés au chapitre COURSE et ses projections.
