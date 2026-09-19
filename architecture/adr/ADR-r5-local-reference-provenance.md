# R5 — Provenance locale réelle et préparation sans exécution

Décision propriétaire : extension explicitement approuvée après constat du refus
des références non synthétiques, sur `1eca5e3c3a1029c4d72c3955871c8aa1c44169d3`.

Le contrat de provenance évolue en `CONVERSATION-REFERENCE-PROVENANCE-1.1` :
le label historique synthétique reste accepté à l'identique ; un second label
fermé, `REFERENCE_LOCALE_R5_V1`, désigne une source locale réelle, sans présumer
son autorité officielle. Aucun mélange implicite ni label libre n'est admis.
Les identités, limites, sections, grounding et autres contraintes restent intacts.

Le port M04 de préparation ne produit ni candidat ni version. Il emprunte les
mêmes deux étapes AG02/AG03, contrôles de délégation et préparation neutre que la
génération, mais s'arrête à `GenerationCoordinator.prepare`. Un port de refus
remplace tout transport. La réussite est « projection préparée », jamais
« génération réussie ». Les anciens chemins live, budgets et grants ne changent pas.

Une sélection explicite de locators issus de la recherche M03 est relue sur une
copie privée authentifiée via OP-11/OP-13 et F2A. Les agents n'acquièrent ni SQL ni
filesystem. Le classement de recherche n'est pas une validation pédagogique.
Les liens documentaires manquants restent signalés ; aucun fichier externe ou URL
n'est ouvert. Les projections et résultats réels restent hors dépôt et hors modèle.

L'entrée locale de préparation complète le navigateur de recherche déjà livré,
sans nouvelle route HTTP. Les tests synthétiques, y compris R4, restent portables.
La recette réelle sur copie privée est distincte. Les successeurs de guards sont
authentifiés par chemins, fonctions et empreintes exacts, sans exception globale.

Originaux, migrations utilisateur, règles CAP, cycle de versions, format R4,
fournisseurs et prochaines phases restent hors de ce changement.
