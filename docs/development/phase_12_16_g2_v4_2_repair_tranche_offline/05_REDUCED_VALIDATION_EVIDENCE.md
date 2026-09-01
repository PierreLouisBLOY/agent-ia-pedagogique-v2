# Phase 12.16-G2-V4.2 — Preuves de validation réduite

Date : 2026-09-01.

La suite globale n'a pas été lancée. Les credentials ont été neutralisés et
`RUN_PEDAGOGICAL_LIVE_CALIBRATION=0` pendant pytest.

## Tests ciblés

Commande :

```powershell
python -m pytest -q -p no:cacheprovider --basetemp .tmp/pytest-v42-final tests/unit/test_pedagogical_calibration_v4_2.py
```

Résultat final : `12 passed in 6.00s`.

Couverture : contrat Review, fixture maximale, validations locales, diagnostic de
troncature V4.1, call-spec hashing, équivalence carry-forward, provenance inter-runs,
sélection de la tranche, sélection unique du failed Anthropic, canaries-first, budget
guard, autorisation fail-closed et invariants de readiness.

## Contrôles statiques ciblés

```text
Ruff (3 fichiers V4.2)                 PASS — All checks passed
mypy (2 modules V4.2, imports skipped) PASS — no issues found
compileall (2 modules V4.2)            PASS
git diff --check                       PASS
```

Les imports sont volontairement sautés dans mypy afin de limiter le contrôle aux deux
modules modifiés et de ne pas réintroduire les 45 diagnostics legacy hors scope. Aucun
diagnostic mypy ne touche un fichier V4.2.

Les vérifications de manifeste et d'absence de secret sont consignées dans le handoff
final. Aucun test n'est déclaré PASS sans exécution réelle.
