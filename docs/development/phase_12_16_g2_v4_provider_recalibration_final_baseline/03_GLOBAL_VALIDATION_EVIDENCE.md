# Phase 12.16-G2-V4 — Validation globale offline

Environnement d'exécution :

- `RUN_PEDAGOGICAL_LIVE_CALIBRATION`, `RUN_F2B_LIVE_SEMANTIC_BENCHMARK` et `RUN_F2B_OFFLINE_R1` supprimés du processus ;
- `OPENAI_API_KEY` et `ANTHROPIC_API_KEY` supprimées du processus ;
- base canonique `G:` lue localement par les gates SQLite réelles ;
- répertoires runtime de pytest placés hors de l'arbre source.

Résultats :

```text
PYTEST_GLOBAL = 4445 passed, 3 skipped in 815.92s
PYTEST_REAL_SQLITE_E2E = 22 passed in 534.94s
PYTEST_HISTORICAL_R2_R3_R4 = 106 passed in 57.82s
RUFF = PASS
MYPY_BACKEND = PASS (659 source files)
COMPILEALL_BACKEND_TESTS = PASS
GIT_DIFF_CHECK = PASS
SOURCE_TREE_RUNTIME_DATABASE_FILE_COUNT = 0
```

Les trois skips sont des gates opt-in volontairement fermées. Aucun skip ne masque un test standard ou une gate SQLite réelle.
