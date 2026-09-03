# Phase 12.17.4E-B07 — Mypy et architecture

```text
ACTIVE_MYPY_PRE_POST = 0/41 -> 0/41
BACKEND_MYPY_PRE_POST = 0/671 -> 0/671
HISTORICAL_MYPY_PRE_POST = 15 errors/10 files -> 15 errors/10 files
NEW_MYPY_DIAGNOSTICS = 0
ARCHITECTURE_GUARDS = 42/42 PASS
RUFF = PASS
COMPILEALL_BACKEND_CALIBRATION_TOOLING = PASS
GIT_DIFF_CHECK = PASS
```

Le mypy actif a été exécuté en mode strict avec `explicit-package-bases`. La
dette historique a été rejouée séparément : son exit code reste `1`, avec
exactement 15 diagnostics dans 10 fichiers. Elle n'est donc pas présentée comme
une gate verte, seulement comme une reproduction stable.

Les cinq guards B07 couvrent les noms nouveaux et legacy, l'absence de chemin
privé dans le code de configuration, l'absence de découverte globale, la
lecture injectée par la composition et l'absence de SQL/provider/métier dans le
contrat de chemins.
