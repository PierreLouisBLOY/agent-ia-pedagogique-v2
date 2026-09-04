# Staging et commit

La politique canonique exige un commit atomique code+configuration+tests+preuves B03. Le staging est littéral et limité aux fichiers B03. Aucun log, fichier temporaire, base, sidecar runtime, secret ou sortie fournisseur ne peut être inclus.

```text
STAGED_FILES = 36
GIT_DIFF_CACHED_CHECK = PASS_BEFORE_COMMIT
COMMIT_SHA = CREATED_AFTER_MANIFEST_FREEZE
PUSH = NONE
ROLLBACK = git revert <COMMIT_SHA> après revue explicite
```

Le rollback du code n'autorise ni ne déclenche la suppression de journaux utilisateur existants.
