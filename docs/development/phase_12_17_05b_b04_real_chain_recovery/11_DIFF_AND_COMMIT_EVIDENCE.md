# Phase 12.17.5B-B04 — Diff et stratégie Git

Le lot B04 ajoute uniquement le présent dossier de preuves. Les bases de
validation, backups, fichiers de recovery et sidecars restent hors dépôt. Le
code runner, le SQL `002` et les tests sont le carry-forward B02/B03 approuvé.

Le plan prévoit des preuves B04 séparées, mais B02 et B03 se chevauchent et
restent non commités. Il n'autorise pas une consolidation B02+B03+B04. Aucun
stage artificiel ni commit partiel n'est donc créé.

```text
B04_TECHNICAL_SOURCE_CHANGE_COUNT = 0
B04_TRACKED_RUNTIME_DATA_COUNT = 0
B04_TRACKED_SQLITE_BINARY_COUNT = 0
B04_TRACKED_SIDECAR_COUNT = 0
COMMIT = NONE
STAGING = NONE
PUSH = NONE
COMMIT_POLICY_DISPOSITION = DOCUMENTED_PENDING_EXPLICIT_REVIEW
```

Les fichiers non suivis préexistants et hors scope ont été préservés.
