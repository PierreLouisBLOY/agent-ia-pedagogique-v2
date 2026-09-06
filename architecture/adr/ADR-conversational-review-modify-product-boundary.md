# ADR — R3 conversational review and targeted modification

Status: accepted for synthetic implementation by the project owner, 2026-09-06.
Baseline: 817ad474d93c78c602a22bd30cf77fe7621e68b1.
Approved proposal manifest: b9f90be754a2e7dc359087675e23ec4284673e9e5336fe742ecf286a1ddba211.

## Decision and authority

Implement H2_CONVERSATIONAL_REVIEW_MODIFY_V1 / REVIEW-MODIFY-HTTP-LOCAL-1.0
on exactly the 59 paths in the approved preparation inventory (44 new, 15 modified).
The owner's message approves implementation, seven new routes, sixteen CAP-A01
checks, synthetic tests and a bounded local commit only after successful validation.
The unsigned recommendation in the review ZIP is not itself an approval.
Documentation network and every live permission remain NOT_AUTHORIZED.

M04 owns immutable subject/correction/marking bundles and targeted D3 changes.
M09 owns deterministic CAP-A01 checks, with no agent or provider dependency.
M08 owns session commands, exact-version reads, idempotence and atomic publication.
AG03 CAP-G02 and AG04 CAP-V01 remain technical generation and critique authorities
only. New outbound bridges translate their canonical contracts to neutral module DTOs.
No module imports agent_runtime. No agent receives a store, SQL, filesystem or secret.
CAP-R02 and its closed R2 DTO remain unchanged. R3 adds a separate bundle projection.

An absent bundle may be materialized once for an existing immutable subject/version.
A targeted change creates V2 with a stable production reference, an exact V1 parent,
matching correction/marking and a CAP-A01 report before a single atomic publication.
The memory store shares one lock/lease with R2. V1 remains readable and unchanged.
No latest alias, partial publication, automatic promotion, export or durable persistence.

Source monetary scale must be explicitly evidenced before normalization to EUR.
EUR means factor 1; kEUR means factor 1000. Unknown/ambiguous scale fails closed.
180 kEUR must become 180000.00 EUR, never 180.00 EUR. Tests cover both outcomes.
Source values, scale and source locator are retained in the bounded synthetic bundle.
A V1 review never applies to V2: newly published V2 is REVIEW_NOT_RUN.
CAP-A01 PASS is not an official validation; CANDIDATE — NON VALIDÉE remains visible.

## Guard evolution

G01: local_browser_product_boundary — active registry16 and exact R3 inventory,
preserving the closed R2 historical contract and security assertions.
G02: local_search_product_boundary — active count and documentary test fixtures,
with historical R1/R2 counts and negative cases preserved.
G03: resource_ref_contract_fitness — last route-registry assertion only.
G04: security_recovery_observability_e2e_fitness — exact backend owner allowlist
in test_later_provider_work_preserves_phase_f_backend_owners only.
G05: conversation_product_boundary — authenticated R2 closure at the baseline and
separate active R3 checks across HEAD/index/working tree; historical hashes unchanged.
G06: local_browser_product_routes — first count assertion only, 9 to 16.
G07/G08: new independent R3 boundary and mutation/non-regression tests.
The precise mutable function sets are in the approved inventory; no other guard
may be silently changed. Repository hygiene, calibration tooling, HIST020, the
frozen generation adapters, historical manifests and prior preparation stay intact.

## Validation and limitations

Synthetic doubles only; localhost HTTP and bounded fake workers; existing dependencies.
All caches/logs/temporary synthetic fixtures remain outside the repository.
Only tests/non_functional/test_retrieval_quality_real_gate.py may be excluded from
the explicitly approved synthetic suite. That gate stays NOT_RUN / NOT_PASS.
No new skip/xfail, external network, user database/metadata, credentials or provider.
Review and modification results are session-volatile and lost on restart.
The old R2 grant is CONSUMED and its vanished candidate cannot be reconstructed.
A successful synthetic delivery is R3_SYNTHETIC_WIRING_ONLY, not product/live completion.
No automatic live preparation, R4, H3, push or merge.
