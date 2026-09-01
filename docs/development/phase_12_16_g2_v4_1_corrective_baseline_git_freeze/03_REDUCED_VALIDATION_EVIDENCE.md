# Phase 12.16-G2-V4.1 — Preuves de validation réduite

## Validations obligatoires

- Tests unitaires V4.1 baseline, authorization, reporting, matrice et budget : `15 passed in 8.85s`.
- Checksum matrice : `94eb067ac7dd8498eeb2605ee506315fd0c831259f454555ecac88acbe94403a` — `PASS`.
- Checksum pricing : `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8` — `PASS`.
- Budget guard : `102` appels, plafond `4.984760 USD` — `PASS`.
- Fail-closed identité/configuration/live avant executor : `PASS`.
- Intégrité des manifests : `PASS`.
- `git diff --check` avant indexation : `PASS`.

La suite globale n'a pas été relancée dans ce lot : la preuve immédiatement antérieure reste `4460 passed, 3 skipped in 839.43s`, conformément à l'instruction de validation réduite.

## Qualité Python

- Changement Python dans le lot de freeze : `0`.
- Ruff sur les trois fichiers Python V4.1 figés : `PASS`.
- compileall sur les trois fichiers Python V4.1 figés : `PASS`.
- mypy du lot de freeze : `NOT_REQUIRED_NO_PYTHON_CHANGE`.

Un essai diagnostic non requis de mypy strict sur le harness test-only a relevé `45` diagnostics dans ses dépendances. La configuration canonique de `pyproject.toml` limite mypy à `backend`, qui passait avant le gel (`659` fichiers). Aucun diagnostic n'a été remédié, car toute modification Python aurait constitué une dérive post-approbation.

SCOPED_MYPY_TEST_DIAGNOSTIC = OUT_OF_SCOPE_NON_GATING

SCOPED_MYPY_TEST_DIAGNOSTIC_COUNT = 45

REMEDIATION_ROUTE = SEPARATE_POST_FREEZE_LOT_ONLY

## Sécurité

- Appels OpenAI : `0`.
- Appels Anthropic : `0`.
- Credentials résolus : `0`.
- Transports réels construits : `0`.
- Autorisation live : `FALSE`.
