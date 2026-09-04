# Phase 12.17.5C — Rejeu de la suite globale

Le premier rejeu post-commit a produit `4814 PASS, 3 SKIP, 2 FAIL`. Les deux
échecs provenaient exclusivement de 109 bases/sidecars temporaires laissés sous
`.tmp/pytest-05c-targeted-precommit` : deux guards parcourent l'arbre source
et n'ignorent pas `.tmp`.

Après suppression des seuls temporaires 05C, la même suite a été rejouée avec
un `basetemp` système hors dépôt. Ce rejeu autoritatif est vert :

```text
GLOBAL_SUITE_REPLAY = 4816 PASS, 3 SKIP, 0 FAIL
GLOBAL_SUITE_DURATION = 548.94s
SKIP_MASKING = NONE
SYSTEM_BASETEMP_CLEANED = TRUE
REPOSITORY_RUNTIME_DATABASES_EXCLUDING_TOOL_CACHES = 0
```

Les trois skips sont les gates explicites live calibration, live semantic
retrieval et offline R1, toutes dépourvues de l'autorisation séparée requise.
Aucun skip nouveau n'a été ajouté.
