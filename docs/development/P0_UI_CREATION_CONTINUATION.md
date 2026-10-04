# Raccordement P0 depuis 48ab2e9

La continuation ajoute un adaptateur HTTP compagnon fermé à sept routes et un
service Application commun aux 24 cellules. Les contrats R6 Context, Production,
ReadView, Create/Revise, Validate, SavedProduction et ExportSaved sont réutilisés.
Le registre historique R2/R3/R4 est inchangé. Les frontières validées restent en
place : aucun SQL, secret, fournisseur ou accès de stockage dans les agents ou
les handlers HTTP. Aucun framework ou adaptateur fournisseur n'est introduit.

Le port sortant P0 neutre complète le port conversationnel typé R2, qui ne peut
pas accepter un contexte cours ou quiz. La composition normale le laisse non
lié. Son contrôle d'autorisation précède son unique dispatch ; aucune réponse
synthetique n'est disponible dans le lanceur normal. Le double est uniquement
dans tests/support/p0_generation_double.py et la composition du harnais.

La sélection d'un passage utilise la recherche Application existante avec son
identifiant et sa version. Les six ancrages exacts R6 restent proposés en
complément ; leurs corrections ne font pas partie de la requête de génération.
Leur statut REVIEW/NEEDS_REVIEW n'atteste aucune autorité officielle. La sélection
pédagogique et la pertinence des références restent à relire.

Les commandes sont liées à leur contenu complet et consommées avant dispatch.
Le même identifiant restitue son résultat, une substitution est refusée ; une
issue inconnue n'est pas relancée. Une préparation consommée ne peut être envoyée
avec un autre identifiant. Les éditions humaines créent une nouvelle version,
sans mutation du parent, et sans appel fournisseur. Les réponses professeur sont
consultées à part de la vue élève. Les sauvegardes passent par R4 et conservent
les parents ; la réouverture ne restaure aucune autorité.

Les preuves HTTP de la matrice portent sur un transport simulé déclaré. Elles
ne valent ni génération réelle de ces 24 productions, ni recette enseignante.
Les cinq assertions historiques sont conservées ; la succession courante est
inventoriée et protégée séparément par le garde R6 et ses tests de mutation.
