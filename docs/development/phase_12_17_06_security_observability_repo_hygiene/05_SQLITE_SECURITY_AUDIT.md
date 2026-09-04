# Phase 12.17.6 — Audit de sécurité SQLite

## Identité et mutabilité

- Les chemins doivent être absolus, sont résolus et les collisions seed/runtime sont refusées, y compris par `samefile` lorsque les deux cibles existent.
- L'inspection du seed authentifié utilise `mode=ro&immutable=1`; les lectures runtime utilisent `mode=ro` et `PRAGMA query_only=ON`.
- Le provisionnement photographie le seed et ses sidecars avant/après et refuse toute mutation.
- Le runtime mutable active clés étrangères, délai busy de 3 s et WAL ; les lectures runtime restent non immutables afin de voir le WAL légitime.

## Migrations, SQL et intégrité

Le registre de migrations est allowlisté et authentifié par checksum. Les statements de migration proviennent exclusivement de ces artefacts internes ; transaction, ledger, postconditions, `foreign_key_check`, préservation du nombre de documents et write-probe sont présents.

Les écritures et recherches métier injectent les valeurs via paramètres `?`. Les seules interpolations SQL relevées utilisent les constantes internes `LEDGER_TABLE` et `MARKER_TABLE`. `connection.execute(statement)` n'accepte que les statements issus du registre de migrations contrôlé. Aucun identifiant ou fragment SQL fourni par l'utilisateur n'est concaténé.

`SQL_PARAMETERIZATION_STATUS = PASS`

## Backup, restauration et Git

Les backups utilisent une destination fraîche, un fichier temporaire de même répertoire, l'API SQLite backup, un hash, un manifest et une publication atomique. La restauration authentifie le backup, refuse seed/target/backup identiques et refuse une cible existante. SQLite, DB, WAL et SHM sont ignorés par Git. Aucun binaire DB runtime n'a été trouvé parmi les 126 éléments ni dans `.tmp`/`artifacts`.

## Écart

La création de répertoires et fichiers dépend des ACL/umask héritées ; aucun contrôle explicite des permissions, du propriétaire ou d'un lien symbolique/junction sur les chemins runtime, index sémantique et backup n'est appliqué juste avant ouverture/publication. Le contexte mono-utilisateur et les contrôles d'identité/atomicité réduisent l'impact, sans supprimer un risque local de redirection ou de lisibilité excessive.

`SQLITE_SAFETY_STATUS = PARTIAL_CORE_GUARDS_PASS_PERMISSION_SYMLINK_HARDENING_OPEN`
