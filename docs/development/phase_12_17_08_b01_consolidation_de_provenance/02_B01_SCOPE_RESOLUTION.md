# Phase 12.17.8-B01 — Résolution du scope

```text
B01_CANONICAL_TITLE = Consolidation de provenance
B01_FINDINGS = CF-REPO-001
B01_SCOPE_UNAMBIGUOUS = TRUE
B01_SCOPE = REPO_EVIDENCE_CONSOLIDATION
B01_OUT_OF_SCOPE = B02_TO_B07_IMPLEMENTATION
B01_COMMIT_POLICY = ONE_DOCUMENTATION_PROVENANCE_COMMIT_LITERAL_STAGING_NO_PUSH
B02_CANONICAL_TITLE = Frontière locale fichiers et SQLite
```

## In scope

- the owner-bound rebound inventory of 172 files;
- the separately classified seven 12.17.7B gate artifacts;
- the owner-approved B01A corrective evidence package of seven files;
- the owner-approved B01B EOF-normalization evidence package of ten files;
- six personal-locator minimizations: the original five plus `REPO-052`;
- exact rebinding of the two affected manifests;
- the thirteen-file B01 evidence package, including the staging allowlist and its manifest; total literal commit allowlist `209`.

## Out of scope

No application or infrastructure code, configuration, dependency, ignore rule, HTTP contract, observability implementation, SQLite operation, provider operation, deletion, push, merge, B02 work or 12.18 work is included.

## Test gates

Exact inventory and allowlist equality, 19 source/corrective manifest checks plus the B01 manifest, six minimization equivalence checks, zero personal locator, zero secret or database candidate, repository baseline tests, historical freeze guards, targeted/active/backend mypy, Ruff, compileall and staged diff checks.
