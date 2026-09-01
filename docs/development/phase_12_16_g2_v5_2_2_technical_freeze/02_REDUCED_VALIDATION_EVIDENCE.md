# V5.2.2 reduced validation evidence

No global suite was run.

- Targeted pytest: `22 passed in 41.04s`
- Ruff on the modified Python files: `PASS`
- mypy strict, explicit package bases and imports skipped outside the scoped modified
  files: `PASS`
- compileall on the modified Python files: `PASS`
- `git diff --check`: `PASS`
- Strong/Mixed/Weak carry-forward proofs: `3/3 PASS`
- Exact budget: `0.055600 + 0.055600 = 0.111200 USD`
- Live gate default closed: `PASS`
- Provider calls / credentials / transports: `0/0/0`

The non-gating wide mypy traversal reports `33 errors in 15 files`. Those errors are
historical and outside the V5.2.2 modified scope; they are handed to Phase 12.17.
