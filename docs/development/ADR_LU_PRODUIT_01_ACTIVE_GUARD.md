# ADR — Successeur actif fermé du lot LU-PRODUIT-01

Date : 11 octobre 2026. Statut : PROPOSED — revue distincte préalable requise.

## Entrée et cause indépendante des tests

L'entrée post-fusion est `89ef3edc5f9d09e5f769862833ffa2c1b175c8fb`, arbre
`93bdaa387815f6a6654496120b40e6853629f082`. Le manifeste R6 reçu protège 452
propriétaires et 27 exclusions privées. Son SHA-256 normalisé LF est
`3d1ac5b5b44e7b920f1a19d338dbd4903df73bb92444d68723d01fcf36ffe1ee`.
Son garde authentifié conserve le digest de code
`bb813b672cb5ad9f79239735394625721a44b072820c81883b50dd7ee51115d3`.

Les corrections autorisées LU de l'Application, de l'interface, des contrôles,
des références et des exports produisent des octets successeurs. Le garde
reçu les refuse comme il doit le faire avant admission de leur delta. Un
rejeu ciblé conservé au dossier unique confirme ce refus collectif. La
mise à jour ne découle donc pas d'un objectif de résultat vert : elle suit
l'implémentation et la revue d'un périmètre de sources explicitement identifié.

## Décision proposée, avant modification des pins

1. Préserver le commit d'entrée et toutes les fabrications historiques.
   Ne modifier ni leur manifeste Git, ni les entrées historiques de la liste
   `successors`, ni les tables CP645 PRE, ni les résultats et dispositions.
2. Ajouter `tests/support/lu_product_guard_registry.json`, registre source
   public `LU-PRODUCT-GUARD-REGISTRY-1.0`, et un compagnon
   `tests/unit/test_lu_product_active_guard.py`. Ils contiennent uniquement
   identités de sources et contrôles ; aucun chemin de base privée, résultat
   généré, export, source pédagogique, reçu privé ou credential.
3. Le registre lie l'entrée post-fusion, le manifeste prédécesseur, les
   propriétaires LU exacts modifiés et ajoutés, les SHA normalisés PRE/POST,
   les décisions relues et les node_ids de couverture. Le delta inclut ce
   registre, le compagnon, le présent ADR et les deux fichiers du garde.
   Le registre ne contient pas son propre digest ; le manifeste R6 le protège
   comme tout propriétaire. Ce sens de liaison évite une identité circulaire.
4. Ajouter une seule entrée de succession
   `LU_PRODUIT_01_INTEGRATED_ACTIVE_1_0` dans le manifeste R6. Préserver les
   452 propriétaires, ajouter les nouveaux propriétaires publics du lot et
   actualiser uniquement les pins des propriétaires exacts revus. Chaque
   changement possède PRE/POST et motif. Le delta cumulatif depuis la
   baseline R6 historique reste fermé et exact ; le delta LU depuis
   `89ef3ed` est aussi vérifié séparément. Aucune exclusion de répertoire.
5. Les fonctions du garde partagé sont inchangées. Seule sa constante
   `MANIFEST_SHA256` suit le manifeste successeur ; cette constante est
   explicitement exclue du digest de code existant. `SELF_SHA256`, baseline,
   prédicats d'identité/index, scanner et liste des 27 exclusions ne changent
   pas. Aucune nouvelle autorité métier ou admission institutionnelle n'est
   conférée par un pin.
6. Toute dérive entre le snapshot relu et le gel final oblige à inventorier
   les sources supplémentaires et à obtenir leur revue distincte avant leur
   pin. Le producteur ne transforme pas l'observation de nouveaux octets
   en leur admission. Un chemin inconnu, une disparition ou un nouveau
   fichier runtime bloque la fermeture. Le gel final précède les mutations
   et la qualification combinée.

## Couverture requise

Les assertions archivistiques R3–R5 continuent d'utiliser leurs fixtures
Git exactes nommées. Leurs node_ids, tables et diagnostics privés ne changent
pas. Les compagnons actifs demeurent appliqués au code courant.

Le test `test_stabilisation_active_guard.py` paramètre déjà chaque
`guard.PATHS` : il vérifiera donc chaque propriétaire ajouté, avec octets
conformes, substitution, absence, remplacement au même chemin, substitution
de l'objet Git indexé et retrait de l'index. Les tests de substitution du
garde/manifeste restent appliqués à l'ensemble. Le scanner n'est pas remplacé
par un test borné à l'ancienne entrée.

Le nouveau compagnon vérifie l'entrée Git/arbre exacts, la conservation
intégrale des anciennes entrées et propriétaires, l'égalité du delta LU réel
avec le registre, le chaînage manifeste/registre, tous les SHA PRE/POST,
l'absence d'autorité accordée aux exclusions privées et le maintien du
digest des fonctions du garde. Ses mutations refusent un chemin inconnu,
un chemin omis et une substitution coordonnée de registre/manifeste ; les
mutations d'octets/index existantes sont conservées pour chaque propriétaire.

Le protocole ciblé comprend les six modules de gardes actifs R6, STMG,
clôture, recette, CP645 et exclusions privées, le nouveau compagnon et
les contrôles architecturaux affectés. Les assertions F2A/calibration et les
tests de frontières restent réels ; un échec sémantique après fermeture ne
peut pas être réparé en repinnant arbitrairement son oracle.

Les node_ids effectivement collectés puis exécutés, résultats bruts, Ruff,
typecheck applicable et inspection du diff sont liés au snapshot final.
Aucun PASS n'est annoncé sur la seule préparation de ce contrat. Le global
est réservé à la qualification combinée du lot après fermeture et tests
ciblés ; il n'est pas déclenché par cet ADR.

## Limites et retour arrière

Les 27 exclusions privées, D02 adopté, D03 complémentaire, attestations
satisfaites, D07 et sauvegardes conservent leur portée ; rien n'est rouvert.
Pas de données runtime ou preuves privées en Git, changement de seed/SQL,
appel fournisseur, live, credential, nouveau framework, push, merge,
release ou signature enseignante.

Avant admission du successeur, conserver les deux sources du garde reçues
et leurs identités dans Git. Le retour arrière technique du seul correctif
de garde restaure ces deux fichiers depuis l'entrée exacte ; il n'effectue
aucune opération sur une base, une production sauvegardée ou un original.
Les nouvelles corrections restent alors volontairement refusées par le
prédécesseur jusqu'à une nouvelle décision bornée. Aucun nettoyage automatique.

## Revue distincte

PENDING. Le producteur fournit cet ADR, le prototype du compagnon et le
snapshot exact au dossier unique. L'avis doit préciser les SHA relus,
couverture, limites, conditions et conclusion avant toute modification
de `r6_scope_guard.py` ou `r6_scope_manifest.json`.
