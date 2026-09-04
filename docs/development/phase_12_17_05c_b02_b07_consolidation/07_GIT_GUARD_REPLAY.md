# Phase 12.17.5C — Rejeu du guard historique

Avant consolidation, le test
`test_later_provider_work_preserves_phase_f_backend_owners` échouait comme
attendu parce qu'il interroge `git diff --name-only HEAD -- backend`.

Après le commit, le diff backend contre `HEAD` est vide et le test passe
`1/1`. Le guard n'a pas été modifié.

```text
HISTORICAL_GUARD_SHA256 = c363c5cf6a2b19802a04f68b079126047a8f33f037a9681cc21ae7169e03641c
HISTORICAL_GUARD_CHANGED_IN_COMMIT = 0
B07_GIT_GUARD_PRE = FAIL_EXPECTED
B07_GIT_GUARD_POST = 1/1 PASS
B07_GIT_GUARD = PASS
```
