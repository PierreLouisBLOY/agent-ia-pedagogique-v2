# Corrections PR 4 du 8 octobre 2026

Référence examinée : `057f6874f47e5da6d5227f427cfb395a2b703054`.
La revue technique assistée publiée sur cette référence demande REV4-01,
REV4-02 et REV4-03. Le propriétaire a autorisé leur correction dans le même
lot A06, avec les obligations de clôture encore applicables.

## Delta et responsabilités

- REV4-01 : le service Application reconnaît les demandes de comptage et les
  comparaisons de quantités non monétaires, ainsi que les réponses numériques
  accompagnées d'une unité. Le verbe « analyser » seul laisse l'applicabilité
  indéterminée. Une année dans un objectif qualitatif n'impose pas un calcul.
  Le contrôle requis conserve ECHEC tant qu'aucun oracle indépendant lié au
  bundle exact n'a été exécuté. Aucun PASS structurel ne certifie l'arithmétique.
- REV4-02 : le composeur BTS demande la sélection du référentiel, du processus,
  de l'activité, des compétences et des notions avant de construire le contexte
  confirmé. Il conserve le garde Application et ne choisit aucun premier cadre.
- REV4-03 : chaque version affichée remplace ou invalide la qualité du parent.
  La génération et la révision consomment la qualité de leur propre réponse.
  Une qualité absente reste non vérifiée. Une validation tardive ne remplace
  pas le panneau d'une autre version ou d'un document rouvert. Le frontend
  présente les décisions Application ; il ne calcule aucun verdict métier.

Les contrats, la composition fournisseur, les audiences, les oracles et le
scanner partagé restent identiques. Il s'agit de corrections dans les
responsabilités existantes, sans nouvelle dépendance ni déviation architecturale.

## Régressions et limites des preuves

`tests/unit/test_pr4_quantitative_application.py` utilise le service réel avec
la fixture institutionnelle BTS synthétique qualifiée déjà présente dans les
tests. Le seul transport de génération est un double déclaré, sans fournisseur.
Il couvre effectifs, réponses nues et avec unité, paraphrases, distance, durée,
volume, révision, validation, review refusée et enveloppe de conservation.

`tools/tests/pr4_lifecycle_regressions.test.cjs` exécute les fonctions et handlers
du fichier frontend courant. DOM, HTTP, prévisualisation du contexte et mise en
page sont des doubles déclarés. Il couvre CG1/CG2 avec et sans présélection,
sélection explicite suivie du submit de préparation, STMG, demande ambiguë,
génération, révision, validation et réouverture. Il ne constitue pas une preuve
navigateur ou une recette pédagogique.

La reproduction initiale a exécuté 17 cas Application (15 FAIL, 2 PASS) et 13
cas frontend (10 FAIL, 3 PASS). Le premier rejeu corrigé a exécuté les mêmes
populations avec 17 PASS et 13 PASS. Les résultats bruts, leurs empreintes et
les dépendances sont conservés hors Git dans le dossier A06. Les contrôles
finaux et les résultats globaux sont consignés séparément sur leur état exact.

## Succession de couverture active

Le manifeste R6 ajoute un successeur explicite, rattaché à la référence
examinée et à son manifeste parent. Il conserve tous les 422 propriétaires
précédents, les 27 exclusions privées, les décisions historiques et la baseline.
Il protège les deux nouveaux tests et cette note, avec les deux sources corrigées.
Les fonctions du garde restent inchangées ; seule la pin du manifeste est mise
à jour. Les mutations de contenu, suppression, substitution et index restent
obligatoires pour chaque propriétaire actif. Les probes historiques ne sont
pas réécrits. Cette succession ne prouve aucune précondition privée absente et
n'étend aucune disposition historique.

La relecture finale distincte doit couvrir ce delta et la succession avant
intégration. La revue assistée initiale reste une demande de corrections.
Les treize FAIL historiques, cinq SKIP, sept lignes SQL, contrôles Windows/R1,
Word Q18, historique et règles GitHub conservent leurs obligations propres.
Aucune génération fournisseur, acceptation enseignante, signature ou fusion
n'est effectuée par ce correctif.

## D03 : copie temporaire de référence protégée

Le rejeu exact R1 avec la copie de référence R5 authentifiée a révélé une
copie temporaire héritant de l'attribut lecture seule via copy2. Le provisioning
copie désormais les octets avec copyfile dans le fichier privé déjà créé.
Les attributs et ACL de la seed restent inchangés ; aucun droit nouveau n'est
accordé. Les vérifications de chemins, hardening, empreintes, migrations,
publication atomique et conservation de la seed restent obligatoires.
Le test synthétique dédié échoue avant et réussit après. Le rejeu R1 réel
et les contrôles finaux sont consignés séparément, sans convertir son ancien
SKIP ni effacer le premier échec de préparation. Cette correction ne résout
aucune des sept réserves de DDL SQL01–SQL07.

## Complément révélé par le global 859826a

Le premier rejeu complet de cette continuation conserve 7 952 PASS, 14 FAIL,
34 ERROR et 5 SKIP. Il a utilisé la référence R5 authentifiée, protégée en
lecture seule. La fixture institutionnelle HTTP héritait encore de cet attribut
via copy2 : les scénarios s'arrêtaient avant leur parcours. La fixture copie
désormais les octets avec copyfile dans son dossier de test privé, sans changer
la référence. Son admission reste synthétique, sans autorité pédagogique.

Le fitness de publication atomique exigeait littéralement copy2, malgré son
effet erroné sur une référence readonly. Son successeur exige copyfile dans le
temporaire privé et interdit les deux copies directes vers le runtime. Les
assertions de fichier frais, hardening, immutabilité et atomicité sont conservées,
avec la régression comportementale readonly et les parcours HTTP. Le premier
résultat FAIL n'est pas rétroactivement changé.

Le banc initial a aussi exposé des refus transitoires d'ouverture de la référence
partagée entre processus. Les suites utilisant la seed réelle sont rejouées
dans une partition séquentielle déclarée. Aucun contrôle filesystem, droit,
ACL, original ou garde partagé n'est assoupli. Tous les node_ids applicables
restent exécutés ; aucun résultat n'est masqué. Cette qualification ne démontre
pas une ouverture concurrente d'une même référence externe sur cet hôte.

La couverture versionnée conserve les 426 owners précédents, les 27 exclusions
et les fonctions du garde. Le delta fixture/fitness/note est ajouté et protégé.
Le premier global, les résultats corrigés et le successeur exact restent des
preuves distinctes. La revue finale demeure requise ; aucun DDL supplémentaire,
fournisseur, credential, merge ni acceptation enseignante.


## REV4-01 : résidu de la revue distincte du 9 octobre

La revue COMMENTED 5463587979 porte sur le delta de 8746f74 ; elle ne vaut
ni approbation de merge ni revue préalable de l'ADR SQL. Son contre-exemple
est reproduit dans le service Application réel : contexte initial qualitatif,
total de deux quantités, réponse précédée de « Il y a ». Le banc utilise
une résolution institutionnelle synthétique valide et un transport doublé.

Le contrôle détecte les agrégations et les résultats numériques dans la
réponse sans dépendre de sa position ni d'un lexique d'objets. Une quantité
isolée dont l'opération n'est pas établie laisse A_DETERMINER, même si le
contexte préparé était qualitatif. Les dates contextuelles reconnues ne sont
pas assimilées à une opération. La détection reste déterministe et prudente,
sans prétendre résoudre toutes les formulations en langue naturelle.

Le même banc Application passe de 22 PASS / 12 FAIL sur le backend exact
8746f74 à 34 PASS après correction. Il couvre six formulations du total,
trois autres unités, deux réponses avec préfixe sans mot d'opération,
l'indétermination, quatre dates et une révision qualitative vers numérique.
Création, validation, revue refusée sans transport, conservation et séparation
élève/professeur conservent le statut de la version exacte. Aucun oracle
n'est inventé ; CALCULS_VERIFIES reste lié au contrôle existant du même bundle.
Trois témoins supplémentaires contrôlent que le filtre de dates ne masque
pas une équation ni une quantité de quatre chiffres : les années sont
contextuelles par leur formulation, pas par leur seule valeur.
Le premier banc avec une assertion DTO erronée reste dans les bruts privés.

Le successeur conserve les 427 propriétaires, toutes les fonctions du garde
et les 27 exclusions. Seules les empreintes de ces trois fichiers protégés
et la pin du manifeste évoluent. Le global de 8746f74 reste daté et immuable ;
les contrôles par impact du nouveau delta sont consignés séparément.
L'ADR SQL et ses annexes exactes sont disponibles dans le dossier privé existant,
sans revue préalable présumée ni changement DDL. Revue du nouveau delta,
dispositions historiques, Windows, règles GitHub et recette enseignante
gardent leurs conditions. Aucun appel fournisseur ni merge.
