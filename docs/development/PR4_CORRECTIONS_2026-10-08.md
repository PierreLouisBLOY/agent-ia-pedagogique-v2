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

## D04 : addendum ciblé après revue SQL du 9 octobre 2026

**Version documentaire RSQL-1.0 / PROPOSED / RELECTURE CIBLÉE ATTENDUE.**
Rattachement source : `38768829a50d02d4ed1808d5f84fd38024ed347e`.
La revue [COMMENTED 5464372510](https://github.com/PierreLouisBLOY/agent-ia-pedagogique-v2/pull/4#pullrequestreview-5464372510)
a reçu l'ADR SQL exact, SHA-256
`f95537a767cd8390f0ea7a98e9b30d92cbe5a01f9202955d964d4868f5fdb583`,
et demande RSQL-01, RSQL-02 et RSQL-03. La revue préalable a donc été
effectuée avec verdict REQUEST_CHANGES ; elle n'est plus une pièce manquante.
Le présent addendum répond uniquement à ces points. Il ne vaut pas approbation
par le producteur ni permission d'appliquer le DDL.

L'accord propriétaire de portée reste acquis sur la fiche exacte SHA-256
`5eb33f27e03c570482fb4f8b1f15b40591be21fcbc66edfcd66d269168d5fe5a`.
L'ADR initial et ses octets sont conservés hors Git. Les chemins et identités
privés restent ceux de cette pièce et de son reçu de décision ; aucune cible
supplémentaire, sélection par le lanceur ou migration globale 001/002.

### RSQL-01 / SQL04 : mémoire de publication append-only

Le registre proposé `_pr4_published_version_seal` comporte exactement une
colonne `resource_version_id`, TEXT, NOT NULL, clé primaire, référence exacte
à `resource_version.id`, avec suppression de la version référencée interdite,
sans cascade ni SET NULL. Aucun champ mutable ni commande « unseal ».
Son alimentation initiale est exclusivement l'ensemble des versions PUBLISHED
authentifiées, dans la transaction d'installation ; l'alimentation future
suit l'insertion d'une version PUBLISHED ou son passage effectif à PUBLISHED.
Une identité PUBLISHED NULL, dupliquée ou incohérente provoque STOP avant
migration ; aucun élargissement de la correction de clé SQL06.

Des gardes supplémentaires du registre refusent tout DELETE et tout UPDATE,
même une réaffectation, et tout INSERT en collision avec une identité déjà
scellée. Le refus est explicite avant la résolution d'un conflit : REPLACE,
INSERT OR REPLACE, IGNORE, UPSERT et UPDATE OR REPLACE doivent être examinés
et testés, sans dépendre de l'exécution des seuls triggers de suppression
implicite de SQLite. L'idempotence de migration vient du manifeste déjà
appliqué à checksum identique, pas d'une réinsertion tolérée des sceaux.

Les gardes de resource_version refusent aussi un INSERT visant une identité
déjà scellée et un UPDATE qui substitue une identité scellée en destination,
avant un éventuel remplacement. DELETE d'une version scellée demeure refusé.
Aucun chemin couvert de remplacement ou de conflit ne peut effacer le sceau,
modifier les anciens octets ou le réaffecter à une autre version.

Liste de colonnes observée dans la pièce Application 28A, à réauthentifier
intégralement avant application : `id`, `resource_id`, `version_number`,
`previous_version_id`, `title`, `summary`, `body`, `lifecycle_status`,
`validation_status`, `published_at`, `valid_from`, `valid_to`,
`created_at`, `created_by_actor_id`. La définition, les types, contraintes,
defaults, colonnes cachées/générées et tous les triggers concernés sont
figés dans le manifeste exact. Une colonne ou définition supplémentaire,
absente ou inattendue entraîne STOP ; pas de projection partielle silencieuse.

Toute colonne hors lifecycle_status est comparée avec une égalité sensible
à NULL, équivalente à IS/IS NOT, sans != nullable ni COALESCE confondant des
valeurs. Le seul changement autorisé pour une version scellée est
PUBLISHED → ARCHIVED, toutes les autres valeurs inchangées. Un UPDATE
strictement sans changement peut rester admis ; ARCHIVED reste scellé.
Les triggers préexistants sont conservés et leur graphe d'effets est relu.
Si l'archivage modifie automatiquement un autre champ, STOP : aucun trigger
n'est supprimé et aucune exception implicite n'est ajoutée à l'immutabilité.

Contrôles prévus, **non exécutés** : publication initiale/future, nouvelle
version enfant et archivage strict licites ; DELETE/UPDATE/réaffectation du
sceau ; collisions REPLACE/UPSERT/IGNORE du registre et de la version,
puis tentative de mutation ; chaque colonne et NULL↔valeur ; changement
conjoint statut/contenu ; démotion et mutation après archivage ; chemins
de cascade pertinents ; retrait ou altération de chaque garde et du registre.
Chaque refus doit conserver les octets et sceaux concernés.

Un administrateur pouvant modifier le schéma ou le contexte de connexion
reste un pouvoir distinct : le manifeste et le préflight détectent les DDL
retirés/substitués et les réglages inattendus ; ils ne rendent pas impossible
une intervention administrateur. Les anciennes démotions non identifiables
avant installation restent NON COUVERTES.

### RSQL-02 / SQL05 : une requête, un ensemble éligible, un état de lecture

Le contrat fermé retourne en une seule requête de lecture le diagnostic et
l'éventuelle version exacte à partir du même ensemble éligible E et de la
même règle de maximalité. Il n'effectue pas « lire le diagnostic, puis relire
la candidate » dans deux états indépendants. Zéro candidate donne ABSENT ;
une seule candidate maximale donne EXACT avec son identité ; plusieurs
candidates maximales donnent AMBIGUOUS_CURRENT_VERSION sans version choisie.
Les libellés de diagnostic sont ceux du contrat fermé à relire.

Le préflight Application en lecture seule doit relever le texte exact de
v_current_resource_version, ses colonnes, tables/triggers dépendants,
prédicats d'éligibilité, expression de maximalité et comportement NULL.
Ces octets et empreintes sont figés avant de construire le diff. Ce relevé
complet n'est pas prétendu disponible dans 28A, qui inventorie des tables.
Aucun nouveau filtre de lifecycle_status, validation_status, tri par id,
COALESCE de date ou critère d'insertion n'est déduit du seul nom de la vue.
Définition absente/inattendue ou sémantique non authentifiée : STOP.

La vue diagnostique proposée et le consommateur utilisent exactement E ;
la vue courante ne rend aucune candidate pour une collision. Le diff concret
des vues et du contrat doit encore être relu avant application. La sélection
explicite d'une version historique autorisée est un parcours distinct ;
une ambiguïté n'est jamais résolue automatiquement par ce parcours.

Contrôles prévus, **non exécutés** : zéro/une/plusieurs candidates, maxima
égaux, permutations d'insertion, statuts éligibles/inéligibles et valeurs
NULL selon la définition figée ; substitutions du diagnostic ; version
historique explicite. Un writer concurrent entre deux appels indépendants
peut changer la réponse ultérieure, mais ne doit pas mélanger diagnostic et
version dans une même réponse. Si une implémentation introduit plusieurs
lectures, elle dévie de cette stratégie et doit obtenir une relecture de
son snapshot/transaction avant application.

### RSQL-03 : copie et sauvegarde avant une publication fraîche unique

Stratégie retenue pour la relecture : la cible finale autorisée reste absente
jusqu'à l'unique appel de publication fraîche. Aucun fichier n'est supprimé
pour simuler cette absence et atomic_publish_fresh n'est pas assoupli.

1. Authentifier source, schéma complet, identités filesystem et état cohérent
   des sidecars par Application. Les pins source et schéma restent ceux
   de l'ADR initial. Refuser alias, hardlinks, redirections et cible existante.
2. Préparer la copie initiale dans le temporaire privé sécurisé du mécanisme
   existant, sous le seul périmètre admis, **pas à la cible finale**.
   Vérifier bytes, taille, hash et schéma égaux à la source authentifiée.
3. Avant migration, sauvegarder cet état initial dans le backup déjà prévu,
   absent et distinct de source/temporaire/cible. Vérifier backup et
   restauration vers le chemin de contrôle déjà prévu, jamais vers l'original.
   Pas de nouvel emplacement hors de la racine privée admise.
4. Appliquer le successeur fermé dans ce temporaire, en transaction, après
   les préconditions et la relecture des DDL/contrats exacts. Vérifier
   invariants, contenu légitime, schéma, FK, intégrité et reçu. Échec :
   rollback, reçu conservé, aucune publication.
5. Revalider identités et absence de la cible ; publier **une seule fois**
   le temporaire vérifié vers la cible finale fraîche via le mécanisme
   sécurisé existant. Une collision concurrente provoque STOP sans écrasement.
   Recalculer les empreintes finales et l'immutabilité source/backup.
6. Démontrer le retour arrière prévu via Application vers le contrôle distinct.
   Après publication, un remplacement de la seule copie est une opération
   distincte à identité exacte, jamais un second atomic_publish_fresh.
   Son contrat sûr et ses preuves doivent être établis avant son utilisation.
   Sans ce contrat, STOP du rollback opérationnel, conserver le successeur
   et la sauvegarde ; aucun effacement ou remplacement improvisé.

Le manifeste distingue source, copie initiale temporaire, backup, restauration
de contrôle, successeur temporaire et cible publiée avec leurs identités et
empreintes avant/après. Une sauvegarde du même dossier n'est pas une preuve
de sauvegarde indépendante du disque. Aucun changement du lanceur ou de
configuration utilisateur et aucun original modifié.

### Conditions et statuts conservés

Les contrôles ci-dessus sont une spécification à relire, pas des PASS
d'implémentation. SQL01/02/03/06 gardent leurs orientations ciblées ;
SQL06 reste limité à notion.id, SQL07 à la garantie Application du bundle
exact, sans réparation de jointures relationnelles ni « 7/7 SQL corrigés ».

L'avis ciblé favorable à REV4-01 et les avis REV4-02/03 sont consignés.
La revue documentaire des treize FAIL et des huit ADR est réalisée dans
sa couverture déclarée ; elle ne vaut pas revue exhaustive des 274 chemins.
Seules les trois dispositions OPEN_DEFERRED PR #3 demeurent acquises.
Les dix autres restent proposées avec une matrice exigence/contrat/preuve/
limite/décision exacte dans le dossier privé ; aucun brut FAIL/SKIP réécrit.

L'erratum bénéficie d'un avis favorable documentaire : premier ajout observé
des 27 préparations à 5bdd49be, distinct du pin map 5b6f563, dans la chaîne
examinée. Les objets historiques et bundles privés sont conservés, sans purge.
R1 et Word Q18 restent datés ; Windows, D07, revue complète, recette enseignante
et décision de merge gardent leurs conditions. Deux gates live fermées,
aucun fournisseur, credential, DDL ou merge.

### D02 : compagnons portables du contrat courant, à relire

Le banc actif conserve les assertions historiques inchangées et ajoute six
témoins distincts dans test_stabilisation_active_guard.py : trois états Git
réels untracked/staged/committed et trois retraits contracts.py/transport.py/both.
La fixture ne contient que les 427 propriétaires publics et les deux fichiers
de garde/manifeste. Elle n'importe aucun original privé ni ancien runtime.
L'inventaire courant, le véritable index et les blobs du HEAD synthétique sont
contrôlés selon l'état. Les propriétaires publics des frontières historiques
restent inclus ; cette preuve ne reconstitue pas l'inventaire privé ancien.

La vérification privée conserve explicitement NOT_PERFORMED_ABSENT ; le mode
exigeant une attestation complète refuse l'absence. Les retraits de modules
contrôlent séparément le travail valide/index substitué et le travail retiré/
index valide, puis l'absence du véritable index, pour les deux modules ensemble
et chacun. Les mutations sont limitées aux fixtures et restaurées.

Cette succession de tests relève de la séparation historique/actif des ADR
déjà lus et de l'avis documentaire 5464372510. Elle reste à relire sur ses
bytes et preuves exacts ; elle ne dispose d'aucune approbation automatique.
Elle ne modifie ni les treize FAIL, ni les trois OPEN_DEFERRED acquis, ni les
dix décisions supplémentaires encore proposées. Le résultat des tests est
consigné dans le dossier privé, sans addition au global historique.
## A06 : revue reçue, adoption D02 et préflight préparatoire du 9 octobre 2026

La [revue COMMENTED 5472372189](https://github.com/PierreLouisBLOY/agent-ia-pedagogique-v2/pull/4#pullrequestreview-5472372189)
est vérifiée sur f6fe3e409a584d8d851e7d752656bede8bda1f20. L'addendum RSQL-1.0
reçoit FAVOURABLE_DESIGN_REVIEW : les trois demandes de conception sont satisfaites.
La lecture distincte du successeur MD13 et de ses consommateurs reçoit un avis
favorable ciblé. Les six compagnons portables reçoivent un avis favorable dans leur
portée. Aucun de ces avis ne vaut nouveau PASS applicatif ni revue universelle.

Le propriétaire a adopté explicitement les dix propositions exactes D02-A à D02-E
de la matrice16, SHA-256
41f129ed41d46ef2bec4ccc16f74b46d12054b552a421ed61ad25e6ccd5c24a9.
Les trois dispositions antérieures restent acquises. Les limites par ligne, les
FAIL/SKIP historiques et les attestations privées distinctes sont conservés.
Ce constat ne vaut pas merge ni clôture automatique d'une précondition privée.

L'inspection préparatoire runtime_schema_inspection reste dans local_provisioning :
use case via port, inbound Application propriétaire, composition explicite, adaptateur
de persistance en lecture seule. Aucune route HTTP, outil agent, SQL ou path libre.
Elle relève tous les objets du schéma, table_xinfo/FK/index et les fichiers du runtime
authentifié. Le contrat de migration demeure distinct et non implémenté.
L'inspection institutionnelle existante et son contrat restent inchangés.

Le lecteur immutable n'interprète pas de WAL ; il refuse un WAL non vide, tout
journal et un SHM incohérent. Un WAL vide accompagné d'un SHM de32768 octets peut
être conservé pendant une lecture des octets main authentifiés. Le jeu complet est
contrôlé avant/après. Cela ne constitue pas une preuve de quiescence des writers,
une permission de copie ni une mutation du mode SQLite natif.

Le préflight réel par Application a relevé 121 tables, 157 index dont autoindex,
7 triggers et 11 vues ; intégrité/quick_check=ok et0 violation FK. Les59 définitions
du relevé historique concordent. Source et sidecars inchangés ; cible/backup absents.
Un premier refus strict de sidecars est conservé avec ses preuves et sa résolution
limitée à la lecture immutable ; aucun fichier n'a été supprimé pour le contourner.

SQL05 : E conserve exactement PUBLISHED et les bornes valid_from/valid_to avec
CURRENT_TIMESTAMP. La maximalité reste NOT EXISTS d'un created_at strictement
supérieur dans le même E ; pas de filtre de validation, tri/id ou MAX nouveau.
created_at est TEXT NOT NULL dans le schéma authentifié. Le diff privé préparé
sépare cardinalité/diagnostic et ne sélectionne une version que pour EXACT ;
une seule requête fermée donnera ABSENT/EXACT/AMBIGUOUS_CURRENT_VERSION.

Le DDL, le diff des vues, le contrat de maintenance fermé, les préconditions et
les contrôles de mutation sont préparés pour la lecture d'implémentation expressément
requise par ADR40/RSQL-1.0. Ils ne sont ni exécutés ni enregistrés dans001/002.
L'ancienne empreinte de schéma est conservée ; la nouvelle sérialisation exhaustive
est explicite et leur liaison doit être relue, sans ancien pin changé silencieusement.
Aucune copie, sauvegarde, restauration, migration ou publication SQL réalisée.
SQL06 reste notion.id ; SQL07 demeure une garantie Application distincte du DDL.

Les20 PASS de l'inspection synthétique/frontières sont un banc différent des anciens
11/5/211. Le global7988/13/0/5 reste daté8746f74. R1, Word technique, REV4 et erratum
sont conservés. Revue du diff final, Windows, D07 et recette enseignante demeurent
distincts ; gates live fermées et aucun merge.

## A06 : successeur SQL fermé après revue concrète (10 octobre 2026)

La revue COMMENTED5475808797, sur9446728d433561354f4d15aaf8732c9cc18bac33,
est reçue et vérifiée : FAVOURABLE_TARGETED_SQL_REVIEW_WITH_EXECUTION_PRECONDITIONS.
Le DDL15, la requête17, les préconditions18 et la convention de digest nommée ont
un avis favorable dans leur portée. Les88 probes de revue restent une preuve
distincte en mémoire/Linux/Python3.13, sans addition aux compteurs du projet.
Les dix dispositions D02 et trois antérieures restent acquises dans leurs limites.

Le chemin sql_successor appartient à local_provisioning : use cases, contrats et
port typés, inbound Application propriétaire, composition explicite et persistence.
La requête d'application ne contient que les trois identités de plan/décision/revue.
Aucun SQL ou path libre, outil agent, route HTTP, activation du lanceur, dépendance
ou extension du registre001/002. Les trois textes SQL exacts sont épinglés par SHA.
L'ancien pin de schéma reste distinct du digest actuel ; le binding porte le relevé
complet, colonnes/FK/index/flags et identités/hash de main et de tous ses sidecars.

Le cycle impose : stabilité Windows avant effet, copie initiale exacte dans un
temporaire privé, backup frais conservé et restauration de contrôle exacte avant DDL,
transaction unique, préconditions à zéro, objets existants inchangés sauf SQL05,
empreintes multiensembles/comptes des tables métier, intégrité/FK et sceaux exacts,
puis publication fraîche unique. Reprise seulement sur binding/reçu/hashes/postschéma
et contenu exacts, sans réécriture. Une collision ou histoire partielle est conservée.

Stabilité : OPEN_EXISTING de main et des sidecars présents sans SHARE_WRITE ni
SHARE_DELETE, chaînes de parents épinglées sans SHARE_DELETE. Un writer déjà présent
ou une mapping écrivable refuse l'acquisition ; les writers futurs sont refusés.
Le source reste lu immutable, mais cette option ne tient pas lieu de verrou.
Les fichiers absents, journal ou nouveaux sidecars sont revérifiés ; aucun sidecar,
mode source, permission ou original n'est modifié pour satisfaire les conditions.
Les destinations de copie sont ouvertes sans partage, sans suivre de reparse point,
avec identité physique/fichier régulier/lien unique vérifiés avant troncature.
La documentation primaire de cette règle de partage est
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew.

SQL05 utilise la requête unique revue : ABSENT/EXACT/AMBIGUOUS_CURRENT_VERSION ;
version seulement pour EXACT. Eligibilité, bornes temporelles et maximalité NOT EXISTS
sont conservées, sans sélection arbitraire, filtre de validation ou fallback.
SQL06 reste notion.id. SQL07 conserve sa garantie Application, aucune réparation DDL.

Les fixtures reprennent treize tables authentifiées et leurs contraintes utiles,
avec des lignes exclusivement synthétiques. Les mutations de chacune des dix-huit
nouvelles gardes ont des contre-exemples ; les anciennes protections redondantes
sont isolées explicitement dans ces seuls tests, jamais supprimées en production.
Le banc comprend publication/archivage, toutes colonnes, REPLACE/IGNORE/UPSERT,
refus de préconditions, rollback transactionnel, diagnostics temporels, processus
Windows concurrents, hardlink/substitution, collision, idempotence et altération du
binding complet. Chaque résultat reste lié à son XML et à ses octets datés.

Retour arrière après publication : STOP_PENDING_SAFE_REPLACEMENT_REVIEW.
Le contrôle de restauration avant DDL est distinct. Aucun remplacement n'est exécuté :
la primitive partagée vérifie puis remplace par path et ne prouve pas l'exclusion d'une
substitution dans cet intervalle. Son éventuel successeur sûr et sa revue restent
nécessaires avant ce seul effet. La primitive partagée n'est pas assouplie/modifiée.

Les reçus d'exécution, l'application réelle éventuelle sur la seule copie D autorisée
et la revue finale du code sont distincts de la revue des SQL proposés.
Le dernier global7988/13/0/5 reste rattaché à8746f74, non au successeur.
Deux SKIP Windows, gates live fermées, D07, attestations privées applicables,
sauvegarde indépendante du disque et recette enseignante gardent leurs conditions.
Aucun nouveau fournisseur, COUNT, credential, changement de sécurité ou merge.


### Correction ordinaire de reprise : reçu et cible substitués ensemble

Le checkpoint baedbc2 conserve l'implémentation initiale et ses151/38 résultats
distincts. Deux contre-exemples réellement exécutés ont ensuite révélé qu'une
substitution coordonnée du reçu et de la cible pouvait faire accepter une reprise.
Ces2 FAIL ciblés sont conservés. La correction compare désormais les objets
postérieurs au DDL exact relu, les empreintes métier au backup lui-même épinglé
par le SHA du source, et le sceau à l'ensemble exact des publications initiales.
Les hashes inscrits dans le reçu ne constituent plus leur propre référence.
Le troisième cas retire un sceau puis réinstalle sa garde avant de falsifier le
reçu ; il doit aussi être refusé. Aucun DDL proposé, source original, registre
global, guard partagé ou périmètre d'autorisation n'est changé.
