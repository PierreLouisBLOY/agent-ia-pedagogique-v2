# Phase 12.17.5B-B06 — Preuves sur les données existantes

L'inspection du seed a été faite par URI SQLite `mode=ro&immutable=1`. Le SHA-256
avant et après est identique à l'identité canonique. Un runtime temporaire issu
du même seed et de la chaîne `001 -> 002` a été inspecté par les tests réels.

| Base | Total Resource | `ACTIVE` | `CANONICAL` | Autre |
|---|---:|---:|---:|---:|
| seed | 1 399 | 1 399 | 0 | 0 |
| runtime temporaire | 1 399 | 1 399 | 0 | 0 |

Le schéma observé ne contient aucune colonne de canonicalité séparée. La
colonne `identity_status` a le default `'ACTIVE'` et aucun `CHECK` sémantique.
Les contrôles seed donnent `integrity_check=ok`, `quick_check=ok` et zéro
violation de foreign key.

Une première invocation de tests réels a résolu un alias de configuration
legacy vers un lecteur `G:` inaccessible. Les deux noms de configuration ont
ensuite été reliés explicitement au seed local déjà authentifié; la sélection
finale a passé. Cet écart d'environnement n'a produit aucune écriture seed.

```text
SEED_RESOURCE_ACTIVE_COUNT = 1399
SEED_RESOURCE_CANONICAL_COUNT = 0
RUNTIME_RESOURCE_ACTIVE_COUNT = 1399
RUNTIME_RESOURCE_CANONICAL_COUNT = 0
SQLITE_ACCESSED = TRUE_READ_ONLY_SEED_AND_TEMPORARY_RUNTIME
SQLITE_SEED_MODIFIED = FALSE
SQLITE_BUSINESS_DATA_BACKFILLED = FALSE
```
