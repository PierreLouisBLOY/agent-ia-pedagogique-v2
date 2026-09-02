# Phase 12.17.4E-B02 — Preuves de tests ciblés

## Tests unitaires et intégration

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/unit/calibration_tooling tests/integration/calibration_tooling
```

Résultat : `25/25 PASS`.

Couverture : cardinalité strong/mixed/weak, specs absolue/pairwise, version et
identités, schéma actif, parse fail-closed, borne UTF-8, troncature, budget,
allowlist exacte, consommation one-shot, ledger terminal/ambigu, dispatch,
ordre déterministe, zéro retry et arrêt au premier échec.

## Gates statiques

| Gate | Résultat |
|---|---|
| Mypy strict actif | `0 erreur / 19 fichiers` |
| Mypy backend | `0 erreur / 659 fichiers` |
| Ruff fichiers B02 | PASS |
| Ruff dépôt complet | PASS |
| compileall `backend calibration_tooling` | PASS |
| architecture | `11/11 PASS` |
| ancien root mypy | `15 erreurs / 10 fichiers`, stable |

La suite pytest globale est différée à la gate finale 12.17.4E, conformément au
plan des neuf lots. B02 ajoute un package isolé et ne modifie aucun invariant
runtime existant ; les tests ciblés et le Ruff global sont les gates
proportionnées à ce lot.

`TARGETED_TESTS = 36/36 PASS`
