# Phase 12.17.4E-B07 — Entrée et carry-forward

```text
B06_STATUS = PASS
B07_ENTRY = READY
HEAD_PRE_B07 = 757254675d51ace6c1173cc21217580ae2509ba9
B06_COMMIT = 757254675d51ace6c1173cc21217580ae2509ba9
B06_MANIFEST_SHA256 = 45194e42a80c27d3d530aeac525fb4d590dcef54b584c56144d1ca3d79b96c05
B01_MANIFEST_SHA256 = de4903fa9a78d4cbbcc0c792a0d4e46d3805874c686b9e03d75350e694466e8e
B01_MANIFEST_ENTRIES = 8/8 PASS
ACTIVE_MYPY_PRE = 0/41
BACKEND_MYPY_PRE = 0/671
HISTORICAL_MYPY_PRE = 15 errors/10 files
HISTORICAL_FREEZE_PRE = 40/40 PASS
KNOWN_DRIFTS_PRE = 7/7
NEW_HISTORICAL_DRIFT_PRE = 0
```

Le SHA du seed canonique `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`
est uniquement propagé comme invariant documentaire. Le seed n'a pas été
ouvert. L'écart global connu de `catalog.py` est antérieur et hors scope ; il
n'est ni réparé ni requalifié dans ce lot.

Les éléments non suivis antérieurs à B07 ont été préservés et exclus du stage.
