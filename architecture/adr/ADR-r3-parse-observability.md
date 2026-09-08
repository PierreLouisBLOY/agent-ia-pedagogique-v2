# ADR — R3 parse observability, version 1

Status: accepted for offline implementation following the owner's explicit
approval of the three-guard extension (reply `oui`, 2026-09-08).
Baseline: `7e851503a78962cb04f0089bd0a01fdbafb29b70`.
Approved pre-inventory SHA-256:
`c91e2ae135c884e6049b0442982015b55f7fe58a8ee39c0b8fc1135484032d08`.
Reviewed guard proposal SHA-256:
`ba7ef240abeec99e916b51a9c61067b7e5b2d5450e60be296d34077010a8c4f0`.

## Decision and boundary

Instrument the existing outer response parser and inner R3 JSON parser at their
existing failure sites. A provider-independent, in-memory diagnostic retains only
closed stage, code, status and the constant PREPARE_SUPPLEMENTS_V1 target. No raw
value, received key, exception, traceback, prompt or provider identifier is retained.
The first failure wins. Non-failed states have a null code (not an additional code).
Unexpected exceptions map to UNCLASSIFIED_PARSE_FAILURE without inspecting them.
Concrete adapters expose a private snapshot; no port, HTTP response, application
DTO, event log, agent authority or public route acquires this diagnostic.

No acceptance rule, coercion, repair, request, prompt, model, business schema,
CAP-A01, bundle, CAS, versioning or publication behavior changes. Parsing failure
still aborts before CAP-A01 and bundle publication. Refusal and incomplete results
retain their existing meanings. Only PREPARE_SUPPLEMENTS is labelled by this
diagnostic; other operations retain an UNKNOWN, non-executed diagnostic.
Persistence is explicit and private, outside the repository, before service close.
No consumed runner or historical evidence is rewritten.

## Exact repository delta

Modify two adapters: generation/openai/adapter.py and generation/assessment_revision.py.
Create generation/parse_diagnostic.py under backend/adapters/outbound.
Create tests/unit/test_r3_parse_observability.py and
tests/integration/test_r3_parse_observability.py.
Create tests/support/r3_parse_observability_guard.py and this ADR.
Evolve only active_inventory/assert_guard_scope in tests/support/r3_guard_oracle.py;
assert_r2_generation_source_lineage in tests/architecture/test_conversation_product_boundary.py;
test_exact_closed_inventory_owners_and_protected_identities in
tests/architecture/test_r3_product_boundary.py. Total: ten repository paths.

Historical oracles, constants, manifests and guards outside these exact symbols
stay intact. A separate versioned oracle authenticates the successor, its closed
inventory and the AST outside approved guard symbols. Mutation tests must reject
unapproved files, constants, functions and hidden staged changes. This does not
exempt the API or any historical lineage check.

## Verification and limits

Synthetic tests exercise all six stages and eleven failure codes, original error
behavior, privacy, nominal CAP-A01 and failed-output non-publication. Use existing
dependencies, external caches/fixtures, lint, strict backend typing, compilation
and exact diff/hash checks before one coherent local commit.
Repository and private pytest sessions have separate explicit rootdir/confcutdir;
use --import-mode=importlib for the two approved equal-basename test files.
No real database, credential, network, provider/count call, retry, push, merge or live authorization.
The historical fine-grained failure cause remains unknown: no raw output exists
from which to reconstruct it. A subsequent live call needs a separate decision.
