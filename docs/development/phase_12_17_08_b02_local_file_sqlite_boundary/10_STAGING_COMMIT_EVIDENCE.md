# Phase 12.17.8-B02 — Staging et commit

La politique B02 exige un seul commit atomique code + tests + preuves. L'allowlist est la liste littérale des fichiers de code/config/factories touchés, des tests B02 ou guards directement adaptés, et des treize artefacts de ce dossier.

Avant commit, les contrôles suivants sont obligatoires : inventaire `git status`, revue du diff, scan secrets et bases/sidecars, manifeste `12/12`, égalité staged/allowlist, `git diff --cached --check`, puis seed/runtime POST.

```text
UNEXPECTED_PATHS = 0
STAGED_FILE_COUNT = 30
GIT_DIFF_CACHED_CHECK = PASS_BEFORE_COMMIT
COMMIT_POLICY = ONE_ATOMIC_B02_COMMIT
COMMIT_SHA = CREATED_AFTER_MANIFEST_FREEZE
PUSH = NONE
MERGE = NONE
```
