# Phase 12.17.8-B01 — Gel du plan à sept lots

```text
12_17_8_BATCH_COUNT = 7
ORDER = B01 -> (B02, B04, B05, B06) ; B02 -> B03 ; ALL -> B07
PROVIDER_CALLS_ALL_BATCHES = 0
CANONICAL_OR_USER_SQLITE_WRITES_ALL_BATCHES = 0
```

| Batch | Canonical title | Findings | Scope | SQLite | Provider | Owner approval | Commit policy |
|---|---|---|---|---|---|---|---|
| B01 | Consolidation de provenance | CF-REPO-001 | Evidence inventory, approved minimization, manifests and staging provenance | none | 0 | required and obtained | one documentation/provenance commit; literal staging; no push |
| B02 | Frontière locale fichiers et SQLite | CF-FILE-001; CF-SQLITE-HARDEN-001 | Local filesystem boundary and seven SQLite guards | temporary fixtures/copies; seed read-only only | 0 | no additional business decision | one atomic code/tests/evidence commit |
| B03 | Observabilité minimale locale | CF-OBS-001 | Local rotating NDJSON sink and 12 signals | temporary fixtures only | 0 | OBS-A obtained | one atomic code/config/tests/evidence commit |
| B04 | Contrat HTTP local-browser fail-closed | CF-HTTP-001 | Pure loopback-only contract; no server or endpoint | none | 0 | no | one contract/tests/evidence commit |
| B05 | Dépendances, environnement et alias de configuration | CF-DEPENDENCY-001; CF-DOC-001; CF-LEGACY-001 | Locks, environment docs and V2 config aliases | none | 0 | separate approval only for a lock exception | one environment/config/docs/tests commit |
| B06 | `.gitignore`, tests déterministes et rétention locale | CF-TEMP-LOCAL-001; CF-GITIGNORE-001 | Four ignore gaps, deterministic walkers, dry-run retention | none | 0 | no destructive action authorized | one hygiene/tests/evidence commit |
| B07 | Ré-audit transverse et clôture | eight must-fix findings; four historical and four deferred monitored | 16 final gates and closure evidence only | seed read-only; temporary runtimes | 0 | closure review required before merge | one documentary closure commit; no automatic push/merge |

The plan source is `09_12_17_8_BATCH_EXECUTION_PLAN.md`; no scope was inferred from the label B01.
