# Phase 12.17.4E-B08 — Typing et architecture

```text
ACTIVE_MYPY_PRE_POST = 0/41 -> 0/41
BACKEND_MYPY_PRE_POST = 0/671 -> 0/671
HISTORICAL_MYPY_PRE_POST = 15 errors/10 files -> 15 errors/10 files
NEW_MYPY_DIAGNOSTICS = 0
ARCHITECTURE_GUARDS = 46/46 PASS
RUFF_GLOBAL = PASS
COMPILEALL_BACKEND_CALIBRATION_TOOLING = PASS
GIT_DIFF_CHECK = PASS
```

Les quatre guards B08 prouvent l'ouverture seed immuable/query-only, la
publication fraîche et atomique, l'allowlist et le maintien des deux migrations
UNKNOWN en deferred, ainsi que l'absence de chemin privé ou dépendance
provider. Les frontières B01–B07 restent vertes.

La dette mypy historique conserve volontairement son exit code `1` et ses 15
diagnostics dans 10 fichiers ; elle est stable, pas déclarée PASS.
