# Addendum — édition locale du chapitre COURSE conservé

11 octobre 2026, PROPOSED_FOR_DISTINCT_REVIEW. Base `89ef3edc5f9d09e5f769862833ffa2c1b175c8fb`. Prolonge l’ADR de reprise locale sans restaurer une autorité ni les preuves brutes.

## Défaut et décision

Le chapitre riche lie exactement son titre et ses sections de compatibilité. L’éditeur générique actuel modifie uniquement cette projection : une modification ordinaire est donc refusée par COURSE_STUDENT_PROJECTION_BINDING. Le raccorder au chapitre structuré existant ; ne pas convertir le chapitre en cours générique ni effacer ses documents, questions, corrigé ou médias.

Dans la commande revise existante, ajouter une clé fermée `course_edits` aux edits uniquement pour un parent avec course_chapter. Les patchs autorisés sont context (title/text), documents (id/title/text), questions (id/prompt), concepts (id/definition/explanation/example), parts (id/title), synthesis et teacher_answers (id/expected_answer/rationale/vigilance/remediation). Les IDs doivent préexister et rester uniques. Les champs institutionnels, capacités, provenance, sources, tables, relations et médias ne sont pas modifiables par cette clé. Le titre top-level met à jour le titre du chapitre ; les sections sont ensuite dérivées de CourseChapter.sections(), jamais prises du client.

Le frontend construit ces patchs depuis les champs lisibles du chapitre projeté, et montre les compagnons professeur séparément. Une modification du contenu d’un chapitre illustré est refusée si elle peut périmer ses médias : aucune image ancienne n’est réattestée ou régénérée silencieusement. Une modification de titre seule conserve les données pédagogiques et les assets exacts. Le refus est visible et précis ; la voie de préparation média existante reste distincte.

L’enfant passe CourseChapter, P0Production et ReviseSavedP0Candidate ou la voie avec preuves fraîches selon son origine de session. Parent, contexte et références demeurent immuables ; sources historiques=RESERVE. Aucun fournisseur, COUNT, credential, SQL, filesystem ou nouveau stockage.

## Contrôles et retour arrière

Positifs : titre seul d’un chapitre illustré, patchs d’un chapitre sans média, reprise/save/redémarrage/export ; mêmes identités de questions élève/corrigé. Négatifs : ID absent/dupliqué, champ d’autorité ou provenance injecté, section client discordante, patch COURSE sur autre famille, média périmé, mauvais parent/hash. Comparer le parent exact avant/après. Aucun test historique affaibli.

Retour arrière : retirer la clé course_edits et son éditeur structuré ; conserver les enfants déjà produits. Aucun effacement de bibliothèque ou correction rétroactive. Revue technique distincte avant implémentation, recette enseignante NOT_PERFORMED.
