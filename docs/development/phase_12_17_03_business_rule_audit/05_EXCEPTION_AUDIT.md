# Phase 12.17.3 — Exception audit

## Result

- Distinct exceptions: **10**.
- Exceptions without a parent rule: **0**.
- Exceptions broader than their parent: **0** proven.
- Exceptions with an implementation/evidence gap: **1** (`EX-01`).
- Exceptions without a dedicated or structural test: **1** (`EX-01`).

## Register

| ID | General rule | Activation condition | Justification and authority | Implementation/evidence | Test | Conflict |
|---|---|---|---|---|---|---|
| `EX-01` | `BR-001`–`BR-003`: no implicit legacy inheritance | A legacy asset is explicitly identified, audited, justified and approved | Canonical `README.md` reuse process | Phase 12.15 documents a Phase 7 adaptation, but the required `docs/legacy-review` trace is absent | None located for the trace obligation | No semantic conflict; documentary non-conformance |
| `EX-02` | `BR-012`: resource lookup succeeds only with a row | OP-03 returns no resource | Application use case defines `RES_NOT_FOUND`, rejected, blocking, non-retryable | `GetResourceQuery` | Unit test of missing resource | None |
| `EX-03` | `BR-018`: every SQLite connection enforces common safety settings | The connection targets the mutable runtime rather than the read-only seed | Runtime concurrency requires `busy_timeout=3000` and WAL | `connect_sqlite` | SQLite persistence unit tests | None |
| `EX-04` | `BR-019`: migrations advance through versioned artifacts | The exact same version and checksum were already applied | Verified idempotent reapplication is a no-op; a changed checksum still fails | `apply_migration` | SQLite persistence unit tests | None |
| `EX-05` | `BR-032`: a gate grants no business authority | All prelaunch checks are `APPROVED` | Approval permits continued evaluation/launch only, never validation or promotion | `RoutingPreLaunchGuard` | Gate handoff integration test | None |
| `EX-06` | `BR-052`: evidence retrieval should return its declared result | A declared retrieval channel is unavailable | Explicit `DEGRADED` evidence is safer than fabricated completeness | `RetrievalCoordinator` | Search/RAG real-gate integration test | None |
| `EX-07` | `BR-043`: effects are not retried by default | Effect state is known `NONE` and every other retry guard passes | A proven no-effect attempt can enter bounded deterministic retry | `RetryPolicy` | Retry unit tests | None |
| `EX-08` | `BR-048`: observability delivery should succeed | An observability sink fails | Sink failure is isolated and cannot change the functional outcome | `ObservabilityDeliveryPolicy` | Failure-isolated sink unit tests | None |
| `EX-09` | `BR-061`: live observations are not silently reused | Prior observation has certified identical contract, projection and lineage | Owner-approved calibration carry-forward policy | Versioned ledgers/manifests | V4.2 calibration tests | None |
| `EX-10` | `BR-060`: no provider call without exact owner approval | One exact baseline/matrix/allowlist/price ceiling is authorized once | Owner decision and live guard | Live runner authorization guards; authorization consumed | Live-runner unit tests | None; historical scope only |

## Assessment

`EX-01` is the only exception that fails the complete evidence chain expected by its parent policy. The repository records the adaptation, but not at the mandated trace location. The audit neither reconstructs nor approves that trace.

The other exceptions are narrower than their parent rules, have an identifiable authority and have implementation or structural evidence. Their wording is still candidate material until the canonical rule set is owner-approved.
