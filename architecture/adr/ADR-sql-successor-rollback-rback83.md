# RBACK-83F-1.3 : retour arriere ferme du successeur SQL

## Decision et revue prealable

Continuation A06 autorisee depuis 83f7a1c. La passe distincte autorisee par le
proprietaire a relu ADR40/RSQL inchanges, contrat 1.0 et amendements 1.1/1.2/1.3
avant implementation. Avis FAVOURABLE conception exact, 10 octobre 2026,
identite /root/rback_prior_review; preuve privee SHA-256
c7dd63273e06436d9f64c37d170ce580f07098c890f9c02cb41fb0ef9c86b754.
Addendum exact 1.3 : b1b7fdebbe4a0fa0e4563b637cf050b50db219b8b606d99d9215a29def53bdb9.
Cet avis ne qualifie pas le code ni une operation sur la copie proprietaire.

## Portee et objets

Use case explicite dans local_provisioning, inbound Application de confiance,
factory sans enregistrement dans HTTP/agent/lanceur. Aucun changement du DDL,
des migrations globales, de SQL05/07, des bases originales ni du scanner partage.
L'ancien APPLIED, son backup et son lien initial restent intacts.

Le binding externe ferme contient plan, decision, revue et operation; binding
SQL original complet; empreinte APPLIED, nom initial conserve; identites device/
inode/taille/hash du successeur et du backup. Aucun SQL, path libre ou force
dans la requete. La factory borne la racine distincte des originaux et du depot.

prepare cree le lock de maintenance et un namespace derive du hash d'operation,
une copie independante du backup et un alias de lecture. Sous handles et lecteur
existant, il verifie bytes, schema, metadonnees, integrite, FK et lignes de l'ancien
successeur contre le backup authentifie. L'intention exclusive est flush/fsync
avant retour de son hash au demandeur de confiance. execute/reprise exigent ce
hash externe : jamais appris de la cible ou du recu courant. Crash avant remise
du hash = refus de reprise automatique.

Le lock conserve est lie au binding+operation et ouvre avec partage zero, sans
reecriture. Identite physique du lock attestee dans l'intention. Migration/reuse/
resolution refusent l'histoire rollback sous ce meme lock; un reader deja sous
pins fait refuser DELETE avant retrait. Aucun namespace efface pour reprendre.

Chaque paire a deux noms : final/archive READ|DELETE et lien initial READ;
staging/final restauration READ|DELETE et alias READ. Tous SHARE_READ seulement,
ancetres sans SHARE_DELETE. La lecture Application passe par l'alias READ; les
bytes du handle rename se lisent par son fd. Source/backup ont chacun un lien,
restauration physiquement distincte. Comptages/identites/hashes/sidecars verifies
avant/apres les transitions. Aucun pin relache pour contourner Windows.

Deux moves par handle avec remplacement interdit : final vers archive fraiche,
puis staging vers final frais. Controle final, nouveau recu exclusif flush/fsync.
Aucun ancien recu reecrit, aucun occupant ecrase, aucun sidecar efface.

## Etats et retour arriere de cette intervention

Initial+staging : retrait une fois. Archive+staging et final absent : restauration
une fois. Archive+final restaure sans recu : verification et recu uniquement.
Archive+final restaure+recu exact : ALREADY_ROLLED_BACK sans nouvelle ecriture.
Toute autre histoire : STOP/refus, conservation des fichiers et preuves pour
une disposition distincte. Pas de remigration implicite ni de nettoyage de preuve.
Pour revenir sur le code, restaurer le commit precedent dans une nouvelle
candidate; ne pas rejouer ni supprimer l'histoire de fichiers.

## Controles et limites

Banc synthétique natif requis : nominal/reouverture/repetition, collisions
archive/final, substitution egale/different inode, liens inattendus, writer,
arrets reels aux deux transitions et reprise dans autre processus, falsification
coordonnee APPLIED/cible, backup/archive modifies, autre binding, intention
absente/tronquee/attestation differente, recu final faux, contention interprocess,
sidecars de tous les noms pertinents, refus remigration/reuse/resolution.
Chaque PASS doit avoir ete execute; les PRE sont conserves.

Limites : intervalle sans nom final (pas d'echange atomique), alias transitoire
cree puis supprime entre points d'observation non exclu, panne electrique non
qualifiee. Les pins ne prouvent pas l'immuabilite apres fermeture des handles.
Aucune ACL/privilege/securite/volume/TxF supplementaire. La sauvegarde independante
du disque, D07, les deux SKIP symlink et la recette enseignante restent distincts.
Les gates live demeurent fermees. Aucun merge/release presume.
