# Phase 12.17.4E-B08 — Diff et commit

Le lot modifie le provisioning/migration et la connexion SQLite, ajoute un
test unitaire de cycle, une gate réelle, quatre guards d'architecture et les
preuves de ce répertoire. Le SQL de migration approuvé n'est pas modifié.

Les artefacts non suivis antérieurs, les 40 historiques, le seed, la runtime,
ses sidecars et tous les backups restent hors stage et hors Git.

```text
B08_COMMIT_POLICY = SEPARATE_COMMIT
B08_COMMIT = CREATED_AFTER_ARTIFACT_FREEZE
COMMIT_MESSAGE = feat: establish sqlite seed runtime lifecycle
PUSH = NONE
```
