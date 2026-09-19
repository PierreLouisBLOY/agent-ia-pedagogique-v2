# R5 — exact selection in the conversation worker

This opt-in extends the delivered R5 selection through M04 / AG02 / AG03 into the
existing supervised worker. No provider operation is enabled merely by installing
the code. R2 defaults, grants and historical source files stay separate.

Prepare an exact selection with `prepare_exact_selection`, then freeze it using
`scope_from_preparation`. Each selected object/passage/version and text checksum is
mandatory. The parent and child re-materialize only those selections through the
existing read-only admission and OP13 path: no generic search or fallback. The
local provenance label is not official authority, regardless of an ID's prefix.

`--r5-scope <private-json> --r5-authorization <private-json>` opts the existing local
entry into R5, with an explicit runtime, root, hash and `--enable-conversation`.
It rejects R2 authority, saved-only and simultaneous R3 execution. No new route.
The exact request is checked before masked input, private IPC and dispatch. The
supervisor reserves the single-use receipt before execution; UNKNOWN cannot be
retried. Receipts contain technical metadata, never text, paths or credentials.

The R5 grant is separate: exact baseline/scope/profile/pricing, explicit live and
transfer approvals, one call, zero retry/fallback, a fresh maximum 30-minute grant,
an independently bound R5 count receipt and a sufficient explicit ceiling. An
UNKNOWN count *outcome* is rejected. An UNKNOWN count *cost* needs a separate
explicit acceptance in this R5 receipt; R2's historical exception is not reused.
Profile/rates remain technical proposals until separately approved for this scope.

Current preparation functions emit canonical semantic GENERATION and COUNT JSON.
Those hashes are not automatically wire-byte hashes. Only an offline capture from
the actual SDK serialization may be labeled CAPTURED_TRANSPORT; any changed prompt,
context, schema or selected text requires new identities and a new applicable count.

Pedagogy: construct a complete solvable dependency chain before choosing guidance.
Preserve STANDARD, duration and objectives, without mapping difficulty to a new enum
or forcing a functional balance already classified. Missing methods or indispensable
data cannot be hidden by easier questions or invented sources. The output remains
the existing subject sections, not a validated R3 correction/marking bundle.

Tests: `test_r5_worker`, `test_r5_worker_guard`, prior R5 selection/boundaries and
the portable conversation/R3/R4 regression set. All fixtures are fresh, synthetic
and external to the checkout. Transport/credentials are artificial doubles.
The numerical fixture reconstructs RS=220, ES=180, FRNG=40, BFR=25 and TN=15 kEUR;
TN agrees with 18-3. This checks one fixture, not general pedagogical quality.

Real source coverage remains a separate assessment. A successful double does not
establish live R5 completion. No count, generation, pilot change or R6–R8/H3 is
authorized by this implementation document. Private grants, projections, excerpts,
exports, databases and evidence archives must never be committed.
