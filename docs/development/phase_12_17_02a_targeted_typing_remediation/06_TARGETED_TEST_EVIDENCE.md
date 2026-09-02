# Phase 12.17.2A — Preuves de tests ciblés

## Pytest final

Les onze fichiers de tests ciblent directement les neuf modules modifiés et leurs invariants transverses immédiats :

```text
tests/providers/anthropic/test_transport.py
tests/unit/test_pedagogical_calibration_catalog.py
tests/unit/test_pedagogical_calibration_call_plan.py
tests/calibration/pedagogical/test_anchor_corpus_v3.py
tests/calibration/pedagogical/test_v3_human_delta_reconciliation.py
tests/unit/test_pedagogical_calibration_v4_2.py
tests/unit/test_pedagogical_calibration_v5_semantic_integration.py
tests/unit/test_pedagogical_calibration_v5_semantic_pilot_freeze.py
tests/unit/test_pedagogical_calibration_v5_1_mini_pilot.py
tests/unit/test_pedagogical_calibration_v5_2_semantic_gate.py
tests/unit/test_pairwise_output_contract_v5_2_4.py
```

Résultat final : `146 passed in 64.99s`.

## Contrôles statiques et qualité

- mypy backend : `PASS — 0 erreur / 659 fichiers`;
- mypy import-driven : résultat attendu du lot ajusté, `15 erreurs / 10 fichiers`, aucun diagnostic nouveau;
- Ruff ciblé sur les neuf fichiers Python modifiés : `All checks passed!`;
- `compileall -q` sur les neuf fichiers Python modifiés : `PASS`;
- `git diff --check` avant génération des preuves : `PASS`.

## Probe diagnostique annulée

Avant rollback de `MYPY-001`, le run en arrêt immédiat a produit `71 passed, 1 failed`; l'échec était la gate `MATRIX_MISMATCH` de V4.2. Cette probe a servi à refuser le changement. Le run final de 146 tests est entièrement vert.

Aucune suite globale n'a été lancée et aucun test n'a ouvert un provider live.
