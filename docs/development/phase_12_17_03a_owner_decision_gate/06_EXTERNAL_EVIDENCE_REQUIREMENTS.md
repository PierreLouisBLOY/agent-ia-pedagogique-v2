# Phase 12.17.3A — External evidence requirements

## SQLite evidence decisions

`SQLITE_EXTERNAL_EVIDENCE_DECISION_COUNT = 3`

| Decision | Flag | Why | When required |
|---|---|---|---|
| `OD-05` | `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE` | Its subject is verification of the unseen canonical schema | Before any structural equivalence or data-model closure claim |
| `OD-06` | `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE` | Stored vocabulary/constraints must be known before aligning the ten literal families | Before `ALIGN_DATA_MODEL` or migration design |
| `OD-07` | `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE` | Version/include storage semantics are unseen | Only if implementation option C is selected; A/B/DEFER make no schema claim |

The other five decisions do not require SQLite evidence to be decided. Later implementation under `OD-03` or `OD-04` may create a separate schema dependency, but this package does not infer one.

## Minimum acceptable SQLite evidence package

- Owner-supplied absolute locator outside Git.
- Expected SHA-256 and size of the exact canonical seed.
- Read-only connection mode and a guarantee that the seed is never migrated in place.
- Schema metadata only: tables, columns, declared types, nullability, primary/foreign keys, unique/check constraints, indexes, triggers and views.
- Expected inventory reconciliation: `98` tables, `20` indexes, `7` triggers, `2` views, or an explicit owner-approved explanation of variance.
- No row data, document content, source document, local path in published artifacts, credential, secret or personal data.
- A minimized manifest tying each observation to affected `BR-*` and `CR-*` IDs.

If any identity or inventory check fails, evidence use stops and all affected rules remain `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED`.

## Alternative evidence mode

`OD-05 OPTION_C` permits a signed schema-only export rather than direct seed access. It must contain enough structural information to verify the same checks, be hash-bound to the source seed and explicitly exclude row content. An incomplete export cannot be treated as equivalent to the database.

## Other external evidence

| Decision | Evidence | Boundary |
|---|---|---|
| `OD-01` | Original consolidated Phase 1/2 rule corpus, if it exists | Exact locator, hash, provenance and authority; otherwise an explicit owner unavailability declaration |
| `OD-02` | Evidence of the Phase 7 adaptation referenced by Phase 12.15 | Documentary lineage only; no reconstruction of unobserved approval |
| `OD-08` | Phase 12.16 closure identities | Already present in repository; no new provider call or external transfer |

## Prohibited handling

- Do not copy the SQLite database into Git.
- Do not export full rows or documents.
- Do not infer DDL from adapter SQL and call it canonical.
- Do not resolve provider credentials or make provider calls.
- Do not apply a migration during evidence collection.
- Do not use external evidence to start 12.17.4 before all eight attestations are complete.
