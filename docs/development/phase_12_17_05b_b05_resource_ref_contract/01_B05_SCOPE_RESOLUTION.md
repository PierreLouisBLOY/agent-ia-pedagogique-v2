# Phase 12.17.5B-B05 — Résolution du scope

```text
PHASE_12_17_05B_B04 = PASS
B05_ENTRY_GATE = READY
B05_CANONICAL_TITLE = Contrat resource_ref
BASELINE_COMMIT = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
DM_02 = OPTION_A
```

## Plan gelé

| Champ | Résolution B05 |
|---|---|
| scope | source de vérité `resource_ref`, propagation Domain/Application/persistence et alignement handoff API |
| hors scope | endpoint HTTP, migration data, DM-03, `ContextOrigin`, provider |
| fichiers attendus | Value Object/erreur Resource, DTO/port/adapters, tests et preuves B05 |
| SQLite | inspection read-only uniquement; zéro écriture |
| tests | bornes, propagation READ-15, persistence, handoff, architecture, typage et qualité |
| commit policy | règle + tests sans endpoint; pas de consolidation implicite B02–B04 |
| gate suivante | B06 après contrat unique, données conformes et régressions vertes |

```text
B05_SQLITE_WRITE_AUTHORIZED = FALSE
API_ENDPOINT_IMPLEMENTED = FALSE
B06_CANONICAL_TITLE = Sémantique ACTIVE/CANONICAL
PROVIDER_CALLS = 0
```

Le bundle source a le SHA-256
`65f379d95b098f1f270f76a99fe09796791e778804f15fa738f3ca71c6f67c6b`
et son manifeste est vérifié `6/6 PASS`.
