# Canonical SQLite reference - CP645

`CP645.json` identifies the unique canonical seed. The binary, runtimes, backups and
private audit evidence must stay outside Git. Former seed identities are provenance,
not an authentication fallback. The seed/runtime and Evidence boundaries in
ADR-P12-056 and ADR-P12-057 remain unchanged; their historical inventories describe
the former seed, not CP645.

Before updating the constants, a readonly, immutable comparison of the two authenticated
seeds found 23 added tables, three explicit indexes and nine views; no old schema object
was removed or changed. CP645 retains 628 CANONICAL and nine MERGED notion rows. Its
210 APPROVED formula rows do not approve methods or proposed relations by transitivity.

Resolve paths with the existing `PROJET_V2_CANONICAL_DB`, `PROJET_V2_RUNTIME_DB` and
`PROJET_V2_DATA_DIR` contract. Keep process overrides explicit; do not overwrite an
existing user runtime or replace its seed implicitly. Authenticate size and checksum
before any seed inspection; inspect with read-only + immutable. Provision a fresh
runtime with the existing allowlisted migration registry, not raw SQL copied from
the handoff. Preserve the seed and sidecars before/after, and create a verified backup.

The handed-off migration smoke-test runtime is not a seed or a replacement for a
local run. A new runtime may have a different binary checksum due to its migration
ledger. Its identity and backup checksum belong in private run evidence, not in
the canonical seed manifest.

Offline tests: `tests/unit/test_cp645_reference_manifest.py` checks documentary/code
consistency. Real Evidence/seed/runtime checks require the exact local CP645 file;
synthetic fixtures are not evidence that this file was read. Retrieval quality and
METHOD admission remain separate gates; no provider is needed for this integration.
