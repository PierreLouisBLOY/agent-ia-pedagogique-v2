# ADR — Fixtures historiques et contrôle actif de stabilisation

Statut : REVUE TECHNIQUE LOCALE EFFECTUÉE AVANT IMPLÉMENTATION.
Mandat : stabilisation du 7 octobre 2026, checkpoint 85caccd.

## Cause indépendante du résultat des tests

Les tables PRE/POST R3–R5 décrivent des fabrications fermées antérieures à R6.
Leurs fixtures copient pourtant des fichiers du HEAD courant : frontend,
sauvegarde, routes et export ont ensuite évolué sous des décisions explicites.
Exiger les bytes R3–R5 sur ces copies récentes ne teste ni la fabrication
historique ni le contrat actif. Les gardes support R3–R5 n'ont pas changé entre
5bdd49be35149a7134e866fa4473926b65a5ee69 et 85caccd.

## Décision bornée

1. Les tests d'identité, d'inventaire et de mutation des fabrications R3–R5
   reçoivent une fixture code depuis le commit exact
   5b6f5630c54706bde7cc2afb72bd032efd289b9c, avec arbre
   Git identifié. Le code candidat de la fixture n'est jamais importé/exécuté.
   Les assertions Git des contrôleurs locator/CAP/serializer présentent une
   contradiction indépendante : leur chaîne exige les propriétaires R5 mais
   leur inventaire local refuse les ajouts R4/R5 déjà admis. Ni f4ba498 ni
   5b6f563 ne peut satisfaire simultanément ces deux contraintes.
   La fixture nommée utilise donc un successeur de contrôle Git versionné :
   inventaire global R3–R5 existant, toutes les identités/sémantiques anciennes
   et égalité de chaque index avec son propriétaire authentifié. Aucun chemin
   inconnu n'est soustrait. Ce successeur est utilisé uniquement par les
   assertions archivistiques nommées ; les fichiers des anciens gardes et
   leurs tables restent inchangés. Contrôle actif R6 et mutations restent requis.
   Les assertions, tables, seuils et oracles historiques restent inchangés.
2. Les 27 préparations déclarées privées ne sont pas extraites de Git dans cette
   fixture. Leur absence est NOT_PERFORMED_ABSENT et non une attestation PASS.
   L'index synthétique de la fixture ne les contient pas. Cette disposition ne
   modifie pas le HEAD produit ni les trois FAIL documentaires originaux.
3. Chaque fichier actif des mêmes fabrications reste couvert : identité exacte
   actuelle via le successeur R6 déjà livré lorsque modifié depuis 5bdd49be,
   identité historique lorsqu'il est inchangé. La fabrication R5 précède le
   provisioning CP645 : 5bdd49be reste la baseline du successeur actif R6,
   pas celle de l'inventaire historique fermé R5. Des contrôles positifs et de
   mutation couvrent travail, index substitué, fichier manquant et remplacement.
   Le delta Git réel, y compris les nouvelles fixtures, est vérifié sans exemption
   globale des tests ou des répertoires. Manifeste et garde sont authentifiés.
4. Les tests de comportement exécutent toujours l'Application actuelle. La
   fixture historique s'applique uniquement aux contrôles archivistiques nommés.
   Les node_id existants sont conservés, aucun skip/xfail/filtrage n'est ajouté.
5. Les changements des propriétaires du correctif entrent dans un successeur
   explicite du manifeste R6 ; anciennes empreintes et preuves restent en Git.

## Autres causes internes

- Le matériau locator est un calcul local pur, mais son `while` déclenche
  l'interdit architectural général des boucles fournisseur. Utiliser une
  itération finie des occurrences exactes, sans changer les règles d'ancrage,
  de chevauchement, d'ordre et de non-réutilisation ; tests des mêmes règles.
- Le successeur review metadata approuvé le 5 octobre consomme le contrat
  ContentThreatSignalCode dans le même owner review que son prédécesseur :
  l'inventaire architectural doit nommer cet owner exact, avec refus d'autres
  consommateurs et import interdit dans les zones protégées.
- Le module local_provisioning livré nécessite une décision canonique
  explicite sur la liste des modules : ne pas ajouter ce nom aveuglément à
  l'inventaire des treize modules pédagogiques. Examiner son ADR/disposition
  existante avant de corriger ce contrôle.
- La calibration figée doit consulter le review adapter de sa fabrication
  historique, tandis que son successeur actuel et sa mutation restent testés.

## Limites et preuves requises

Aucun changement de frontière Application, de contrat pédagogique ou d'autorité.
Aucun appel fournisseur, credential, seed, migration réelle ou nouvelle fonction
visuelle. Les preuves privées absentes restent des préconditions ouvertes ; pas
de reconstruction à partir des rapports ni de faux PASS.

Le rejeu global 85caccd reste immuable. Registre pré/post par node_id, tests de
mutation du successeur actif, Ruff/mypy/compileall et inspection du diff sont
requis avant qualification. Un merge reste interdit tant que ses conditions ne
sont pas satisfaites.

## Revue technique du 7 octobre

Les décisions R3 portable, R4 et R5 autorisent déjà les vues historiques
authentifiées après vérification de la source successeure exacte. La correction
des fixtures conserve ce mécanisme, les contrôleurs et leurs tables. La revue
exige le contrôle actif supplémentaire décrit au point 3, avant tout statut
résolu. Elle ne reconnaît aucune attestation privée par la réussite de ces tests.
Le changement d'algorithme locator préserve le contrat approuvé de matérialisation
déterministe ; le scanner architectural n'est pas assoupli. L'owner review ajouté
est celui de l'ADR propriétaire déjà adoptée le 5 octobre. Les contrôles de liste
des modules et les décisions canoniques manquantes restent ouverts.

Cette revue technique ne vaut ni revue humaine de PR ni recette pédagogique.

## Disposition de local_provisioning avant correction du contrôle

Le mandat R5 APPLICATION_PROVISIONING_BOUNDARY_AND_CLOSE transmis puis exécuté
par le propriétaire autorise un mini-module opérationnel en l'absence de contexte
approprié. Les sept décisions R5 étaient approuvées. local_provisioning possède
une Application et des ports, sans SQL, infrastructure, fournisseur, HTTP ou outil
agent ; les tests existants en vérifient la frontière. work_orchestration traite
les productions pédagogiques et ne porte pas l'administration locale des bases.
Les treize modules pédagogiques Phase 6 restent inchangés. L'inventaire distingue
un ensemble opérationnel fermé contenant uniquement local_provisioning, avec
ses sous-frontières minimales. Aucun nouveau module n'est créé par ce correctif.
Les mutations de nom inconnu et suppression d'un owner sont refusées ; ce
successeur de fixture et son renvoi documentaire sont contrôlés par R6.

Complément de revue avant implémentation : le successeur Git de fixture
authentifie l'ensemble fermé avant tout contrôle d'index. Il remplace les
entrées `assert_git_state` contradictoires, pas les prédicats d'identité ni
les oracles sémantiques. Tests positifs, index substitué, chemin inconnu et
substitution de source doivent prouver le refus. Les échecs des tentatives
de localisation précédentes restent dans les résultats bruts.
