# Alignement institutionnel STMG et cours expliqués

Entrée : cb0d6df2ebb4070ef0c89108e4005bf118e3e1f1. ADR préalable :
ADR_STMG_INSTITUTIONAL_ALIGNMENT_2026-10-05.md. Les productions et grants
historiques conservent leurs empreintes ; aucun appel fournisseur nouveau.

## Contrats et responsabilités

Le contrat P0-CONTEXT-2.0 ajoute une sélection institutionnelle exacte et sa
résolution Application, distinctes de la progression locale. Les sept cadres
fermés sont Management et SGN en première, puis MSDGN commun et les quatre
enseignements spécifiques GF, Mercatique, RHC et SIG en terminale. Une notion
canonique conserve son identité et plusieurs liens par programme et version.

Knowledge Reference projette les cadres et liens existants. La connexion SQLite
reste dans l'adaptateur outbound, authentifiée et query-only. Les consommateurs
passent par STMGAlignmentInbound. Aucun agent n'exécute de SQL ni de migration.
Le contexte historique R6-P0-CONTEXT-1.0 reste lisible, exportable et rejouable
dans les harnais déclarés. La composition normale exige le contexte exact pour
toute nouvelle préparation STMG ; il n'existe aucun défaut Management.

La résolution précède AG-01 et la lecture AG-02. Elle filtre programme, version,
question, capacités, notions et profondeur. AG-03 et AG-04 reçoivent les mêmes
identités et preuves. Les liens implicites, IA ou proposés restent non admis.
Le contrôle financier et l'autorisation fournisseur existants restent requis,
après cette gate institutionnelle. Les anciens grants ne peuvent être étendus
à ces requêtes dont les empreintes changent.

## Politique COURSE

COURSE-EXPLAINED-1.0 impose les sections objectifs, notions expliquées, méthode,
application guidée et synthèse. La profondeur est confirmée ; aucune limite de
pages n'est implicite. Un cours peut expliquer son application guidée ; ses
questions, corrigé et barème structurés restent vides. Le contrôle de structure
ne démontre pas la profondeur pédagogique : celle-ci reste à la recette.

## Résultat du catalogue authentifié

La projection Application a retrouvé 628 notions canoniques et les sept cadres,
soit 4 396 cases notion/cadre : 961 cases ont des liens contextuels à admettre,
3 435 n'ont aucun lien dans ce cadre. Les sept versions sont V47_SOURCE_SNAPSHOT,
sans document officiel ni source émettrice rattachés ; aucune capacité CAPACITY
n'est encodée. L'unique institutional_attachment est INFERRED / AI_INFERENCE /
PROPOSED. Une publication de snapshot ne prouve pas l'autorité du programme.

Ces constats interdisent actuellement une nouvelle génération STMG en composition
normale. L'interface expose les choix et les lacunes ; le backend refuse le
dispatch avant l'autorisation fournisseur. Il faut admettre des provenances,
capacités et liens exacts, par un travail de référence distinct de la seed,
avant un usage fournisseur futur. Aucun rattachement n'est inventé pour obtenir
un statut vert. La matrice complète et ses identités restent hors Git.

## Vérifications

Tests positifs et de substitution : sept cadres, confusion Management/SGN,
commun/spécifique, GF/autres spécialités, mauvaise version/thème/provenance,
propagation implicite, profondeur, source notionnelle exacte, structure de cours,
headers des exports et maintien des contextes historiques. Les pins du delta
actif sont ajoutés dans un successeur du manifeste ; le prédécesseur reste dans
Git. La qualification globale de 01f2e94 comprend 6 731 PASS, 415 FAIL,
35 ERROR et 28 SKIP, conservés dans les résultats bruts hors Git. Elle n'est pas
annoncée verte. Les anciens inventaires, les pièces privées manquantes et les
préconditions runtime sont distingués dans le rapport, sans attribuer tous les
échecs à des causes externes. Les replays sur cb0d6df sont identifiés séparément.

Les dix assertions de sélection de sources conservent leur couverture sur un
contexte BTS valide ; elles utilisaient précédemment un contexte STMG historique
que la composition normale refuse désormais. Deux tests supplémentaires vérifient
ce refus en première et terminale avant la lecture des preuves. Les contextes
historiques sauvegardés et les harnais explicitement déclarés restent lisibles.

Une correction ultérieure du sélecteur conserve toutes les questions du catalogue,
y compris celles sans numéro de thème dans leur libellé. Huit questions SGN étaient
masquées par ce filtre. Leur identifiant exact reste sélectionnable ; un thème
absent reste null et produit THEME_RELATIONSHIP_UNRESOLVED / CONTENT_GAP. La
préparation locale peut exposer cette lacune, mais génération et review restent
refusées avant autorisation. L'interface et les exports affichent « Thème non
renseigné », sans fabriquer un numéro ni modifier les données originales.

## Références publiques vérifiées

Le découpage des enseignements est confirmé par la page ministérielle
[Programmes STMG](https://eduscol.education.gouv.fr/5862/programmes-et-ressources-en-serie-stmg).
Les programmes de première relèvent du BO spécial 1 du 22 janvier 2019,
[NOR MENE1901646A](https://www.education.gouv.fr/bo/19/Special1/MENE1901646A.htm).
MSDGN terminale relève du BO spécial 8 du 25 juillet 2019,
[NOR MENE1921262A](https://www.education.gouv.fr/bo/19/Special8/MENE1921262A.htm).
Ces références bibliographiques vérifiées ne sont pas une réconciliation
automatique de tous les éléments du snapshot ni une recette pédagogique.
