# Phase 12.16-G2-V4.2 — Validation réduite post-approbation

Date : 2026-09-01.

La suite globale n'a pas été lancée. Les variables de credentials ont été neutralisées
et `RUN_PEDAGOGICAL_LIVE_CALIBRATION=0` pendant pytest.

## Résultats exécutés

```text
pytest ciblé V4.2                     PASS — 12 passed in 6.17s
Ruff sur les 3 fichiers Python V4.2  PASS — All checks passed
mypy sur les 2 modules V4.2          PASS — no issues found
compileall sur les 2 modules V4.2    PASS
audit de partition                    PASS — 63 + 39 = 102
audit de dérive                       PASS — OTHER_CALL_SPEC_DRIFT = 0
manifeste approuvé                    PASS — 10/10 entrées exactes
```

Le contrôle mypy utilise `--follow-imports=skip --explicit-package-bases` afin de rester
limité aux modules V4.2 et de ne pas englober les diagnostics legacy hors scope.

Les contrôles couvrent le Review contract, la troncature, le call-spec hashing,
l'équivalence carry-forward, la provenance, la repair tranche, le failed Anthropic,
les canaries, le budget guard et l'autorisation fail-closed.
