# V5.1 — Reduced validation evidence

No provider, credential or real transport was used.

## Targeted tests

Command scope:

- V5.1 parser/adaptor and telemetry tests;
- canonical V5 scorer tests;
- V5 semantic integration, canary and fail-closed tests;
- V5 transfer-scope and live-gate tests.

Result: `45 passed in 12.85s`.

The V5.1 fixtures cover conforming output, case/space normalization, explicit
alias, unknown enum, ambiguous alias, invalid type, missing field, extra field,
out-of-bound score, invalid JSON, truncated response, privacy-safe failure and
exact cost on parse failure.

## Static validation

- Ruff on modified Python files: `PASS`.
- mypy strict with explicit package bases and skipped imported baseline modules,
  run separately on each modified Python file: `PASS`, one source file each.
- compileall on modified Python files: `PASS`.
- `git diff --check`: `PASS`.

No global test suite was run.
