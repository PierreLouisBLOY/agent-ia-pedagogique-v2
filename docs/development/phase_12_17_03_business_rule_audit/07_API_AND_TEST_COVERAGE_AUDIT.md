# Phase 12.17.3 — API and test coverage audit

## Mechanical coverage

The denominator is the `66` raw rule occurrences in `02_BUSINESS_RULE_REGISTER.json`. Percentages are not deduplicated candidate coverage.

| Metric | Count | Percentage | Definition |
|---|---:|---:|---|
| Rules with at least partial implementation | 62/66 | 93.9% | `IMPLEMENTED` or `PARTIAL` |
| Rules fully implemented | 59/66 | 89.4% | `IMPLEMENTED` only |
| Rules with an explicit or structural test | 58/66 | 87.9% | `test_status != NONE` |
| Rules with an explicit test | 55/66 | 83.3% | Direct executable test named in the register |
| Rules with locally verified data mapping | 5/66 | 7.6% | `data_mapping_status = VERIFIED`; non-data rules remain in denominator |
| Data-impacting rules requiring external schema | 9/66 | 13.6% | `EXTERNAL_REQUIRED` |
| API-relevant rules with a contract boundary | 8/11 | 72.7% | Application/agent contract exists, not an HTTP endpoint |
| API-relevant rules with an HTTP `/api/v2` endpoint | 0/11 | 0.0% | No concrete endpoint exists |

There are `59` fully implemented, `3` partially implemented and `4` unimplemented raw rules. The test inventory contains `412` Python test files, but file volume is not used as proof of rule coverage.

## Rules without implementation

| Rule | Gap |
|---|---|
| `BR-003` | Required legacy-reuse trace directory/evidence is absent |
| `BR-015` | READ-15 `version_ref` and `include` options are explicitly deferred |
| `BR-065` | Projected `/api/v2` adapter has no endpoint implementation |
| `BR-066` | CAP-R02, CAP-A01 and CAP-A02 have route metadata but no concrete Application owner |

## Rules without a test

`BR-001`, `BR-002`, `BR-003`, `BR-004`, `BR-015`, `BR-025`, `BR-065`, `BR-066` — **8** rules.

The first four are governance/documentary rules. `BR-025` is a vocabulary ownership problem rather than one check. `BR-015`, `BR-065` and `BR-066` are unimplemented scope and must not receive tests that falsely imply implementation.

## API translation

| Rules | Existing contract | API validation | Domain/Application authority | Divergence |
|---|---|---|---|---|
| `BR-009`, `BR-011`–`BR-013` | Resource DTO/use case/inbound bridge | Exact use-case and payload validation | Yes, Resource Library Application | HTTP adapter absent |
| `BR-015` | Deferred READ-15 contract only | None | Intended Resource Library owner | `version_ref`/`include` absent |
| `BR-030` | Generic Application route contract | Runtime route validation | Application is required authority | Not an HTTP endpoint |
| `BR-053`–`BR-055` | Agent result contracts | Agent boundary validation | Outputs explicitly lack business authority | No API adapter |
| `BR-065` | Projected `/api/v2` statement | None | Must delegate to Application | Endpoint implementation missing |
| `BR-066` | Capability/route metadata | Route-level checks only | Concrete Application owners absent | Metadata could be mistaken for implementation |

The absence of `/api/v2` is recorded as an implementation finding. It does not erase the resource, validation, generation, review or promotion rules.

## Duplicate and structural tests

- Architecture tests validly prove dependency direction, provider neutrality and boundary shape, but do not substitute for behavioural business tests.
- Multiple tests cover the same fail-closed and no-authority invariants at different boundaries. The audit does not classify them as removable duplicates.
- Real-gate SQLite tests demonstrate adapter behaviour against the external seed when the environment provides it; they do not place the DDL in this audit corpus.

No test suite was rerun because this lot changes documentation only. JSON parsing, register consistency, manifest hashes, worktree scope and whitespace are the executable validations for this audit.
