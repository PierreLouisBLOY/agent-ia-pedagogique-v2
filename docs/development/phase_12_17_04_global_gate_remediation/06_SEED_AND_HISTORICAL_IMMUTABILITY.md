# Phase 12.17.4 — Immutabilité seed et historique

```text
HISTORICAL_FREEZE_PRE = 40/40 PASS
HISTORICAL_FREEZE_POST = 40/40 PASS
KNOWN_DRIFTS = 7/7 UNCHANGED
NEW_HISTORICAL_DRIFT = 0
HISTORICAL_FILES_MODIFIED = 0
```

| Fichier seed | Taille PRE/POST | mtime PRE/POST | SHA-256 PRE/POST |
|---|---:|---:|---|
| principal | 105553920 | 1787357637550000000 | `38ca8b3f...35134` |
| `-wal` | 0 | 1787909575545000000 | `e3b0c442...b855` |
| `-shm` | 32768 | 1788256202007000000 | `fd4c9fda...89eb` |

Les trois identités sont strictement identiques avant et après les tests ciblés
et la suite globale. Aucun fichier SQLite n'entre dans Git.
