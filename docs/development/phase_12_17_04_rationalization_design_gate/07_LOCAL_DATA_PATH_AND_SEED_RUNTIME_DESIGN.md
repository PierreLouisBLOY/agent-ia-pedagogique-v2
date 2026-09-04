# Phase 12.17.4 — Chemins locaux et cycle seed/runtime

## Décision de configuration

Le chemin Bureau observé en 12.17.3D est une preuve locale, jamais un default
produit. Aucun nom d'utilisateur ou lecteur ne doit entrer dans Git.

| Variable cible | Rôle | Default portable |
|---|---|---|
| `PROJET_V2_DATA_DIR` | racine locale non suivie | `%LOCALAPPDATA%\ProjetV2` résolu par l'OS ; erreur fermée si le dossier OS n'est pas résolvable |
| `PROJET_V2_CANONICAL_DB` | seed externe immuable | `<DATA_DIR>\seed\base_pedagogique_v2.sqlite`, avec override explicite requis pour tout autre emplacement |
| `PROJET_V2_RUNTIME_DB` | copie runtime mutable | `<DATA_DIR>\runtime\base_pedagogique_v2.runtime.sqlite` |

Sous un autre OS, le résolveur utilise le répertoire de données utilisateur de
la plateforme, jamais `~` concaténé à la main. Les anciens noms
`PEDAGOGICAL_CANONICAL_SEED_PATH` et `PEDAGOGICAL_RUNTIME_DATABASE_PATH` peuvent
être lus pendant une fenêtre de compatibilité, mais la présence simultanée de
l'ancien et du nouveau nom avec des valeurs différentes est une erreur.

Sous-répertoires dérivés : `imports/`, `exports/`, `logs/`, `backups/` et
`runtime/`. Ils sont hors dépôt et soumis aux mêmes règles de redaction.

## Invariants de chemin

- chemins absolus après résolution ;
- seed et runtime différents après `resolve()` et comparaison d'identité de
  fichier ;
- aucun symlink/junction ne peut faire converger les deux cibles ;
- runtime absente ou explicitement provisionnable ; pas d'écrasement implicite ;
- extensions et noms ne remplacent jamais le contrôle hash/structure ;
- aucun chemin local dans logs, erreurs, manifests Git ou payload provider.

## Cycle de vie

```text
1. RESOLVE_CONFIG
2. SNAPSHOT_SEED_SIDECARS_PRE
3. OPEN_SEED mode=ro + immutable=1 + query_only=1
4. VERIFY size/hash/inventory/integrity/quick/FK
5. CLOSE_SEED
6. COPY to a fresh temporary runtime path
7. ATOMICALLY_PUBLISH_RUNTIME if destination absent
8. OPEN_RUNTIME mutable; foreign_keys + busy_timeout + WAL
9. APPLY_APPROVED_MIGRATIONS to runtime only
10. VERIFY runtime ledger/constraints/FK
11. CHECKPOINT/CLOSE runtime
12. SNAPSHOT_SEED_AND_SIDECARS_POST
13. PUBLISH readiness without private paths
```

Toute différence du fichier principal seed en taille, hash ou mtime fait
échouer la gate. La copie et les migrations ne démarrent pas si l'identité
canonique n'est pas prouvée.

## Backup runtime

- checkpoint du WAL et fermeture des connexions avant backup ;
- backup vers `<DATA_DIR>/backups/` par fichier temporaire puis publication
  atomique ;
- manifeste local avec hash runtime, version de migration et horodatage ;
- restauration vers une nouvelle cible, jamais sur le seed ;
- aucun backup, WAL, SHM, base ou manifeste local dans Git.

## Sidecars WAL/SHM

```text
FINDING_ID = SQLITE_SIDECAR_ATTRIBUTION_UNDETERMINED
STATUS = OPEN_TRACEABILITY_FINDING
SEED_MAIN_FILE_MUTATION = NOT_OBSERVED
```

12.17.3D a observé en POST un WAL vide et un SHM de 32768 octets, mais aucun
snapshot PRE n'existe. Leur création ne peut donc être attribuée à cette
inspection ni à un autre processus.

Le prochain contrôle capture avant toute connexion : présence, type, taille,
hash, mtime et identité de fichier des suffixes `-wal`, `-shm` et `-journal`.
Après fermeture, il reprend le même snapshot. Sur un seed ouvert avec
`mode=ro&immutable=1`, aucune création ou modification de sidecar n'est
attendue ; toute différence bloque la gate et conserve les fichiers pour
diagnostic. Aucun sidecar n'est supprimé automatiquement.

La base runtime, elle, peut légitimement créer WAL/SHM. Ces sidecars sont
attendus uniquement à côté du runtime, checkpointés et gérés avec son cycle de
vie. Un test doit vérifier qu'ils ne sont jamais confondus avec ceux du seed.

## Contrats et tests futurs

- `SQLiteDatabasePaths` évolue vers un contrat incluant racine de données et
  invariants de séparation ;
- le loader reste pur et reçoit un mapping injecté ;
- tests unitaires des defaults OS, overrides, conflits de variables, symlinks,
  cibles existantes et redaction ;
- gate réelle sur une copie runtime fraîche, avec snapshots sidecars PRE/POST ;
- seed attendu : SHA-256
  `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`,
  taille `105553920`, inventaire `98/20/7/2`.

Aucun de ces contrôles n'est exécuté par la présente gate de design et la base
SQLite n'est pas modifiée.
