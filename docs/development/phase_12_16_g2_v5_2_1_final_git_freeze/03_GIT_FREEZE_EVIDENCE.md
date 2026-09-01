# Phase 12.16-G2-V5.2.1 — Preuve du commit de gel

## Paramètres immuables

- Parent vérifié : `c534b488276eabfa9f82b379282a043cdc0f4b65`.
- Branche : `phase12/12-16-provider-model-calibration`.
- Message exact : `test: freeze v5.2 semantic mini-pilot baseline`.
- Push : `NONE`.
- Live : `FALSE`.

Le SHA du commit ne peut pas être inscrit dans le tree qui le détermine sans créer
une référence circulaire. `BASELINE_COMMIT_SHA` est donc relevé par
`git rev-parse HEAD` immédiatement après le commit local et communiqué dans le
handoff d'exécution.

## Contrôles post-commit exigés

- parent égal à `c534b488276eabfa9f82b379282a043cdc0f4b65` ;
- sujet du commit exact ;
- `git status --short` vide ;
- `git diff HEAD^..HEAD --check` en succès ;
- manifestes conformes ;
- identités techniques inchangées ;
- aucun push et live fermé.

```text
BASELINE_COMMIT_SHA = RESOLVED_POST_COMMIT_BY_GIT_REV_PARSE_HEAD
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE
PUSH = NONE
```
