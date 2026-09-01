# Reduced validation evidence

No global suite and no provider call were run.

| Validation | Result |
|---|---|
| Synthetic 191-character V5.2.2 reproduction | `PASS` |
| Boundaries 180/181/191/255/256/257 and no truncation | `PASS` |
| Nested candidate A/B and ambiguous mixed representation | `PASS` |
| Call spec, projection, matrix, pricing, gate, scope and anchor identities | `PASS` |
| Carry-forward and exact two-call budget | `PASS` |
| Safe usage-before-parse and raw absence | `PASS` |
| Targeted pytest | `41 passed in 52.64s` |
| Ruff, modified/adjacent scope | `PASS` |
| mypy `--strict --follow-imports=skip`, two modified Python files | `PASS` |
| compileall, two modified Python files | `PASS` |
| `git diff --check` | `PASS` |
| Live closed | `PASS` |

Targeted pytest scope:

- `tests/unit/test_pedagogical_calibration_v5_1_parser_remediation.py`
- `tests/unit/test_pedagogical_calibration_v5_2_semantic_gate.py`
- `tests/unit/test_pairwise_runner_v5_2_2.py`
- `tests/unit/test_pairwise_output_contract_v5_2_3.py`

The broad historical mypy debt remains `33 errors / 15 files` and is deferred to
Phase 12.17. It was not rerun or reclassified in this bounded remediation.

`PROVIDER_CALLS = 0`

`GLOBAL_SUITE = NOT_RUN_BY_DESIGN`
