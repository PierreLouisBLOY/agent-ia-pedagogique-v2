# Phase 12.17.4E-B06 — Tests ciblés

La suite cumulative B01–B06 a exécuté 127 cas : 89 cas carry-forward et 38 cas
SQLite/Resource B06. Ces derniers couvrent 21 cas de mapping, quatre guards
owners, trois guards SQLite, trois cas path/migration, quatre guards Resource,
deux cas de query et un cas de route Application. Elle n'a utilisé ni réseau,
ni provider, ni seed.

```text
TARGETED_TESTS = 127/127 PASS
ARCHITECTURE_GUARDS = 33/33 PASS
MAPPING_FAMILIES = 10/10 PASS
UNKNOWN_VALUE_CASES = 10/10 PASS
ACTIVE_MYPY = 0/41 PASS
BACKEND_MYPY = 0/671 PASS
HISTORICAL_MYPY = 15 errors/10 files STABLE
RUFF_GLOBAL = PASS
COMPILEALL_BACKEND = PASS
```

Un probe non bloquant de la suite globale a été interrompu au premier échec
historique connu : `test_anchor_corpus_v3_fitness` compare encore le hash
12.16 de `catalog.py` à sa version 12.17.2A. La gate B01 confirme séparément le
hash gelé courant ; le plan réserve la suite globale de clôture à l'après-B09.
