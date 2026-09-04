# Phase 12.17.3 — Data-model translation audit

## Evidence boundary

The repository contains runtime adapters and additive migration metadata, but not the DDL of the reported canonical SQLite seed (`98` tables, `20` indexes, `7` triggers, `2` views). The audit therefore does not infer constraints from table or column names.

`EXTERNAL_SCHEMA_EVIDENCE_REQUIRED_RULE_COUNT = 9`

Affected rules: `BR-014`, `BR-016`, `BR-017`, `BR-020`, `BR-021`, `BR-022`, `BR-024`, `BR-025`, `BR-052`.

## Structural translation matrix

| Concept | Domain/Application owner in repository | Adapter/storage evidence | Database constraint verifiable here | API evidence | Assessment |
|---|---|---|---|---|---|
| Notion | No concrete business module | SQLite runtime store | No; external schema required | None | Adapter implements reads/writes with literals; owner absent |
| Document | No concrete business module | SQLite runtime store and SHA migration | Only additive SHA migration is local; base DDL external | None | Partial structural verification |
| Resource | Resource Library port, DTO and `GetResourceQuery` | `SQLiteResourceStoreAdapter` | Mapping visible; base DDL external | Inbound Application bridge only | Only end-to-end Application-owned slice |
| Context | No concrete business module | SQLite runtime store | No; external schema required | None | Persistence precedes business owner |
| Session/task/production | No concrete business module | SQLite runtime store | No; external schema required | Agent/runtime contracts only | Lifecycle literals require owner |
| Validation | No concrete validation module | SQLite runtime store | No; external schema required | Agent/runtime contracts only | `RUNTIME_CONTRACT`/`PASS` literals are adapter-owned |
| Quality | No concrete quality module | SQLite runtime store | No; external schema required | Review contracts only | `COMPLETED`/`1.0` defaults are adapter-owned |
| Promotion | No concrete promotion module | SQLite runtime store | No; external schema required | Route metadata only | Promotion persistence exists without Application owner |
| Audit | No concrete audit business module | SQLite runtime store | No; external schema required | Runtime observability only | Event type/actor/payload defaults are adapter-owned |

## Verified local invariants

- The seed is opened read-only for inspection, copied to a distinct runtime path, then migrated.
- Migrations are ordered, checksum-validated and transactional.
- The local migration adds document hash provenance and rejects invalid migration state.
- Resource mapping returns a transport-neutral `ResourceRecord` rather than a `sqlite3.Row`.
- Transaction and optimistic transition semantics are exercised by integration tests.

These statements verify adapter behaviour, not the complete external schema.

## Implementations without a documented business rule owner

Ten distinct literal/default families are embedded in `backend/adapters/outbound/persistence/sqlite.py` without a corresponding consolidated Domain/Application vocabulary:

1. notion language/status: `fr`, `CANONICAL`;
2. document type/language/status: `OTHER`, `fr`, `ACTIVE`;
3. resource type/status: `OTHER`, `CANONICAL`;
4. context source: `runtime`;
5. session status: `ACTIVE`;
6. task type/ref/status: `RUNTIME_CONTRACT`, `contract`, `COMPLETED`;
7. production type/title/status: `OTHER`, `runtime production`, `VALIDATED`;
8. validation type/status/validator: `RUNTIME_CONTRACT`, `PASS`, `sqlite adapter`;
9. quality/promotion defaults: `COMPLETED`, `1.0`, `PROMOTED`, `runtime contract`;
10. audit event/actor/payload: `RUNTIME_PORT_CONTRACT`, `sqlite adapter`, `{}`.

This count is of **implementation literal families**, not raw registered rules. They are not declared wrong; their business ownership and canonical vocabulary are undocumented.

## Required external verification

A future read-only evidence step must compare the exact authorized seed hash and DDL against:

- foreign keys and uniqueness supporting identity rules;
- check constraints or reference vocabularies supporting statuses;
- transition/audit columns supporting optimistic concurrency and lineage;
- nullability and indexes supporting Resource Library guarantees;
- additive migration preconditions.

Until then, every affected mapping remains `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED`; absence of local DDL is not evidence that the rule is absent.
