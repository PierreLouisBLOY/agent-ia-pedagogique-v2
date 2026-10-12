# ADR LU S5 Rétention explicite du chapitre sans média

Statut : PROPOSÉ POUR REVUE PRÉALABLE. LU-PRODUIT-01, 12 octobre 2026.
Base source exacte : 9c1f7e256ba67948f10f575f571f7068e3b5c879.

## Constat réel et périmètre

Le COURSE confirmé a été récupéré au record bc7dbc84… puis deux descendants
locaux, structurés COURSE-CHAPTER-1.0, ont été sauvegardés. L'inspection Word
a localisé une ligne de réponse orpheline dans le second enfant. Le correctif
suivant a été refusé par Application : R4_VERSION_LIMIT. Les trois versions
restent conservées. La limite 3 du chapitre1.0 est une règle historique
explicitement testée, pas une permission à élargir silencieusement.

## Successeur proposé et sélection

Ajouter COURSE-CHAPTER-LINEAGE-3.0, choisi explicitement dans la construction
d'un nouveau chapitre local. Il possède exactement les champs, les validations
et les projections de COURSE-CHAPTER-1.0, sans octet média ou nouveau stockage.
Les anciens defaults, le payload/provider schema, les profils P1 et leurs
permissions restent inchangés. Aucune conversion automatique de bibliothèque.

Un SavedProduction revalidé doit cumuler origine LOCAL_APPLICATION,
bundle R6-P0-PRODUCTION-COURSE-2.0 et chapitre LINEAGE-3.0 pour recevoir le plafond
32. Toutes les versions de la production sont comptées, anciens ancêtres inclus.
MEDIA-2.0 conserve sa branche32 actuelle, y compris son comportement d'origine.
Plain1.0, productions génériques et imports documentaires LINEAGE-3.0 gardent3.

## Objets et effets autorisés

- Pedagogical Design DTO course_chapter.py : constante et reconnaissance du
  contrat3.0 dans le même validateur fermé. Aucun champ supplémentaire.
- Adaptateur persistence/saved_production.py : nouveau prédicat cumulatif
  pour le seul successeur3.0, sans modification du verrou ou de la transaction.
- Test ciblé du successeur et garde exact de ces nouveaux owners/ADR/tests
  selon le protocole de succession existant du lot, après sa revue.

Le plafond global300, la taille16MiB, le contrôle de catalogue et la limite32
des ancêtres dans l'inbound restent identiques. L'idempotence et le refus des
conflits précèdent le plafond. Aucune suppression, réécriture, déduplication,
migration, nouveau store P1 ou reset de consommation. Aucun fournisseur.

## Contrôles prévus avant effet réel

Exécuter les tests synthétiques : trois anciens ancêtres inchangés ; quatrième
version3.0 réussie ;32e idempotente ;33e refusée sans catalogue changé ;1.0 et
imports toujours refusés à4 ; MEDIA historique inchangé ; contrat inconnu ou
champs médias dans3.0 refusés ; sauvegarde/réouverture/export et séparation
élève/professeur ; mauvais bindings de programme et document conservés.
Ruff/mypy et consommateurs de chapitre/sauvegarde/export ciblés, sans global
pour la seule consignation. Les anciens tests/FAIL/SKIP ne sont pas réécrits.

## Retour arrière et livraison

Conserver le package9c1f7e2 et ses sources ainsi que toutes les versions.
Avant la première sauvegarde3.0, un retour à l'ancien package est possible
sans mutation de données. Après une sauvegarde3.0, l'ancien lecteur peut refuser
ce contrat : ne pas le présenter comme compatible ni supprimer les descendants
pour le faire fonctionner. Rester sur le lecteur qualifié successeur pour ces
versions ; le parent1.0 et ses exports antérieurs restent accessibles dans
leurs preuves et copies conservées. Aucun rollback ou déploiement personnel.

Le code et le package successeurs seront identifiés séparément. Ils ne
reprennent aucune autorisation live bd847eb/9c1f7e2. Toute activation P1 future
reste soumise au rattachement exact prévu, sans toucher LOCK, slots, budgets
ou namespace. La revue assistée ne vaut pas décision pédagogique/propriétaire.
