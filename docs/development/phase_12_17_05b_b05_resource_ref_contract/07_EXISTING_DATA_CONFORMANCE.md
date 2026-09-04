# Phase 12.17.5B-B05 — Conformité des données existantes

Le seed et la runtime ont été ouverts en `mode=ro&immutable=1`. Seuls les
identifiants `resource.id` ont été validés en mémoire; aucune ligne ni aucun
contenu pédagogique n'est exporté dans les preuves.

| Source | Références vérifiées | Conformes | Non conformes | Longueur min/max |
|---|---:|---:|---:|---:|
| seed canonique | 1399 | 1399 | 0 | 44 / 44 |
| runtime utilisateur | 1399 | 1399 | 0 | 44 / 44 |

Il s'agit de 2 798 observations physiques de 1 399 références logiques
miroitées. `integrity_check=ok`, `quick_check=ok` et les violations FK sont à
zéro pour les deux sources.

Les snapshots main/WAL/SHM/journal sont strictement identiques PRE/POST :

```text
SEED_MAIN_SHA256_PRE_POST = 38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134 -> SAME
RUNTIME_MAIN_SHA256_PRE_POST = de6186a26c1054731a7c0702baa133a8dc995b102417151f6538935ba04d1fb1 -> SAME
SIDECARS_PRE_POST = IDENTICAL
SQLITE_ACCESSED = TRUE_READ_ONLY
SQLITE_WRITE_OPERATIONS = 0
SQLITE_MODIFIED = FALSE
DATA_MIGRATION_REQUIRED = FALSE
```
