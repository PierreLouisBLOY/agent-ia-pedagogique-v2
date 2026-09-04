# Phase 12.17.5B-B04 — Scope et autorisation d'écriture

## Résolution du plan gelé

| Champ | Valeur |
|---|---|
| titre canonique | `Validation réelle de la chaîne et récupération` |
| scope | preuve réelle `001 -> 002`, replay et récupération sur copies temporaires |
| hors scope | seed canonique, runtime utilisateur, règle métier nouvelle, B05 et 12.17.6 |
| fichiers du lot | preuves documentaires uniquement |
| SQLite autorisé | copies/runtime de test hors dépôt |
| commit policy | preuves séparées, aucun binaire ou sidecar dans Git |
| gate suivante | B05 après schéma, integrity, quick, FK et ledger PASS |

Le plan n'autorise aucune écriture sur la runtime utilisateur. La demande
d'exécution du bundle B04 autorise le lot, mais n'élargit pas cette frontière.

```text
B04_USER_RUNTIME_WRITE_AUTHORIZED = FALSE
VALIDATION_TARGET = CONTROLLED_RUNTIME_COPY
USER_RUNTIME_002_APPLIED = FALSE
PROVIDER_CALLS = 0
```

Le seed et la runtime utilisateur n'ont été ouverts qu'en lecture immuable pour
les constats nécessaires. Les écritures B04 ont été limitées à un répertoire
temporaire hors dépôt.
