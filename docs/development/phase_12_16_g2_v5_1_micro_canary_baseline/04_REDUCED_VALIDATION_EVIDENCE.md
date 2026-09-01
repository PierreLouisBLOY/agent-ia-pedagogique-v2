# V5.1 micro-canary — Reduced validation evidence

No provider, credential, concrete transport or global suite was used.

## Targeted tests

The reduced set covers:

- V5.1 adapter/parser compatibility;
- usage-before-parse and exact cost on parse failure;
- micro-canary selection and integrated response processing;
- call-spec and projection hashing;
- exact budget calculation;
- every frozen pre-credential identity;
- canary/fanout fail-closed behavior;
- transfer-scope compliance;
- live gates closed by default.

Result: `52 passed in 15.40s`.

## Static checks

- Ruff on four V5.1 Python files: `PASS`.
- mypy strict, explicit package bases and skipped imported baseline modules,
  separately on all four V5.1 Python files: `PASS`.
- compileall on all four V5.1 Python files: `PASS`.
- `git diff --check`: `PASS`.

Provider calls, credentials and transports: `0 / 0 / 0`.
