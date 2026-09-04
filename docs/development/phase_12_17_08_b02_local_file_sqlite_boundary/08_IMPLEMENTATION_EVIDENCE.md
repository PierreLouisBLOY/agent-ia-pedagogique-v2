# Phase 12.17.8-B02 — Preuve d'implémentation

| Surface | Changement B02 |
|---|---|
| Sandbox port | documentation d'implémentation externe actualisée; contrat `resolve/inspect` inchangé |
| Helper infrastructure | canonicalisation physique, reparse scan, snapshots, hash/read no-follow, permissions privées, temp et publication atomique |
| Adapter filesystem | resolver/inspector concret, MIME/signatures, lecture bornée, publication et post-inspection |
| Config SQLite | data root locale, runtime contenu, seed/runtime distincts, liens refusés |
| Connexion SQLite | identité vérifiée avant/après open, mutable owner-only |
| Lifecycle SQLite | seed permission read-only, runtime privé, temp/publication communs |
| Backup/restore | data root, collision, fresh-only, authentification, permissions et WAL/SHM |
| Index sémantique | data root locale, temp privé, remplacement contrôlé, lectures avec identité stable |
| Factories | propagation de la data root aux constructions et lectures |

```text
LOGICAL_PATH_ROLES_HARDENED = 8
ROLES = SANDBOX; SEED; RUNTIME; SEMANTIC_INDEX; BACKUP; BACKUP_MANIFEST; RESTORE; TEMP_PUBLICATION
DOMAIN_FILES_CHANGED = 0
APPLICATION_FILES_CHANGED = 0
MIGRATION_FILES_CHANGED = 0
PROVIDER_IMPLEMENTATION_FILES_CHANGED = 0
```

Les erreurs de frontière sont des codes stables et ne rendent jamais le chemin local hostile ou nominatif.
