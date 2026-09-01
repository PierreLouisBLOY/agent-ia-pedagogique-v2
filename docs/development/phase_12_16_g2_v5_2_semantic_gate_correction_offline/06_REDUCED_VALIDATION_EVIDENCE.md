# Phase 12.16-G2-V5.2 — Validation réduite

## Périmètre

Fichiers ajoutés :

- `tests/calibration/pedagogical/semantic_gate_v5_2.py`;
- `tests/unit/test_pedagogical_calibration_v5_2_semantic_gate.py`.

Aucune suite globale n'a été lancée.

## Résultats

| Contrôle | Résultat |
|---|---|
| Tests ciblés V5.2 | `PASS — 12 passed in 41.57s` |
| Ruff, deux fichiers | `PASS` |
| mypy strict, explicit-package-bases, follow-imports skip | `PASS — 2 source files` |
| compileall, deux fichiers | `PASS` |
| Validation offline des hashes, carries et budget | `PASS` |
| `git diff --check` | `PASS` |

## Couverture des tests

Les tests prouvent :

- modèle d'attente versionné et sourcé;
- absence d'inférence depuis un nom de tier;
- dérivation check-based de `Strong/Mixed/Weak = 4/0/1`;
- absence d'anchor intermédiaire prévalidé et exclusion de la proposition;
- carry-forward Strong et Mixed, avec échec sur toute dérive;
- pairwise SCN-06 et SCN-01 explicites;
- call-specs et projections gelés;
- budget recalculé à trois appels;
- gates sémantiques, distribution, provenance et fail-closed;
- gate live fermée.

## Frontières

- Provider calls : `0`.
- Credential/transport : `NONE`.
- Retry/rerun : `0/0`.
- Commit/push : `NONE/NONE`.
- `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`.
