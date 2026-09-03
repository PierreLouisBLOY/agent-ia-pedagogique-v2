# Phase 12.17.4E-B08 — Réactivation des skips B07

```text
B07_CONDITIONAL_SKIPS_BEFORE = 18
B07_SKIPS_ACTIVATED_BY_B08 = 18
B07_RESIDUAL_LEGITIMATE_SKIPS = 0
REAL_GATE_B07_PLUS_B08 = 19/19 PASS
```

Les 17 cas de `test_sqlite_runtime_real_gate.py` et le cas de
`test_sqlite_resource_application_e2e_real_gate.py` ont été rejoués avec le
seed canonique configuré et sont passés. La gate réelle B08 ajoutée est
également passée dans le même run.

Deux gates SQLite adjacentes, génération/transformation et search/RAG, ont été
rejouées séparément : `2/2 PASS`. Les runtimes, backups et restaurations de test
étaient sous des répertoires temporaires bornés puis ont été supprimés après
fermeture ; le seed et ses sidecars sont restés identiques.
