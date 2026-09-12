# Local editorial correction, authenticated scope and atomic publication

Status: ACCEPTED for synthetic implementation only (owner E01-E04).

Source proposal manifest: c70fe5ffde64239f363dc190bd386e1444793b6b652cb062ee881e568d7992f8.
Scope: 31 exact paths, 23 modifications and 8 creations. No pilot content or grant is stored here.

## Decision

APPLY_REVIEW_EDITORIAL_F01_F02 / R3-EDITORIAL-CORRECTION-1.0 is a local
Application sub-operation of modifications, not a provider transformation. M04
owns the closed plan and local assembly; M09 owns the exact validation scope and
CAP-A01; M08 owns authenticated orchestration and publication. No new route,
capability, persistence or agent access to the store is introduced.

The parent remains immutable. Only the two approved answer texts, their two
dependent locators, three version references and prescribed lineage may differ.
All other keys, values and array order remain equal. The pure locator function
is injected by composition; business modules do not import an OpenAI adapter.

Local lineage uses source_capability=null, instruction_sha256=raw plan hash,
and eight existing keys. LOCAL_DETERMINISTIC_M04 lives in an external scope.
Null, a hash, approved JSON or a structurally copied receipt is never authority.
The private composition verifier recognizes independently authenticated evidence
by identity and exact session/baseline/plan/review bindings. No verification IO
occurs in business modules. Without explicit injection the operation refuses.

The typed scope binds parent, actual child, command, operation and evidence.
Its factory seals a private verifier closure after independently checking the
evidence; structural copies are not sealed. This is an in-process trust boundary
against untrusted input, not a cryptographic signature or a defence against
arbitrary trusted Python code. The verifier must be supplied by the authorized
composition, never deserialized from a document or supplied over HTTP.

Only A14 receives the new editorial branch. Its historical HARDEN comparison
and A01-A13/A15/A16 remain unchanged. Missing or forged scope refuses, with no
parent=None fallback. Revalidation retrieves the exact published capsule and
true parent. A HARDEN child cannot inherit its parent's editorial permission.

The store prepares all copies before publication under its existing RLock:
child, bundle, CAP report, receipt, current candidate, scope and consumed plan.
No child without proof, no orphan proof, no second publication of a consumed
plan. Identical command replay returns the existing receipt. Reservations may
have effects even when publication fails; uncertain completion never implies
automatic retry. Close clears scope and revokes the verifier closure.

Limits stay three versions, eight reports/version and 64 commands. A child is
CANDIDATE / NON VALIDÉE / REVIEW_NOT_RUN; CAP is not pedagogical approval.
Findings and prior reviews are not rewritten or inherited.

## Explicit exclusions and verification

The existing poll/DIAGNOSTIC_CODES dependency-error restitution gap is separate.
The accepted scope includes its exact three-path atomic-scope extension, not a
registry or HTTP expansion. Historical guard tables remain unchanged; a new
authenticated successor oracle verifies exact bytes, symbols and preserved A14.
Named synthetic tests cover the full diff, authority forgery, no provider,
Unicode locators, CAP, lease/CAS/idempotency, failure atomicity, revalidation and
HARDEN succession. Local commit requires actual passing checks and scope review.

E05-E10 are not authorized: no historical session reconstruction, pilot V1
application, pilot V2/V3, findings closure, SQLite, credential, external network,
count or provider call. No push, merge, R4 or H3. Real application requires a new
approval binding the resulting implementation baseline and exact private plan.
