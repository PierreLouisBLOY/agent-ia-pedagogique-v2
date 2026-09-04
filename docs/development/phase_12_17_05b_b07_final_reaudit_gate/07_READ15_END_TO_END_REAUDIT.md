# Phase 12.17.5B-B07 — Ré-audit READ-15 end-to-end

Chaîne vérifiée :

`resource_ref -> ResourceRef -> GetResourceRequest -> GetResourceQuery -> OP-03 -> SQLite adapter -> ResourceView -> inbound projection`.

| Contrôle | Verdict |
|---|---|
| référence bornée/validée avant lookup | PASS |
| `version_ref` déprécié et rejeté | PASS |
| `include` déprécié et rejeté | PASS |
| query/port Application transport-neutral | PASS |
| persistence via OP-03, aucune ligne SQLite au-delà du port | PASS |
| invalid-ref distinct de `RES_NOT_FOUND` | PASS |
| réponse minimisée à quatre champs | PASS |
| champ `availability_status` sémantiquement exact | PASS |
| canonicalité non inventée | PASS |
| handoff sans SQL/repository direct | PASS |
| endpoint HTTP absent | PASS, conforme au scope |

Le handoff effectif est la base B09 complétée non rétroactivement par les deltas
B05 et B06. L'ancien nom `identity_status` dans B09 est historique; la
projection active autorisée est `availability_status`.

```text
READ15_DATA_MODEL_ALIGNMENT = PASS
READ15_API_HANDOFF_READINESS = READY
READ15_RESPONSE_FIELDS = 4/4 DEFINED
READ15_DIRECT_SQL = FALSE
ACTUAL_API_V2_ENDPOINTS = 0
```
