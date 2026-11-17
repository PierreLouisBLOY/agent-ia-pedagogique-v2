# Consolidation de V2 après la PR 6

La base est `03da7a825c4c4dbccf6bf4b023ed4eb50d2120b0` (27 octobre 2026).
Cette livraison rapproche la copie utilisée par le service local et la copie
de travail. Les fichiers de main absents d'une copie partielle sont conservés.
Les bases, documents pédagogiques réels, registres, clés et chemins du
propriétaire ne sont pas distribués avec le code.

## Périmètre intégré

- Mode d'essai manuel choisi explicitement au lancement, budget persistant de
  5 USD, secret backend `OPENAI_API_KEY`, aucune invite console. Le démarrage
  et les lectures ne lancent aucune génération. Le budget représente une
  somme de bornes conservatrices, pas une facture. Aucun retry ni remboursement
  automatique après une issue incertaine.
- Bibliothèque documentaire SQLite séparée, import borné par Application,
  sélection exacte de documents, provenance et distinction entre synthèse
  pédagogique locale et source officiellement admise.
- Fil conducteur d'organisation réelle, lié au contexte, aux références et
  aux octets transmis. Les situations construites restent explicitement
  identifiées ; une identité d'organisation ne prouve pas ses pratiques.
- Chapitre progressif : contexte, parties introduisant leurs documents et
  notions, formalisation, synthèse, vérification et deux activités de transfert.
  Les anciens formats restent lisibles. Le chapitre 3 sert de cas structurel
  de validation ; la référence éditoriale formelle 001 reste le chapitre 2.
- Tables rectangulaires communes au schéma fournisseur et à la validation.
  Le correcteur local de cellules vides excédentaires est explicite et produit
  une copie avec audit ; il n'est pas appelé automatiquement par la génération.
- Suivi HTTP pendant l'appel, sauvegarde Application, réouverture et exports
  Word élève/professeur par les writers existants.

## Décisions et revue

Les décisions locales du 27 octobre (mode d'essai réutilisable) et du 29 octobre
(fil conducteur réel et raccord Application) ont été relues avant leur
implémentation d'origine. Cette consolidation conserve leurs frontières :
Application, génération, validation, qualité et promotion restent distinctes.
Les profils P1 et leurs historiques ne sont pas migrés vers le mode d'essai.
Le mode reste exclusif des anciennes autorisations live dans le lanceur.

La revue de consolidation vérifie les différences avec main, le calcul et le
verrou du budget, l'unicité persistante, l'absence de reprise au redémarrage,
la sélection documentaire, les projections sans secret et la séparation des
exports. Un arrêt de session publié par une autre composition est désormais
relu avant construction du transport et sous le verrou avant réservation.
Il ne suffit donc pas de garder un processus ouvert pour ignorer cet arrêt.
L’aperçu navigateur suit aussi les trois positions de formalisation et les
deux activités progressives, avec séparation des réponses professeur. Les
tests chargent désormais le helper effectivement livré dans real-course.js.

La revue est une revue technique effectuée par l'agent intégrateur ; elle ne
constitue pas une approbation humaine indépendante. Les résultats exécutés et
leurs limites sont consignés dans la description de la PR et le journal local.

## Lancement

Le lanceur normal reste `python -m backend.adapters.inbound.cli.local_browser`.
Le mode `--manual-provider-tests` exige une racine explicite
`--manual-test-receipts`, un stockage existant `--saved-root` et
`--word-profile product-v7`. La racine de session ne doit pas être remplacée
pour remettre à zéro un budget consommé. Le lanceur Windows existant transmet
la configuration utilisateur au processus backend sans afficher le secret.

La bibliothèque se sélectionne avec un descripteur complet :
`--documentary-library`, `--documentary-data-root`,
`--documentary-database-sha256`, `--documentary-archive-sha256` et
`--documentary-snapshot-sha256`. Une sélection ne confère aucune admission
officielle ni autorité d'envoi par elle-même.

Le serveur reste limité à la boucle locale. Une fusion ne redémarre pas le
service existant et n'installe aucun accès réseau ou composant système.

## Évolution conservée séparément

L'adaptation supplémentaire de `ReframeCourseCommand` au contrat du chapitre
réel est conservée sur une branche distincte. Elle concerne le recadrage local
d'une production existante et ne fait pas partie du parcours de création
chargé dans la copie de service prise comme référence pour cette fusion.
Les variantes remplacées par cette copie restent documentées dans la matrice
de provenance locale ; les copies d'origine ne sont pas modifiées.
