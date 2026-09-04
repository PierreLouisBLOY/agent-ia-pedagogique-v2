# Staging et commit

La politique B04 exige un commit atomique contrat+tests+preuves. Le staging doit être littéral et contenir uniquement les fichiers B04. Aucun log, base, sidecar, fichier temporaire, bytecode, secret ou sortie fournisseur n'est admissible.

```text
EXPECTED_STAGED_FILE_COUNT = 21
GIT_DIFF_CACHED_CHECK = PASS_BEFORE_COMMIT
COMMIT_POLICY = ONE_ATOMIC_B04_COMMIT
COMMIT_SHA = CREATED_AFTER_MANIFEST_FREEZE
PUSH = NONE
MERGE = NONE
ROLLBACK = git revert <COMMIT_SHA> après revue explicite
```
