# ADR — R2 conversational generation product boundary

Status: ACCEPTED_FOR_SYNTHETIC_IMPLEMENTATION (owner approval in this conversation).
Reference baseline: 19c42bc9f4b0b1a97b9bd2d6b880acd7378459f7.
Approved source manifest: 359b06ab34aa092831bd0d0eea909fc4b030776eef49414edbe7932f97eb9d6c.
Approved source ZIP: 32da3affbff6c5f7f2ce699bf7b82422adc121c879b16a3e1f1ef4ba5ed93cdb.

## Decision and review before implementation

The owner explicitly approved P_IMPL and P_DOC_NETWORK, C01–C18, the 60 exact
paths (45 CREATE / 15 MODIFY), G01–G10 and a coherent local commit after
successful validations. This ADR records that actual approval; no owner
signature or timestamp is fabricated. The source documents remain immutable.

M07 pedagogical_context owns confirmed context. M04 pedagogical_design owns
the creation command. M08 work_orchestration owns conversation, current
candidate and CAP-R02 exact-version read. HTTP depends only on Application
inbound bridges. Modules never import agent_runtime, SDKs, persistence or HTTP.
Composition binds the existing AG01 workflow selection/compiler, unique
RoutingStepRunner/PlanExecutor, policy/budget, AG02 evidence ports and AG03
GenerationCoordinator/GenerationOutputGuard/ProductionCandidate.

One bounded child supervises the long job; the existing stdlib server remains
single-request and supports polling. Commands use exact-origin/Host/nonce,
closed JSON and raw-byte/deadline bounds. GET has no generative effect.
CAS idempotence and an exclusive technical receipt prohibit replay after
unknown effect or restart. A receipt is not R4 content persistence.

The real working store is process-local and volatile (two hours, three
candidates); CAP-R02 requires the exact production/version pair. Candidate
content is not telemetry. The three existing assets display text only and
preserve READ-15/search. No correction, review, promotion or export is added.
R2 OpenAI mapping is opt-in; legacy generation/correction remains unchanged.

## Approved guard delta

G01–G03: exact nine-route oracle, fixed R2 inventory, historical proof for the
pure HTTP file plus unchanged authorize_request. G04: only final A7 tuple.
G05: one Phase F owner node, exact backend paths AND inventory. G06: cardinality.
G07–G10: R1 historical five routes/30 paths/AST/read-only proof separated from
the active R2 inventory. Only API/CLI local_browser.py are exceptions to the
33 historical read-only dependencies. Other assertions are retained.
The three excerpt decorator tails G06/G08/G10 are not executable source:
actual PRE functions/AST govern. No historical manifest is rewritten.

All 17 historical untracked documents and four preparatory source documents
stay byte-identical and outside the implementation commit. The approved path
list is independently pinned in the active contract and guard.

## Permissions and boundaries

P_IMPL=APPROVED; P_DOC_NETWORK=APPROVED; P_LIVE=NOT_AUTHORIZED.
Only existing dependencies, synthetic newly created SQLite fixtures outside
the repository, loopback sockets, bounded subprocess, volatile stores and
external test caches/logs are permitted. No access to user data, seed/runtime
or sidecars, including metadata; no credential presence check/resolution.
The only global exclusion approved is
tests/non_functional/test_retrieval_quality_real_gate.py.
No new skip/xfail/ignore, install, lock/config change, migration, provider
request, payload counting endpoint, push, merge, R3/R4/H3 is authorized.
The proposed USD 0.140000 ceiling is NOT approved.

## Consequences and proof

The implementation must traverse real agents/ports with explicit test doubles,
prove bounded framing/nonce/idempotence/watchdog/shutdown, retain C08 lineage
and references, and read exact versions without a provider call. Static UI,
manual browser and real model results are separate evidence. Without later
authorized successful live generation, the result is R2_SYNTHETIC_WIRING_ONLY.

Official public documentation may verify the proposed model/pricing/schema
but does not prove the final token bound, account availability or transfer
approval. These remain fail-closed in LIVE_GENERATION_SCOPE.json.
store=false is not a promise of zero provider retention.

This ADR was checked against C01–C18 and the reviewed G01–G10 before code
implementation. It introduces no alternative stack, catalogue, agent,
ProductionCandidate definition, budget engine or general audit.

## Historical implementation stop: C10 / canonical C03 discrepancy (resolved)

The first synthetic WF-4 integration attempt rejected the requested AG02
three-capability delegation before dispatch. The preserved canonical
DelegationEnvelope requires exactly (source_step.capability_id,), at
backend/agent_runtime/contracts/planning/delegation.py:74.
R2 C10 instead requires CAP-E01/E02/E03 in the bounded evidence delegation.
Changing that canonical assertion is outside the approved 60-file inventory.
At that stop no exception or indirect authority bypass had been applied.
The owner amendment below subsequently authorized and resolved this exact delta.
See IMPLEMENTATION_EVIDENCE.md for current actual test results.

## Owner amendment R2-C03-1 (approved in the task)

The owner explicitly answered yes to adding the 61st file, the canonical
contracts/planning/delegation.py, and the bounded AG02 E01/E02/E03 exception,
including this ADR, tests and inventory adjustments. No live permission follows.
The original 60-file preparation and its hashes remain immutable history.

The opt-in is R2-EVIDENCE-MANDATE-1.0, declared both by the compiled evidence
step and its delegation. It applies only to AG01 -> AG02, source CAP-E01,
the exact ordered E01/E02/E03 scope, read only, depth 1, no redelegation,
an explicit equal step/scope budget, zero retries/tools, at most two plan
steps and a deadline/runtime of at most 120 seconds. Existing parent scope
authorization and narrowing remain mandatory. E02 has three fetches maximum;
E01 and E03 each execute once. All non-opt-in delegations remain mono-capability.

This bounded amendment is reviewed before implementation; it changes neither
agent identities, provider authority, canonical seed access nor workflow order.

## Historical global validation stop: generation-source identities

The first global run had 5294 passes, 37 failures and 28 existing skips. One frozen
adapter assertion and 36 V4.2/V5 matrix-derived assertions still hash the current
generation sources as historical identities. At that stop, the exact two-file
delta was reported without application and the scope remained 61 files.
The owner amendment below subsequently authorized this bounded adaptation.
Current validation results are recorded in IMPLEMENTATION_EVIDENCE.md.
Historical matrices/manifests and all live denials remain intact.

## Owner amendment R2-HISTORY-1 (approved before implementation)

The owner explicitly approved the two bounded historical adaptations in this
task. Add test_pedagogical_calibration_fitness.py and repair_tranche_v4_2.py to
the exact inventory: 63 paths, 45 creations and 18 modifications. The source
preparation and all historical manifests remain immutable.

The frozen adapter assertion now authenticates the historical Git blob AND
the closed active R2 source lineage. The V4.2 generation contract uses only
three authenticated blobs at a560d6ca1989ba3dd13c9d02eeb97ef3fff6238b; their
bytes were verified equal to V4.1 and the R2 entry baseline. Review/Scorer
identities remain unchanged. Historical identity reconstruction grants no live
authority: live authorization additionally rejects current generation-source
drift even when a historical matrix can be reconstructed. Non-regressions and
negative mutations are in the already approved T09/T11 files.

No matrix/pricing/carry-forward hash is regenerated. No exclusion or skip is
added. The targeted adaptation passes; the global run resolves the previous
37 failures but identifies two transverse historical-freeze guards below.

## Historical stop R2-HISTORY-2 — subsequently approved

At this earlier stop, the global result was 5351 passed, 2 failed, 28 existing skips. The unchanged
test_calibration_tooling_boundary.py and test_repository_hygiene_b06.py still
require HIST-020 (repair_tranche_v4_2.py) to equal its B01 frozen bytes. The
previous owner amendment did not include those two guard files.

Proposed only: adapt their single failing node each to authenticate the PRE
historical blob plus the closed active R2-HISTORY-1 lineage for HIST-020,
while keeping the other 39 current files byte-exact and all other assertions.
No historical freeze, manifest, ADR or shared historical_hash_freeze.py
helper would change. The exact PRE hashes and proposed 65-path inventory are
recorded in IMPLEMENTATION_EVIDENCE.md. Active authority remains 63 paths.
At that stop, no implementation of this delta, staging or commit was authorized.

## Owner amendment R2-HISTORY-2 (reviewed before implementation)

The owner explicitly approved the two complete paths and their single nodes
recorded in IMPLEMENTATION_EVIDENCE.md, on the same entry baseline and package
manifest. PRE SHA-256 values were rechecked before editing:
43f91d0ea1d631588b76c9646edb8ddba16a771393694d4aa8cda95b2c2e2309 and
1d854e51559244b52c3b062bdfbde410653b8fdeff223deead9334eef5d9acfc.
The active inventory becomes exactly 65 paths: 45 CREATE / 20 MODIFY.

For HIST-020 only, the new R2 proof helper authenticates the original blob
at the fixed B01 baseline and verifies the exact approved active R2-HISTORY-1
helper bytes, in addition to the existing AST and live-denial regressions.
The other 39 entries still require byte-exact current working-tree content.
All historical expected hashes, ordered-set checks, manifests, the old ADR,
and the shared historical_hash_freeze.py remain unchanged. There is no HEAD
fallback, unconditional success, or general exception for historical files.

Only the two approved nodes change in the added files; tests in the existing
T11 file verify unchanged other nodes/constants, reject current/historical
tampering, and reject a 65-path substitution as well as a 66th path. The
fixed-baseline inventory is required to be exact both before and after commit.
AG02, earlier adaptations, the 17 protected documents and four preparatory
sources remain unchanged. No external network is used for this correction.

The inventory also reads the index explicitly against the fixed baseline.
An unauthorized staged delta cannot disappear behind cancelling working-tree
bytes; indexing any protected or preparatory document is refused separately.
The final validation is rerun after this in-scope G02 hardening. It changes
neither the approved paths nor any application source or historical hash.

After all authorized validations pass, the owner authorizes one coherent
local commit of all 65 files. P_LIVE remains NOT_AUTHORIZED; no credential,
user data, migration, dependency, lock, push, merge or H3 permission is added.

Final authorized validation has now succeeded: 5456 passed, 28 preexisting
skips; 397 targeted and 768 reuse tests passed separately. Ruff, mypy backend
(724 files), compilation and dependency checks pass. The source scope remains
65 paths. The authorized local commit binds this validated synthetic snapshot;
it does not grant live authority or establish R2_PRODUCT_COMPLETE.
