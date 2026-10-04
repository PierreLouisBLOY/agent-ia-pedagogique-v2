# État de la continuation P0 du 4 octobre 2026

Le raccordement applicatif et le correctif de démarrage sont versionnés au
commit `22742acd2c963f57f0938ed0ba8b56676dc78149`, successeur de `48ab2e98…`.
Les références LOT 1, LOT 2 et leurs preuves restent conservées.

## Preuves obtenues avant empaquetage

- 27 tests HTTP passent : les 24 cellules, la révision, la sauvegarde des parents
  et enfants, la réouverture après arrêt et les exports ; autorisation absente,
  refusée et dispatch incertain sont également exercés.
- Les 24 cellules ont été parcourues depuis le formulaire dans Chrome. Le
  transport synthétique est déclaré et injecté uniquement au port externe du
  harnais. Il n'est jamais lié par le lanceur normal.
- La composition normale prépare un contexte BTS CG deuxième année avec une
  référence authentifiée, puis refuse la génération faute d'autorisation.
- Trois téléchargements navigateur du harnais concordent octet pour octet avec
  les exports de la version rouverte par Application. Ces documents ne sont pas
  les documents Boréal admis.
- Les contrôles de garde stabilisés passent : propriétaires exacts, substitutions
  de chaque nouveau composant, pièce manquante et propriétaire supplémentaire.

Un premier rejeu global a eu 318 PASS et 34 FAIL de garde : le manifeste a été
actualisé pendant ce rejeu. Il est conservé comme essai invalidé pour la
qualification. Les 36 tests de garde ont ensuite été rejoués avec succès sur un
état stabilisé. La qualification de la copie propre et ses résultats bruts
doivent être consultés dans le paquet privé de cette continuation ; ce document
ne déclare aucun résultat non encore exécuté.

## Démarrage et historique

La version d'entrée a reproduit un blocage d'initialisation navigateur. Trois
essais contrôlés avec une connexion spéculative inactive et six requêtes ont
chacun obtenu 1 HTTP 200 et 5 échecs de connexion avec une file d'acceptation de
taille 1. Le successeur conserve le serveur séquentiel, augmente cette file
bornée à 16 et passe ce test. Les requêtes initiales et leur lecture de corps
sont bornées côté navigateur à dix secondes, sans retry automatique de mutation.
Les campagnes et traces précisent la portée réelle de la démonstration ; aucune
absence universelle d'intermittence n'est prétendue.

Les cinq assertions historiques ne sont ni modifiées, ni désactivées. Leur
analyse conserve les listes PRE/POST de fichiers inattendus, les pins R4 exacts,
la comparaison du composant de retrieval et les assertions non atteintes après
un premier échec. Le changement de ce composant depuis la baseline de recherche
concerne uniquement la taille et le SHA de la seed, au commit R5 `a03e79e…`.
La succession active est couverte par les pins R6 et par les tests fonctionnels
et de mutation ; elle ne transforme pas les résultats historiques en PASS.

## Boréal

Le paquet informatif de réserve V3 rapporte une recette partielle et des avis
favorables sur le fond, conservés comme avis du propriétaire. L'utilisation en
classe des trois documents V3 en l'état n'est pas acceptée : fioritures, mise en
page et template restent ouverts. L'admission du cas fictif guidé demeure acquise.
Les octets V3 et leurs preuves Word/réception précédentes sont conservés.
Aucune signature, acceptation finale, promotion ou génération réelle des
24 cellules n'est présumée.
