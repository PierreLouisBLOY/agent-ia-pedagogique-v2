# V5.1 mini-pilot — Reduced validation evidence

No provider, credential, transport, live call, retry, rerun, or global test suite
was used.

## Targeted tests

The reduced V5/V5.1 set covers:

- mini-pilot selection and exact methodological minimum;
- strict micro-canary carry-forward equality and drift rejection;
- low/intermediate/strong and multi-scenario coverage;
- pairwise selection and false-tie rejection;
- call-spec and transfer-projection hashes;
- exact per-call and aggregate budget;
- evidence-first and transfer-provenance gates;
- sequential fail-closed behavior and live gate closed;
- existing V5 scorer, integration, transfer-scope, parser and micro-canary
  regressions.

Result: `60 passed in 30.83s`.

## Static validation

- Ruff on the two modified Python files: `PASS`.
- mypy strict with explicit package bases and skipped imported baseline modules,
  separately on both modified Python files: `PASS`.
- compileall on both modified Python files: `PASS`.
- `git diff --check`: `PASS`.

Provider calls / credentials / transports: `0 / 0 / 0`.
