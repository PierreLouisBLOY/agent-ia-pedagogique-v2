# Phase 12.17.4E-B04 — Résolution du scope canonique

La lecture du plan approuvé rend le lot univoque.

```text
B04_CANONICAL_TITLE = Composition, imports et CLI
B04_ROOT_CHANGES = RC-04
B04_SCOPE = composition explicite, télémétrie sûre et point d'entrée unique
B04_COMMIT_POLICY = SEPARATE_COMMIT
```

Fichiers prévus :

- `calibration_tooling/runtime/configuration.py` ;
- `calibration_tooling/runtime/composition.py` ;
- `calibration_tooling/runtime/cli.py` ;
- `calibration_tooling/observability/*.py` ;
- tests d'intégration offline et guards associés.

Les tests exigés sont le graphe d'imports, le client fake, le comportement
fail-closed et les gardes allowlist/budget/ledger. L'invariant central est une
configuration injectée dont l'exécution provider est désactivée par défaut.

## Hors scope

B05 typing/dépréciation, B06 vocabulaires, B07 chemins, B08 SQLite, B09
legacy/API, toute migration et tout appel provider live sont exclus. Le lot ne
modifie aucun fichier historique et ne réouvre aucune décision 12.16.

`B05_CANONICAL_TITLE = Fermeture typing et dépréciation active`.
