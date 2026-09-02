# Phase 12.17.4E-B04 — Diff et commit

## Diff B04

Le lot comporte 14 fichiers code/test :

- 4 mises à jour du socle B02/B03 : version, enum d'erreurs, exports runtime et
  guard de séquencement ;
- 3 fichiers de configuration/composition/CLI ;
- 3 fichiers d'observabilité ;
- 4 fichiers de tests unitaires, intégration et architecture.

Il ajoute aussi les 9 preuves B04 et leur manifeste. Aucun backend métier,
aucun harness, aucun fichier historique, aucun artefact B01, aucune donnée
runtime, base, migration ou secret n'est inclus.

## Isolation et politique

Le stage est construit avec une allowlist explicite limitée aux fichiers B04.
Les artefacts antérieurs non suivis et le carry-forward B01 restent hors index.

```text
B04_COMMIT_POLICY = SEPARATE_COMMIT
B01_MIXED_WITH_B04 = FALSE
B04_COMMIT = CREATED_AFTER_ARTIFACT_FREEZE
COMMIT_MESSAGE = refactor: compose canonical calibration runtime
PUSH = NONE
```
