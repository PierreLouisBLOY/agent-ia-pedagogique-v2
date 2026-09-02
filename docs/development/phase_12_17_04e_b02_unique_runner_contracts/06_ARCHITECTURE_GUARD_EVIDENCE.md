# Phase 12.17.4E-B02 — Guards d'architecture

## Commande

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/architecture/test_calibration_tooling_boundary.py tests/architecture/test_calibration_tooling_active_runner.py
```

## Résultat

```text
........... [100%]
11 passed
```

Les cinq guards B01 vérifient l'ADR, le freeze 40/40, les sept drifts et
l'absence d'import historique. Les six guards B02 ajoutent :

1. exactement un runner et un parser actifs ;
2. aucun import actif vers les historiques ou `tests/providers` ;
3. aucun import de `calibration_tooling` depuis backend/harness ;
4. aucun SDK/provider/infrastructure dans contracts/application ;
5. aucun `Any`, `type: ignore` ou wrapper `LEGACY_COMPAT` ;
6. aucune anticipation des adapters, de la composition ou du CLI.

`ARCHITECTURE_GUARDS = 11/11 PASS`
