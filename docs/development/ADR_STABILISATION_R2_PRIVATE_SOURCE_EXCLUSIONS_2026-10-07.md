# ADR — Exclusion des préparations privées de l'arbre source R2

## Décision relue avant correction

Le contrôle compare les 27 fichiers de PREPARATION aux pins Git 5b6f563 :
ils sont tous suivis et leurs 27 hashes d'origine concordent. Il ne s'agit
donc pas de successeurs publics distincts. L'ADR portable R3 interdit déjà
leur présence dans l'index. Le mandat R2 demande de contrôler aussi les
fichiers déjà suivis destinés à publication et de préserver leurs originaux.

Retirer uniquement ces 27 chemins de l'index, sans supprimer leurs octets
locaux. Sauvegarder et vérifier les originaux avant l'opération. Ajouter
leurs chemins exacts à .gitignore ; aucun dossier documentaire général n'est
ignoré. Les commits historiques restent immuables. Cette correction de
l'arbre courant n'efface pas leur présence dans l'ascendance publiée ;
aucune réécriture ou force-push n'est autorisée ou annoncée.

Le successeur du garde R6 contient exactement ces 27 exclusions privées,
liées au manifeste authentifié et à une liste fermée protégée par son propre
hash. Il refuse toute autre exclusion, doublon, omission ou entrée indexée.
Le delta courant conserve la suppression de ces chemins comme opération
explicite ; toutes les sources courantes restantes restent protégées, y
compris .gitignore, cet ADR et les tests. Un fichier privé ignoré préservé
localement ne devient pas une attestation privée ni une source distribuée.

## Vérifications requises

- Les octets des 27 originaux et leurs anciennes empreintes restent intacts.
- La distribution courante et le clone propre excluent les 27 chemins.
- Le vrai index refuse chacun des 27 ajouts forcés de bytes SYNTHETIQUES ;
  aucun original privé n'est copié à une fixture ou à un clone.
- Les mutations du manifeste et toute autre suppression/exclusion sont
  refusées. Les tests et résultats historiques restent distincts des
  compagnons actifs ; aucune assertion d'origine n'est neutralisée.
- Les contrôles statiques, le package propre et la suite applicable sont
  rejoués sur le nouveau SHA. Les préconditions absentes ne deviennent pas
  PASS. La revue indépendante des ADR/diff reste requise avant merge.

Aucun code applicatif, source métier, seed, grant, credential, appel
fournisseur ou contenu pédagogique n'est modifié. La qualification 68f6683
reste liée à ses octets exacts et ne qualifie pas implicitement ce successeur.
