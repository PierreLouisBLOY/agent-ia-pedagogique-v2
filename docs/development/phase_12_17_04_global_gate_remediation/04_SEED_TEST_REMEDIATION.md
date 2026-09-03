# Phase 12.17.4 — Remédiation de la gate seed

La gate réelle résout désormais le seed avec `load_sqlite_paths(os.environ)`.
Elle exige un fichier réel (`CANONICAL_SEED_REQUIRED`), authentifie sa taille et
son SHA-256, puis compare un snapshot du fichier principal et des sidecars avant
et après les deux runtimes fraîches.

Le chemin local a été fourni uniquement par l'environnement d'exécution et
n'apparaît dans aucun code ni artefact. L'accès de preuve était read-only ; les
runtimes temporaires sont distinctes et supprimées après chaque exécution.

```text
SEED_TEST_BEFORE = FAIL_MISSING_LEGACY_ENVIRONMENT
SEED_TEST_AFTER = 1/1 PASS
SEED_SHA256 = 38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134
SEED_SIZE = 105553920
SEED_INTEGRITY_QUICK_FK = ok / ok / 0
SEED_MUTATION = FALSE
```
