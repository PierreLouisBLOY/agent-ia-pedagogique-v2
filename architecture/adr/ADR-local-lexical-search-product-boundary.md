# ADR — Local lexical search product boundary

Status: accepted for bounded R1 implementation by the explicit owner message in this task.
Baseline: 3f724ca81843b5d45ac534e9654ff16281c55713.
Decision package manifest: 7e210975e1c64ecc29aa73bbbaf48c2e4b099501625fd061f33f0ef13d8f15f4.
No invented ADR sequence number or owner timestamp. ADR-P12-069 remains unchanged.

## Decision

Implement exactly P01–P15 of SEARCH-HTTP-LOCAL-1.0. M03 owns a bounded indexed-passage discovery use case with transport-neutral input/output and ports. A separate outbound bridge translates existing Evidence contracts; M03 never imports agent_runtime. Reuse OP-11 LEXICAL, independent F2A admission, OP-13 and OP-03 unchanged. No structured-membership shortcut, semantic fallback, new SQL search, migration or provider.

Add only GET /api/v2/search to the four existing routes. Query parameters are allowed solely on that exact route. READ-15, ResourceRef, body/method restrictions, security ownership, three local assets, correlation and OBS_A remain unchanged. A hit is not a ResourceRef: opening requires RESOURCE, valid domain reference and successful exact Application lookup. Empty bounded results never establish an empty library.

A new readonly snapshot bridge owns BEGIN/rollback only; composition owns the explicit target identity, query-only connection and close. Materialize only admitted selected passages. No implicit settings, seed or runtime discovery. HTTP only receives an injected Application invocation and performs a closed minimized projection.

## Guard scope and invariants

G01: exact five-route AST/runtime/document oracle, no off-registry route.
G02: exact 30-path inventory against the fixed search baseline, with 17 hash-protected input documents; retain the separate 24b7a9850bc4644391dee2307c8a8a31036cd503 historical AST baseline.
G03: only the ResourceRef A7 route tuple assertion.
G04: only the owner assertion with eight additional exact M03/inbound paths and the inventory condition.
U01: only the unit route cardinality 4 -> 5.

All other tests/assertions remain unchanged. No permissive prefix, skipped guard, dependency or framework. Historical manifests describe their Git snapshots; they are not rewritten.

## Proof and limits

Tests use fresh synthetic SQLite fixtures, logs and caches outside the repository, loopback only, process-only configuration and existing dependencies. The owner explicitly approves the sole real-seed test exclusion recorded in the active contract. No data-user metadata access, credentials, external network, migrations, persistent settings, push, merge or H3.

Ship one coherent local commit after targeted positive/negative tests, the authorized suite, lint/typecheck/compile/dependency checks and diff review. Browser manual acceptance remains separate from HTTP/static asset tests. R1 is not full H2/Phase12 closure. Stop after R1; R2 conversational generation is the next priority, with no intervening library enrichment.
