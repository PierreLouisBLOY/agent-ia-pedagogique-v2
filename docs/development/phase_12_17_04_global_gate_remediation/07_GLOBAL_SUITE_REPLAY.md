# Phase 12.17.4 — Replay de la suite globale

```text
COMMAND = python -m pytest -q -p no:cacheprovider
BEFORE = 4717 passed, 25 skipped, 7 failed
AFTER = 4725 passed, 24 skipped, 0 failed
DURATION = 437.01s
GLOBAL_SUITE = PASS
```

La variation est naturelle et entièrement comptée : les sept échecs deviennent
sept PASS, et la gate seed B08 détectée par `PROJET_V2_CANONICAL_DB` devient un
PASS supplémentaire et un skip de moins. Les 21 anciennes gates SQLite qui ne
lisent que l'alias legacy et les trois gates explicitement opt-in restent
conditionnelles. Aucun skip, xfail ou marqueur de masquage n'a été ajouté.

Un premier replay exploratoire avait lié simultanément les alias legacy et B07.
Il a été interrompu à 28 % après avoir révélé le guard compagnon obsolète ; ce
run non comparable n'est pas le verdict global. Après alignement du guard, le
replay comparable ci-dessus est le résultat de gate.
