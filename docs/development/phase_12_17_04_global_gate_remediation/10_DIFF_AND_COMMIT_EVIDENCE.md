# Phase 12.17.4 — Diff et commits

```text
HEAD_PRE_REMEDIATION = 054ba2c7eb19f1be4eb048f94e554022db631dc1
COMMIT_POLICY = REMEDIATION_THEN_SEPARATE_B09
REMEDIATION_COMMIT = CREATED_AFTER_ARTIFACT_FREEZE
B09_COMMIT = CREATED_AFTER_B09_MANIFEST_FREEZE
PUSH = NONE
```

Le premier stage est limité au helper, aux huit tests/guards de remediation et
aux douze artefacts de ce dossier. Le second stage est limité aux livrables B09,
aux deux documents `docs/legacy-review` et au guard B09. Les artefacts B01 et
les autres éléments carry-forward non suivis sont explicitement exclus.

Chaque stage exige `git diff --cached --check = PASS`. Les SHA exacts sont
publiés après création des commits afin de ne pas créer de manifeste
auto-référentiel.
