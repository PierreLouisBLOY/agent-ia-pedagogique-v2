# Phase 12.17.4E-B05 — Résolution du scope canonique

La lecture du plan approuvé définit le lot sans ambiguïté.

```text
B05_CANONICAL_TITLE = Fermeture typing et dépréciation active
B05_ROOT_CHANGES = RC-05
B05_COMMIT_POLICY = SEPARATE_COMMIT
```

## Scope exact

- tests de parité des invariants durables sur les contrats actifs ;
- documentation `HISTORICAL_ONLY` des anciennes racines V4/V5.x ;
- preuve statique qu'aucun source ou test actif n'importe ces racines ;
- fermeture des 15/15 diagnostics dans la traversée active uniquement ;
- reproduction distincte de la dette historique à 15 erreurs / 10 fichiers.

Les fichiers prévus sont des tests sous `tests/unit/calibration_tooling/` et
`tests/integration/calibration_tooling/`, les guards nécessaires et la
documentation d'exploitation. Aucun changement runtime n'est requis : B04
avait déjà ramené les imports actifs résiduels à zéro.

## Hors scope

B06 vocabulaires, B07 chemins, B08 SQLite, B09 legacy/API, migration,
modification historique, configuration mypy d'exclusion et provider live sont
exclus.

`B06_CANONICAL_TITLE = Vocabulaires et mappings owners`.
