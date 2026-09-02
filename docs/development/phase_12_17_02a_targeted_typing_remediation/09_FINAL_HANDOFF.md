# Phase 12.17.2A — Handoff final

## Statut

`PHASE_12_17_02A_TARGETED_TYPING_REMEDIATION = PASS`

Le lot atteint son objectif de corrections locales sûres avec un defer explicitement autorisé par le prompt lorsque la correction de `MYPY-001` s'est révélée liée aux identités historiques.

## Résultats

- `BASELINE_COMMIT_SHA = 3156092091bf755f1d542ef2d36ada2a34f3c210`
- `ALLOWLISTED_DIAGNOSTICS = 19`
- `EXPECTED_ROOT_CORRECTIONS = 13`
- `APPLIED_ROOT_CORRECTIONS = 12`
- `DIAGNOSTICS_REMOVED = 18`
- `DEFERRED_ALLOWLIST_DIAGNOSTICS = 1`
- `RESIDUAL_DIAGNOSTICS = 15`
- `NEW_DIAGNOSTICS = 0`
- `CODE_FILES_MODIFIED = 9`
- `TYPE_SYSTEM_ONLY = TRUE`

## Gates

- backend mypy avant/après : `0/659 -> 0/659`;
- import-driven avant/après : `33/15 files -> 15/10 files`;
- dette réservée initialement à 12.17.4 : `14/14` encore présente;
- diagnostic additionnel déféré : `MYPY-001`;
- tests ciblés : `146 passed`;
- Ruff ciblé : `PASS`;
- compileall ciblé : `PASS`;
- nouveaux ignores : `0`;
- déplacement de fichiers : `0`;
- appels provider : `0`.

## Écart expliqué

La cible initiale de 14 erreurs aurait exigé de modifier `tests/providers/anthropic/transport.py`. Ce fichier entre par ses octets dans le bundle Anthropic des identités historiques. Le fix minimal a déclenché `MATRIX_MISMATCH`; il a donc été annulé et `MYPY-001` est explicitement transféré à 12.17.4. Toutes les gates finales sont vertes après rollback.

## Livraison

- `COMMIT_SHA = SELF — à relever après création du commit local`
- `PUSH = NONE`
- `OPENAI_CALL_COUNT = 0`
- `ANTHROPIC_CALL_COUNT = 0`
- `NEXT_RECOMMENDED_SUBSTEP = 12.17.3_BUSINESS_RULE_AUDIT`

Les phases 12.17.3 et 12.17.4 n'ont pas été commencées.
