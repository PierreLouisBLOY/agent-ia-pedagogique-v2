# Phase 12.17.6 — `.gitignore`, chemins privés et fichiers locaux

## Couverture satisfaisante

`.gitignore` couvre environnements virtuels, bytecode, caches pytest/ruff/mypy, `.env*`, clés PEM/key, SQLite/SQLite3/DB/DB3, WAL/SHM, logs, `/logs`, `/runtime`, `/exports`, `/artifacts`, `/.tmp`, `/tmp`, `/temp`, builds, distributions et fichiers éditeur/OS.

Les sondes `probe.sqlite`, `probe.sqlite-wal`, `probe.db`, `probe.db-shm`, `probe.log`, `runtime/*`, `artifacts/*` et `.tmp/*` sont bien ignorées.

## Gaps `.gitignore`

Quatre familles ne sont pas couvertes hors des répertoires dédiés :

1. backups génériques `*.backup`/`*.bak` et leurs manifests ;
2. temporaires adjacents `*.tmp` créés près d'une DB/backup ;
3. index sémantiques temporaires `*.building` ;
4. logs structurés `*.jsonl` placés hors `/logs`.

`GITIGNORE_GAPS_COUNT = 4`

## Chemins privés

Aucun chemin privé codé en dur n'est présent dans le runtime. Le seul match sous `backend/` est le regex de détection protecteur de `_value_safety.py`. Cinq éléments non suivis des 126 contiennent des chemins historiques de preuve ; ils sont classés comme preuve/docs, pas comme bug runtime, et doivent être minimisés avant versionnement éventuel.

`PRIVATE_RUNTIME_PATH_LEAKS_COUNT = 0`

## Racines ignorées observées

| Racine | Fichiers | Octets | Classification |
|---|---:|---:|---|
| `.tmp` | 3 134 | 11 432 634 | temporaires et copies de tests |
| `artifacts` | 747 | 2 828 378 | résultats locaux générés |
| `.mypy_cache` | 18 | 56 938 725 | cache attendu |
| `.pytest_cache` | 5 | 685 958 | cache attendu |
| `.ruff_cache` | 21 | 97 562 | cache attendu |
| `.venv` | 10 277 | 132 105 615 | environnement local attendu |
| `.venv-validation` | 3 783 | 97 704 924 | environnement local attendu |
| `runtime`, `temp`, `tmp` | 0 | 0 | répertoires vides |

Les artefacts temporaires/cache hors environnements représentent `3 178` fichiers. Aucun fichier n'est déclaré stale sans preuve. Aucun binaire SQLite produit n'a été détecté sous `.tmp` ou `artifacts`.
