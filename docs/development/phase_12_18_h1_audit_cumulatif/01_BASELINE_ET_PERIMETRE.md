# 12.18-H1 — Baseline et périmètre

Audit documentaire et lecture statique du 2026-09-05. La demande actuelle est l'exécution du bundle H1, pas celle d'anciens prompts ni une reprise d'autorisation live, migration ou commit.

## Identités et filiation vérifiées

| Rôle | SHA complet |
|---|---|
| Référence B07 avant correctif | `0404852a3be77381bf7b7c903ee6309e2547487e` |
| Correctif test seed / baseline technique de la suite finale | `f28b29f0964d2642b74eb7098f90359d15fb4f0c` |
| Clôture B07 et HEAD d'entrée H1 | `24b7a9850bc4644391dee2307c8a8a31036cd503` |

Branche observée : `phase12/12-16-provider-model-calibration`. Worktree et index propres à l'entrée. Le parent direct de HEAD est bien le correctif ; `git merge-base --is-ancestor` réussit. Les 14 chemins du commit de clôture sont exclusivement dans le dossier documentaire B07 : aucun changement du graphe technique entre la suite exécutée et HEAD. Un inventaire SHA-256 des 2 257 fichiers suivis est pris avant H1 et comparé après production documentaire.

Le correctif comporte quatre chemins : le test d'intégration seed, sa non-régression unitaire et deux preuves B07. Aucune autorisation de ce commit précédent n'est réutilisée ici.

## Sources et portée de l'entrée

Le ZIP H1 a pour SHA-256 `45b8dacde1f0a1f3740009da87920c4912b39ad591f1cda352897b6b942cfcca`. Ses six entrées de manifeste sont vérifiées en lecture d'archive, sans extraction ni exécution de script embarqué. Les instructions de préparation ne sont pas prises pour des résultats déjà acquis.

Sources finales B07 : [livrable](../phase_12_17_08_closure/LIVRABLE_FINAL_CANONIQUE.md), [16 gates](../phase_12_17_08_closure/04_FINAL_GATES.json), [reprise finale](../phase_12_17_08_closure/13_RESUMED_GLOBAL_EVIDENCE.json), [handoff](../phase_12_17_08_closure/10_CLOSURE_DECISION_AND_HANDOFF.md). Le manifeste B07 courant est `8dd32e9eda71dc86ba3bd3dd740291b85f172630bd979807d9558d8b686fde5b`, 15 entrées vérifiées. Les 25 manifestes sources contrôlés comptent 282 entrées : les 23 de B07 (254), la clôture B07 (15), la clôture 12.16 (13). Deux entrées de cette dernière sont des preuves locales ignorées ; leur hash est vérifié sans recopier leur contenu dans Git.

B07 confirme **12.17.8 CLOSED / B07 PASS / 16 gates PASS**, avec prérequis B07 d'entrée en 12.18 satisfaits. Il ne prononce pas la clôture globale de 12.17 : `NOT_CLOSED_NO_ADDITIONAL_AUTHORITY`. Ce constat ne rouvre pas B07 et ne crée pas une nouvelle gate préalable. La demande actuelle donne l'autorité documentaire H1, pas celle de clôturer l'ensemble de 12.17, 12.18 ou le projet.

Priorité : décisions appliquées et livrables locaux courants, puis handoffs. Les prompts historiques ne remplacent ni le code ni une décision postérieure. [AGENTS](../../../AGENTS.md) et [ENVIRONMENT](../ENVIRONMENT.md) ont été lus ; H1 n'introduit pas de dépendance ni de divergence architecturale.

## Exhaustivité et nomenclature

La matrice trace **33 exigences synthétisées**, sur les 16 positions 12.2–12.17 documentées. La position 12.1 est explicitement non identifiée. Ces 17 positions correspondent à l'intervalle demandé ; elles ne constituent pas la preuve qu'il existe exactement 17 sous-étapes canoniques. Les identifiants H1-REQ sont locaux à cet audit, pas une nouvelle nomenclature de gates. Dénominateur canonique exhaustif : inconnu ; aucun pourcentage produit calculé.

Les livrables 12.13 et 12.15 confirment la macro **12.18 — gate finale et livrable complet canonique Phase 12**. H1/H2/H3A/H3B/H3C et les cinq critères navigateur sont repris comme nomenclature de travail du bundle, mais la décision navigateur originale citée n'est pas dans l'archive et n'a pas été retrouvée dans la recherche locale bornée. Le document de roadmap original cité est également absent de ce paquet. Leurs hashes rapportés ne sont donc pas déclarés vérifiés. Les répertoires canoniques externes non disponibles dans le contexte local ne sont ni téléchargés ni présumés vides.

Les titres/niveaux détaillés restent à rapprocher, sans inventer une nouvelle série de sous-gates :
H1 audit ; H2 intégration ; H3A package/lancement ; H3B recette navigateur ; H3C livrable final Phase 12. L'ancienne macro Phase 3/13/14 décrite dans le bundle ne suffit pas à déclarer la livraison globale du projet. Le manque documentaire S01 limite l'exhaustivité, pas la validité de la description du code observé.

## Garde-fous H1

Lecture Git/sources/preuves et création de six documents H1 seulement. Zéro code, test, configuration ou SQLite modifié ; aucun accès seed/runtime utilisateur, aucun serveur lancé, aucun credential résolu, aucun réseau ni provider. Aucun staging, commit, push ou merge. Aucun nettoyage des éléments locaux conservés sous B06/B07. Aucun H2 ni package commencé.
