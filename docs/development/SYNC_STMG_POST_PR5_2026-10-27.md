# Synchronisation STMG après PR 5

Cette intégration part de `047a67a28a25e29bd126c2f3a83163b6b0e391cf`.
Les 38 commits de PR 5 sont déjà intégrés. Les autres worktrees sont conservés.

## Provenance et sélection

La source de comparaison est le package 327 R5, SHA-256
`bd352c8a9edf5c5ee5ad25c074ec729c72301d98a560be4dcdd699032c6cc430`.
Ses 1 171 fichiers ont été rapprochés des octets Git : 921 identiques,
197 nouveaux et 53 différents. Les 1 899 chemins propres à main sont conservés.
Le patch sélectionne des fonctions ; il ne remplace pas le dépôt par l'archive.

| Lots | Fonctions retenues |
| --- | --- |
| 315–322 | Référence de format, assemblage local, édition, sauvegarde et Word élève/professeur |
| 323B–D | Identifiants canoniques, exercice structuré, focalisation explicite et composants Word communs |
| 324 | Orchestration des agents de recherche, génération/amélioration et critique avec autorités distinctes |
| 325/325S | Chaîne finie contrôlée et représentation XML OPC |
| 326/327 | Sources et organisations, proposition/édition locale, filiation et conservation des médias |

Les adaptateurs de consultation et de récupération ne sont pas tous des
dépendances du serveur normal. Certains sont des entrées Application isolées :
capture partielle, récupération 323B, origine de chaîne finie et préparation OFF.
Ils conservent leurs contrôles, sans charger ici les décisions privées ni les registres.

Les évolutions propres au calcul local de formules 326 et au bilan fonctionnel
329 sont exclues. Le code BTS déjà sur main, ses migrations et ses formules sont
conservés. Les cinq blueprints de chapitre 317–321, leurs médias et recettes
privées restent hors Git. Des cas synthétiques indépendants vérifient seulement
les raccords techniques ; ils ne remplacent pas la recette éditoriale privée.
Les tests comparatifs d'archives exigent une source historique explicitement
désignée, sinon ils sont SKIP avec motif.

## Conflits et contrôles

Les hunks BTS sont retirés des fichiers communs, sans supprimer les API de main.
La signature `locked(create=...)` est conservée jusqu'au ledger de continuité,
qui ouvre toujours le LOCK historique existant. Les modules pytest homonymes
sont collectés en mode importlib, avec le répertoire des helpers de test déclaré.
Les frontières Application, contrats sans SDK et séparation génération,
validation, qualité et promotion restent celles d'AGENTS.md et des ADR existants.

Les journaux, comparaisons par fonction, scans et avis indépendant sont remis
dans le livrable local A–D. Ils ne sont pas ajoutés au dépôt. Aucun résultat
d'appel réel n'est attribué aux transports synthétiques.

## Limites de la fusion

La référence éditoriale `V2-FORMAT-COURS-STMG-001` reste le chapitre 2,
« Les fonctionnements individuels ». Ses originaux Word acceptés restent privés.
La fusion ne vaut aucune nouvelle adoption de source, aucun consentement ou
chargement opérationnel. Les douze rattachements proposés restent non adoptés.
Les preuves M03 et l'écart ASSEMBLY5/LINEAGE3–4 avec médias restent à résoudre
sur le chapitre réel, sans assouplir le contrôle obligatoire.

Les historiques UNKNOWN, 406A, 2f1e, 09ce, 7c99, P1, reçus et réservations restent
inchangés. Aucun service 8943/8944, appel fournisseur ou donnée canonique n'est
modifié. Fusionné sur GitHub, chargé, ON réel et accepté pédagogiquement sont
des états distincts.
