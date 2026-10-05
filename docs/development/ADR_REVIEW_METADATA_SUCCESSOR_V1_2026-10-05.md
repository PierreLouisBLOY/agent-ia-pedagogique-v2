# ADR — Review metadata successor V1 and diffusion V6

Status: ADOPTED by the owner on 2026-10-05, before implementation.
Entry: ae190232950067e33080d511e3a051e112734d57.
Owner review archive SHA-256: 3882de4afcaed535709bc1fe37fa8c04a863f6159c407d49d0d6e887582746ba.
Decision: GUARD_M01_M03 = USE_SUCCESSOR. No supplier invocation is authorized.

## Review boundary

The shared content scanner and historical metadata rejection function retain their
exact semantics and source bytes. The successor is a pure, versioned policy for
CAP-V01 semantic review materialization. HISTORICAL remains the default; opting
in requires the closed NEGATIVE_AUTHORITY_DIAGNOSTICS_V1 enum at composition.
No provider, scope, hash, model, target or version is whitelisted.

Only root `code` fields of diagnostic objects inside `limitations` and
`uncertainties` may recognize NO_AUTHORITATIVE_ORACLE or
NO_AUTHORITATIVE_BASIS_PROVIDED. The accompanying `message` may recognize the
closed literal absence phrases specified and tested by the successor. The
original payload remains unchanged. Every other key, field and text fragment is
checked by the historical guard. Structural authority, positive claims, mixed
instructions, privilege escalation, exfiltration, tool actions, URLs, nested or
moved codes and ambiguous negatives remain rejected. CAP-V02, findings, warnings,
execution metadata, evidence and source content keep historical protection.
Forged or invalid policy versions fail closed.

M01's old review target is immutable. Offline replay of its received result is
diagnostic only and cannot attach it to the selected successor production.
Replays do not create live reports, pedagogical approval or promotion.

## Presentation boundary

An explicitly selected diffusion-v6 projection composes the existing V5 export.
Old profiles and the default composition remain unchanged. V6 replaces the
literal presentation phrases convention pilote / convention du pilote with
convention de l’exercice, and passage SQLite sélectionné with passage sélectionné
in corrections. Course student pagination may reduce paragraph after-spacing
without changing text, font size, monetary values, answers, grading or originals.
The Application export boundary produces successors from the existing saved
versions. Projection identities are separate from pedagogical version identities.
The qualified recipe composition explicitly selects V6, with no provider binding.

## Acceptance evidence

Positive exact diagnostics and default refusal; mutations of location, authority,
mixed claims, ambiguous language, forged policy and target lineage; unchanged
scanner and historical function identities; exact received-byte offline replay;
V5 byte preservation and V6 deterministic exports, text/numeric comparisons;
affected native Word page rendering; clean package validation; five historical
FAIL replay preserved with their dispositions. No skip/xfail masks are added.
Tests, Ruff, mypy, compileall and diff/secret review precede delivery. Scope
inventory gains exact owners and hashes under this ADR without relaxing guard
logic or the historical CP645 baseline.

The closed review-package inventory adds only review_metadata_successor.py.
All existing members and boundary prohibitions remain required; the inventory
test becomes an exact pinned successor owner with a mutation rejection proof.
The five historical documentary assertions remain unchanged.

## Owner decisions remaining

Teacher recipe and pedagogical acceptance, source sufficiency and final release
remain owner decisions. Historical live evidence and authorizations are preserved.
No new supplier call, push, merge or original database modification is permitted.
