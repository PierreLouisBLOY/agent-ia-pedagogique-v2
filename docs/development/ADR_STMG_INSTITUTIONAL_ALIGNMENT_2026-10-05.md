# ADR — Exact STMG institutional context

Status: adopted conceptual owner decision; implementation review recorded before code.
Entry: cb0d6df2ebb4070ef0c89108e4005bf118e3e1f1.
Owner mandate: PROJET_V2_MODELE_INSTITUTIONNEL_STMG.zip, SHA-256
d71237aac78f9d65f918fb0cd746911a87d3c8efa2d35da14c55424262a30a1b.

## Existing structures and decision

M01 knowledge_reference owns canonical notions and institutional relationships.
M02 pedagogical_context owns the confirmed teaching context. M03 resource_library
already projects canonical notions through query-only SQLite outbound adapters.
The current P0 context carries only a level and a free-text discipline; its
immutable contract is retained for historical saved productions.

Add a versioned nested institutional context, with exact programme/version,
teaching subject, common/specific component and track. Reuse canonical notion IDs
and authenticated SQLite framework/programme relationships after inspecting their
physical schema through an Application use case. No second notion ontology or
seed migration. Missing institutional provenance stays a CONTENT_GAP, never an
inferred official attachment. Local progression remains separate from programme
theme/question/capacity; implicit or cross-programme attachments cannot become
explicit through propagation.

The institutional resolver and its outbound port belong to knowledge_reference;
the inbound adapter exposes Application DTOs only. SQLite handles and queries
remain in infrastructure/outbound adapters. The inspection use case returns only
bounded institutional schema/projections, never a connection or executable SQL.
All reads validate the existing authenticated target before and after use.

## Consumer compatibility and active policy

Historical P0 context/bundle, saved records, exports and consumed live identities
remain reproducible. New STMG preparation in normal composition requires exact
institutional resolution before planning, retrieval and production. A source
selected by an unscoped label is not sufficient evidence of programme membership.
AG-03 receives the confirmed frame; AG-04 receives the same immutable frame and
an independent alignment expectation. Neither agent gains admission authority.

The explicit versioned COURSE policy requires objectives, explained notions,
method/application and synthesis appropriate to the confirmed depth, without
imposing a page count or transferring an evaluation oracle. Historical COURSE
outputs remain historical. A local successor M01 is a new candidate/version with
its parent and content provenance preserved, not a new live generation or review.

Sources & contexte and new exports display the exact subject/component/track.
Official programme identity/provenance, local progression and pedagogical judgement
are distinct. A verified ministerial reference is not acceptance of generated
content or of every notion association. The 628-notion matrix preserves IDs and
all separate programme attachments, including unresolved gaps.

## Pre-implementation review

The owner supplied seven non-confusable frames and authorised this extension.
Review: the proposal preserves module ownership, inbound Application access,
query-only seed reads, historical identities and generation/validation/quality/
promotion separation. No supplier, credential, new runtime dependency, automatic
enrichment, promotion or merge is introduced. Tests must cover all seven frames,
wrong programme/version/track, implicit propagation, missing provenance, headers,
request/review binding, current consumer guards and historical replay.
Normal composition must refuse an unresolved STMG context before dispatch.
Remaining source gaps and pedagogical acceptance are explicit external decisions.

## Addendum reviewed before the question-selector correction

The owner reported an empty programme-question selector. Authenticated Application
inspection confirms eight SGN questions with no numeric prefix, official code or
parent-theme link. Filtering on an inferred theme silently hid all eight.
Display every exact programme/version question independently of its numbering.
An unresolved theme is represented by null in a draft selection, never by an
invented official identifier. Resolution accepts only the exact selected question
and records THEME_RELATIONSHIP_UNRESOLVED as CONTENT_GAP; generation/review remain
blocked before authorisation. Numbered-theme mismatch checks remain effective.
Context, source drawer and exports explicitly label the unresolved theme.
Review: this correction preserves Application ownership, source identity,
admission gates, original seed and saved contexts, without provider work or a
second ontology. Add positive selector tests and theme-substitution/dispatch
mutations, then verify the real browser selection and Application preparation.
