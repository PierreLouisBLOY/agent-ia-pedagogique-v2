# Tests et preuves de gates

```text
TARGETED_DEPENDENCY_CONFIG_SECURITY = 34 passed
CLEAN_DEV_TARGETED = 24 passed
CLEAN_DEV_PLUS_CALIBRATION_TARGETED = 41 passed
GLOBAL_NON_SQLITE_SUITE = 4880 passed, 28 skipped, 0 failed / 553.89 seconds
GLOBAL_EXPLICITLY_IGNORED = tests/non_functional/test_retrieval_quality_real_gate.py
ARCHITECTURE_GUARDS = PASS_IN_TARGETED_AND_GLOBAL
MYPY_BACKEND_AND_CALIBRATION = PASS / 710 source files
RUFF = PASS
COMPILEALL_BACKEND_AND_CALIBRATION = PASS
GIT_DIFF_CHECK = PASS
```

Les 28 skips sont 23 gates SQLite réelles sans nom V2 injecté, trois gates
provider/semantic explicitement non autorisées et deux tests de symlink indisponibles
sous Windows. L'unique fichier ignoré exige un accès au seed réel et n'est pas présenté
comme exécuté. La preuve SQLite complète reste la responsabilité de B07.

Les tests nouveaux couvrent locks exacts, pins+hashes, drift des inputs, cible
Python/plateforme, absence URL/VCS, partition runtime/calibration/dev et cohérence de
la documentation. Les tests configuration couvrent V2, legacy seul, legacy+V2 et
redaction des erreurs.

```text
PROVIDER_CALLS = 0
CANONICAL_SEED_WRITES = 0
USER_RUNTIME_WRITES = 0
TEMP_SQLITE_FIXTURES_ONLY = TRUE
```
