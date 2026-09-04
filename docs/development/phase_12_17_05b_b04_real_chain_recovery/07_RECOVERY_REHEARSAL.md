# Phase 12.17.5B-B04 — Recovery rehearsal

Le backup PRE a été restauré vers un nouveau fichier temporaire distinct. La
runtime utilisateur n'a jamais été choisie comme destination de restauration.

| Contrôle | Backup PRE | Fichier restauré | Verdict |
|---|---:|---:|---|
| taille | 105553920 | 105553920 | PASS |
| SHA-256 | `32dfca0e...8554` | `32dfca0e...8554` | PASS |
| ledger | `001` | `001` | PASS |
| lignes `document` | 15 | 15 | PASS |
| cinq defaults perdus après `001` | absents | absents | PASS |
| integrity | `ok` | `ok` | PASS |
| quick | `ok` | `ok` | PASS |
| violations FK | 0 | 0 | PASS |

Le SHA-256 complet commun est
`32dfca0e2c3a483af5f487539ce5bf75ce8398f1d73aefc700c9adc282978554`.
L'ouverture et la fermeture en lecture immuable ont réussi.

```text
RECOVERY_TARGET = DISTINCT_TEMPORARY_FILE
RECOVERY_REHEARSAL = PASS
USER_RUNTIME_OVERWRITTEN = FALSE
```
