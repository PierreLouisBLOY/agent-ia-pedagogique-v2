# ADR — R3 PREPARE producer contract alignment

Status: accepted for offline implementation by the owner's explicit `oui`
following the exact preinventory and targeted guard-extension request.
Baseline: `81592e82aece8e41eb446e5701de3e83e86978c4`.
Preinventory SHA-256: `9e80e8adcbf280ae5db4a6928458700f1ac4ef4e2086da227e3137b9a4406aeb`.

## Proven gap

`OUTPUT_SCHEMA_FIELD_DRIFT`: the generic provider schema only required a
`R3_RESULT_JSON` string inside an envelope. Its decoded business fields were
not constrained by that schema. Synthetic missing, additional, renamed and
wrapped objects passed the producer contract but failed the unchanged
`assemble_revision` exact-field gate. This proves the contract gap; the exact
contents of the historical failed provider response remain unknown.

## Decision and boundaries

Only TRANSFORM / PREPARE_SUPPLEMENTS / ASSESSMENT with
R3-TRANSFORMATION-1.0 and the exact R3_RESULT_JSON section uses a dedicated,
closed provider schema. Its root properties and required fields are exactly
questions, correction, marking, case_data and limitations. Nested structures
mirror the existing bundle/CAP-A01 data contract; local decoding rejects extra
or missing keys, wrappers, duplicate keys, non-finite numbers and wrong types.

The adapter serializes the validated object losslessly into the established
internal R3_RESULT_JSON transport. It does not unwrap, rename, drop or invent
fields. Refusal, failed and incomplete provider responses cannot become a
successful PREPARE. Validation and publication authority stay in Application
and CAP-A01. No change to business rules, monetary conversion, CAS, versioning,
review identity, publication, HARDEN, generic generation or R2 is permitted.

The only existing functions changed are:

- mapping.py: build_openai_request;
- adapter.py: _map_response_body;
- integration/test_r3_parse_observability.py: SyntheticResponsePort.generate;
- support/r3_parse_observability_guard.py: active_source_matches,
  assert_guard_extension, patch_violations, assert_patch_git_state;
- support/r3_guard_oracle.py: active_inventory;
- architecture/test_r3_product_boundary.py:
  test_exact_closed_inventory_owners_and_protected_identities;
- unit/test_r3_parse_observability.py:
  test_every_patch_source_mutation_is_rejected.

The five creations are this ADR, outbound/generation/openai/prepare_contract.py,
unit and integration test_r3_prepare_contract_alignment.py, and
support/r3_prepare_contract_alignment_guard.py. Prefixes are backend/adapters
for the module and tests for test/support paths. Total: exactly twelve files.

## Successor identity verification

A separate versioned oracle authenticates every new successor source, its own
AST identity, the exact twelve-file diff and staged bytes. It verifies PRE
identities against the immutable baseline and AST equality outside approved
functions. Original parse-observability PRE, POST and oracle constants, R3
inventory, protected documents and historical manifests remain unchanged.
Only the two approved producer files receive successor source authentication;
other protected source equality remains enforced. Missing, extra, same-count
substitution, source and index mutations must fail closed.

## Verification and live boundary

Tests cover exact schema, all five missing fields, extra/wrapped/duplicate and
malformed output, lossless parser-to-assembler traversal, CAP-A01 reachability,
failed-output non-publication and unaffected operations. Tests use synthetic
fixtures, volatile stores and an offline firewall. Caches/proofs remain outside
Git. Ruff, mypy, compileall, diff checks and useful R3 regression are required.

Rebuild PREPARE and counting requests locally. If either identity changes,
NEW_COUNT_REQUIRED is true; no count or provider request is authorized by this
ADR. Historical count receipt and consumed live authorizations are not rebound.
Commit only the exact twelve files after validation; no push, merge, R4 or H3.
