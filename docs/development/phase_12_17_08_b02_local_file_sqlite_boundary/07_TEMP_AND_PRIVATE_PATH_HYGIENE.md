# Phase 12.17.8-B02 — Temp et permissions privées

Les répertoires et fichiers créés par la frontière locale sont durcis pour l'owner courant : mode `0700/0600` sur POSIX et DACL Windows protégée `OWNER RIGHTS / Full Access` sans héritage. Le seed externe est seulement inspecté; sa DACL n'est jamais modifiée.

Les temporaires runtime, backup, manifest, restauration, index et sandbox sont créés par `mkstemp` dans le répertoire de destination validé, donc sur le même volume que la publication. Leur nom est aléatoire, leur ACL est durcie avant contenu sensible et leur nettoyage est borné au chemin frais connu.

Tous les runs pytest B02 utilisent `--basetemp` sous le temp système et `PYTHONDONTWRITEBYTECODE=1`; compileall utilise `PYTHONPYCACHEPREFIX` sous le temp système. Aucun `.tmp`, `.building`, SQLite, WAL, SHM ou cache B02 n'est créé dans le dépôt.

```text
PRIVATE_DIRECTORY_POLICY = OWNER_ONLY
PRIVATE_FILE_POLICY = OWNER_ONLY
TEMP_SAME_VOLUME = PASS
TEMP_OUTSIDE_REPOSITORY = PASS
REPO_TEMP_POLLUTION = 0
```
