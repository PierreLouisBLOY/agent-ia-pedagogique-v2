# 12.16-G2-V4 — Canary persistant implémenté

## Familles

- `OPENAI_GENERATION_CORRECTION` ;
- `OPENAI_REVIEW` ;
- `ANTHROPIC_SCORER`.

Le premier appel planifié de chaque famille est déterminé depuis la matrice. `LiveCalibrationRunner.run()` restaure le breaker depuis le ledger, appelle `authorize()` avant l'exécution et enregistre atomiquement l'état du canary avec son résultat terminal.

Une erreur systémique catégorisée bloque tous les appels suivants de la même famille. Un refus ou résultat de contenu non systémique valide le transport du canary et autorise le fan-out. Une reprise restaure `PASSED` ou `BLOCKED` depuis le ledger et ne déduit jamais le succès d'un simple statut terminal.

```text
CANARY_INTEGRATION = PASS
CANARY_FAMILY_COUNT = 3
AUTOMATIC_RETRY = 0
```

Les tests utilisent exclusivement des fake executors et couvrent succès, blocage, fan-out interdit, résultat non systémique et reprise déterministe.
