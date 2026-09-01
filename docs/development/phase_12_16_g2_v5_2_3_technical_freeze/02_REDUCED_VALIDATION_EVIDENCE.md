# V5.2.3 reduced validation evidence

No global suite and no wide mypy traversal were run.

| Validation | Result |
|---|---|
| V5.1 parser remediation, V5.2 semantic gate, V5.2.2 pairwise runner and V5.2.3 bound tests | `41 passed in 57.03s` |
| Ruff on modified and adjacent pairwise files | `PASS` |
| mypy `--strict --follow-imports=skip` on the two V5.2.3 Python files | `PASS` |
| compileall on the two V5.2.3 Python files | `PASS` |
| Pre-stage `git diff --check` | `PASS` |
| Synthetic 191-character reproduction | `PASS` |
| Boundaries 180/181/191/255/256 and fail-closed 257 | `PASS` |
| No truncation | `PASS` |
| Nested candidates and ambiguous representation | `PASS / FAIL_CLOSED` |
| Carry-forward proof | `3/3 PASS` |
| Budget `0.055600 + 0.055600` | `0.111200 PASS` |
| Default live gate | `CLOSED` |

The broader historical debt remains `33 errors / 15 files` and is not a gate for
this bounded freeze.

`PROVIDER_CALLS = 0`

`GLOBAL_SUITE = NOT_RUN_BY_DESIGN`
