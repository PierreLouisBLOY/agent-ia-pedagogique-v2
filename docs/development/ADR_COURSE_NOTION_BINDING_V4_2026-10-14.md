# ADR — notions confirmées du COURSE riche, successeur V4

Date : 14 octobre 2026, Europe/Paris.
Statut : PROPOSITION POUR REVUE DISTINCTE AVANT IMPLÉMENTATION.
Portée : même LU-PRODUIT-01 ; changements locaux hors fournisseur. Aucun nouveau lot A06.

## Constat et limite du diagnostic

La voie riche V3 compare concepts.notion aux topics libres du contexte. La sélection institutionnelle porte également des notion_refs et la résolution Application leurs libellés canoniques. Un thème libre tel que « organiser l'action collective » n'est pas le libellé de la notion sélectionnée « Organisation ». L'UI permet ces deux valeurs distinctes ; la projection institutionnelle bornée expose déjà les libellés de notions sélectionnées. Le fournisseur peut donc choisir un libellé canonique qui est ensuite refusé par le binder V3.

Le diagnostic personnel sur la réponse capturée confirme parseur et guard acceptés, puis P0_RICH_COURSE_NOTION_UNKNOWN. Les pièces privées exactes restent dans le dossier technique externe, jamais dans Git. Il ne certifie ni le reste de la structure, ni la fidélité aux sources, ni une acceptation pédagogique. Une simple correction de ce premier refus ne qualifie pas la réponse entière.

Le contrat V3 a été choisi explicitement dans l'ADR du 13 octobre : sa règle ne sera pas modifiée rétroactivement. Les anciens corps, schémas, contextes, chapitres, grants, réservations et événements restent inchangés. Les voies expliquées et les autres familles conservent leur comportement.

## Décision proposée

Créer un embranchement explicite, sélectionné dans la nouvelle demande normale seulement :

- P0-CONTEXT-COURSE-4.0, mêmes champs que COURSE3, format CHAPTER exclusivement, STMG résolu/admis et numéro local explicite.
- P0-COURSE-RICH-CONTENT-2.0 et entrée fournisseur R6-P0-COURSE-CONTENT-INPUT-3.0.
- COURSE-CHAPTER-LINEAGE-4.0 pour le chapitre lié.
- R6-P0-PRODUCTION-COURSE-3.0 pour sa production.
- Le contrat de contexte V3 demeure celui du choix EXPLAINED ; une ancienne demande CHAPTER V3 reste V3 lors de lecture/reprise/édition. Aucun changement implicite de contrat sauvegardé.

Le champ topics conserve intégralement le thème libre confirmé. Les notions du nouveau chapitre proviennent uniquement des lignes de notions réellement résolues par Application pour la sélection exacte. Aucune inférence à partir du thème, slug, casse ou similarité n'alloue une notion.

Un helper pur dans les DTO de pedagogical_context vérifie la résolution liée par selection_sha256, le statut RESOLVED_ADMITTED, les refs sélectionnées distinctes et non vides, une ligne exacte par ref, des labels non vides et non ambigus. L'ensemble de refs résolues doit être exactement l'ensemble sélectionné. L'ordre de sélection détermine N1…N16. Une résolution manquante, modifiée, supplémentaire, dupliquée ou à libellés ambigus est refusée.

## Fournisseur et binder cohérents

Le schéma V2 reste statique et fermé. Il conserve les trois champs racine title/course_chapter/limitations et les contraintes documentaires, pédagogiques et de séparation. Seul le champ concept notion devient notion_id : alias fermé par forme N1…N16. L'appartenance et la couverture exacte de la sélection sont contrôlées localement, même pour une sortie injectée hors fournisseur.

La demande V4 transmet course_notions=[{id,label}] à partir de la résolution déjà employée par la projection institutionnelle bornée. Aucune définition, ancre NOTION brute, nouvel extrait, référence officielle, ID de notion local, preuve d'admission ou droit métier n'est ajouté à cette liste. Les labels sont des repères de cadrage, pas une source disciplinaire ni une certification officielle. Les capacités C1… et les références admises conservent leurs rôles.

Les consignes V4 demandent les alias N de cette liste, les contenus substantiels complets et l'intégrité des liens. Elles explicitent les invariants déjà contrôlés : chaque question est affectée une seule fois à observation/analysis/reinvestment/knowledge_check/transfer ; groupes requis non vides, numérotation continue et réponses professeur dans le même ordre. Le nombre de parties doit être choisi en fonction de la sortie disponible et de ces contraintes. Aucune recette universelle de nombre de pages, parties ou questions.

Le binder V4 transforme uniquement notion_id en libellé canonique correspondant. Il ne fabrique, corrige, complète ou paraphrase aucun definition/explanation/example, document, question, méthode, réponse, vigilance, remédiation ou synthèse. Les textes fournisseur restent identiques. Alias inconnu, label libre à la place d'un alias, notion sélectionnée omise, référence déplacée ou autorité injectée sont refusés.

Le chapitre V4 contrôle que ses notions et tous ses concepts sont liés à cette sélection. Context topics et son SHA ne sont pas réécrits. La production V3 exige chapitre V4 + contexte V4 ; la production historique V2 ne peut absorber silencieusement le nouveau chapitre. Les règles existantes de couverture des questions, provenance, claims, anti-copie professeur et numérotation restent actives. Le scanner partagé et les politiques AG-03 restent inchangés.

## Consommateurs

Adapter ensemble :

1. DTO P0Context et helper pur de notions confirmées.
2. Instructions, schéma statique, projection fournisseur et politique du cours.
3. Mapper pur, CourseChapter, P0Production et validation de livraison.
4. Reframing/édition locale, conservation, sérialisation, reprise et export Word via les use cases existants.
5. Nouvelle demande UI CHAPTER V4 ; pas de migration des anciennes versions.
6. Tests synthétiques par impact et preuve de conservation/reprise/export du successeur hors fournisseur.

Les exporteurs continuent les projections élève/professeur existantes ; aucune voie d'export ad hoc ni accès direct agent aux stores. Les définitions des ancres internes ne sont pas utilisées pour enrichir un cours après génération.

## Préconditions et tests

Avant implementation : revue distincte effective de cette version exacte de l'ADR, portée et réserves consignées. Un avis antérieur ne qualifie pas ce successeur.

Contrôles positifs : thème libre différent du libellé canonique ; N1 exact ; plusieurs refs et ordre explicite ; contenus substantiels préservés ; demandes/vues/édition/conservation/reprise/export cohérents ; enseignements Management/SGN/MSDGN distincts.

Contrôles négatifs : label arbitraire, alias hors sélection, couverture de notions incomplète, résolution/selection_sha changé, ref supplémentaire ou omise, doublons et labels ambigus, injecter autorité/identités, changer provenance/références, fuite professeur, liens/numéros/couverture de questions invalides, mélange contextes/chapitres/productions V3/V4.

Conserver les témoins de wire historiques et refus V3. Les fixtures sont synthétiques et passent par les use cases Application ; aucune base d'origine, archive métier, réponse réelle ou pièce privée comme fixture publique. Ruff/typecheck applicables et tests ciblés réellement exécutés ; aucun nouveau global ni répétition des inspections acquises.

## Live, réponse rejetée, retour arrière

Ce correctif n'autorise aucun appel. Toute nouvelle demande change le contexte/schéma/corps et exige son rattachement précis et les consentements frais prévus par P1. La continuité de la campagne reste bloquée sur l'événement PARSING_REJECTED connu ; cet ADR n'autorise aucun assouplissement du ledger, ni récupération d'un grant, remboursement, effacement d'événement, reset de slot/quota/fenêtre ou promotion.

Le résultat rejeté n'est pas requalifié ni enrichi. Une disposition de l'ancienne tentative et une qualification ultérieure exigent des décisions bornées distinctes, présentées ensemble avec les rattachements réellement nécessaires après stabilisation. Le budget pessimiste déjà réservé reste conservé.

Rollback du code : conserver la branche/copie d'origine exacte et sélectionner explicitement la version antérieure du package. Aucun rollback de base, migration, nettoyage, déploiement ou modification du runtime utilisateur. Le successeur est développé dans un worktree local séparé, jamais activé dans la copie P1 adoptée par cette seule proposition.

La recette enseignante demeure exclusivement la dernière étape, non réalisée et non signée.
