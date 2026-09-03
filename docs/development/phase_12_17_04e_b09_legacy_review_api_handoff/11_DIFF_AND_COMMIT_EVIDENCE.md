# Phase 12.17.4E-B09 — Diff et commit

```text
HEAD_PRE_B09 = 054ba2c7eb19f1be4eb048f94e554022db631dc1
B09_COMMIT_POLICY = SEPARATE_COMMIT
GLOBAL_REMEDIATION_COMMIT = 325ea3397507c0f3d94b9c1ef75c20ca47592d80
B09_COMMIT = CREATED_AFTER_MANIFEST_FREEZE
PUSH = NONE
```

Le stage éventuel sera limité aux deux documents `docs/legacy-review`, aux
seize artefacts B09 et au guard documentaire B09. Les éléments non suivis
préexistants B01/12.17.3/design et le guard de frontière B01 sont exclus.

La remediation est isolée dans son commit propre. Le stage B09 reste limité aux
livrables ci-dessus et exclut les éléments carry-forward B01/12.17.3/design.
Le SHA du commit B09 est publié après sa création pour éviter toute
auto-référence du manifeste.
