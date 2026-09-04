# Phase 12.17.5B-B07 — Ré-audit `resource_ref`

La règle canonique unique reste :
`^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`.

Le Value Object Domain est consommé par l'input Application, le port OP-03,
l'adapter SQLite et l'inbound. Le nombre de validateurs divergents reste zéro.
Les 1 399 références du seed et les 1 399 références du runtime temporaire
sont conformes. Aucune migration de données n'est requise.

Les tests couvrent les bornes 1/128/129, la ponctuation initiale, les caractères
dangereux et Unicode, le rejet avant lookup et la distinction avec
`RES_NOT_FOUND`.

```text
RESOURCE_REF_BLOCKER = CLOSED
RESOURCE_REF_VALIDATOR_COUNT = 1
DIVERGENT_RESOURCE_REF_VALIDATORS = 0
RESOURCE_REFS_CONFORMING = 1399/1399 SEED + 1399/1399 TEMP_RUNTIME
RESOURCE_REF_DATA_MIGRATION = FALSE
```
