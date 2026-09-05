# Staging et stratégie de commit

L'allowlist B05 contient 10 chemins techniques/documentaires globaux et les 13 preuves
de ce répertoire, soit 23 chemins. `pyproject.toml` et `requirements-dev.txt` restent
byte-identiques. Les wheelhouses, venvs, caches et outputs d'installation sont hors Git.

```text
HEAD_PRE_B05 = b63a1463046141512739e4c8f4618ab967002c78
HEAD_POST_B05 = CREATED_AFTER_MANIFEST_FREEZE
B05_TECHNICAL_PATH_COUNT = 10
B05_EVIDENCE_PATH_COUNT = 13
B05_STAGING_ALLOWLIST_COUNT = 23
B05_COMMIT_POLICY = ONE_ENVIRONMENT_LOCKS_CONFIG_DOCS_TESTS_COMMIT
COMMIT_SUBJECT = build(deps): freeze reproducible py312 windows environment
PUSH = NONE
MERGE = NONE
```

Avant commit, le stage doit contenir exactement ces 23 chemins, `git diff --cached
--check` doit passer et les scans secrets/binaires/DB/private-paths doivent rester à
zéro. Le rollback après revue est un `git revert` du commit B05 ; aucun environnement
utilisateur n'est automatiquement modifié ou downgradé.
