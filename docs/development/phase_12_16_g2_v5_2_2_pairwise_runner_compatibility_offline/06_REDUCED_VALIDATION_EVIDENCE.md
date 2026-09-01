# Reduced validation evidence

Only V5.2/V5.2.2 targeted validation was executed.

- Pytest: `22 passed in 38.21s`
- Exact fixed-runner extraction for both pairwise payloads: `PASS`
- Ruff on the adapter, tests and local runner: `PASS`
- mypy strict on the three modified Python files with explicit package bases and
  imports skipped outside the scoped files: `PASS`
- compileall on the three modified Python files: `PASS`
- Carry-forward audit against the actual safe report/ledger: `3/3 PASS`
- Pairwise call-spec/projection identity preservation: `PASS`
- Proposed budget `0.111200 USD`: `PASS`
- Live flag closed: `PASS`
- Provider calls / credentials / transports: `0/0/0`
- Global test suite: `NOT RUN`

A preliminary strict mypy traversal through imported historical calibration modules
reported 33 pre-existing errors in 15 untouched files. No PASS is claimed for that
broader traversal, and no unrelated file was changed. The required strict scoped
check on modified files passed.

`git diff --check = PASS`
