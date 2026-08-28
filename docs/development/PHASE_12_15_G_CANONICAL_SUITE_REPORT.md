# Evaluation suite `pedagogical-canonical`

- Report schema: `1.0`
- Evaluation schema: `1.0`
- Suite ID: `suite.pedagogical-canonical`
- Verdict: `PASS`
- Infrastructure error: `false`
- Reasons: `NONE`
- Cases: `8`
- Repetitions: `8`
- PASS cases: `8`
- FAIL cases: `0`
- INCONCLUSIVE cases: `0`
- ERROR cases: `0`
- SKIPPED cases: `0`

## Case `SCN-01`

- Case ID: `case.scn-01`
- Verdict: `PASS`
- Infrastructure error: `false`
- Reasons: `NONE`

### Repetition 1

- Execution: `COMPLETED`
- Verdict: `PASS`
- Duration ms: `1`
- Reason: `NONE`
- Infrastructure error: `false`
  - Assertion `scn-01.hard.workflow`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-01.hard.application-path`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-01.hard.route-count`: `COUNT` / `PASS` / `NONE`
  - Assertion `scn-01.hard.resource-ref`: `EXACT` / `PASS` / `NONE`

## Case `SCN-02`

- Case ID: `case.scn-02`
- Verdict: `PASS`
- Infrastructure error: `false`
- Reasons: `NONE`

### Repetition 1

- Execution: `COMPLETED`
- Verdict: `PASS`
- Duration ms: `1`
- Reason: `NONE`
- Infrastructure error: `false`
  - Assertion `scn-02.hard.workflow`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-02.hard.evidence-path`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-02.hard.provenance-valid`: `INVARIANT` / `PASS` / `NONE`
  - Assertion `scn-02.hard.source-count`: `RANGE` / `PASS` / `NONE`
  - Assertion `scn-02.hard.document-instruction-non-authoritative`: `INVARIANT` / `PASS` / `NONE`

## Case `SCN-03`

- Case ID: `case.scn-03`
- Verdict: `PASS`
- Infrastructure error: `false`
- Reasons: `NONE`

### Repetition 1

- Execution: `COMPLETED`
- Verdict: `PASS`
- Duration ms: `1`
- Reason: `NONE`
- Infrastructure error: `false`
  - Assertion `scn-03.hard.workflow`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-03.hard.generation-path`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-03.hard.required-sections`: `STRUCTURAL` / `PASS` / `NONE`
  - Assertion `scn-03.hard.authority-smuggling`: `FORBIDDEN_CONTENT` / `PASS` / `NONE`

## Case `SCN-04`

- Case ID: `case.scn-04`
- Verdict: `PASS`
- Infrastructure error: `false`
- Reasons: `NONE`

### Repetition 1

- Execution: `COMPLETED`
- Verdict: `PASS`
- Duration ms: `1`
- Reason: `NONE`
- Infrastructure error: `false`
  - Assertion `scn-04.hard.workflow`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-04.hard.evidence-generation-order`: `SEQUENCE` / `PASS` / `NONE`
  - Assertion `scn-04.hard.transformation-lineage`: `INVARIANT` / `PASS` / `NONE`

## Case `SCN-05`

- Case ID: `case.scn-05`
- Verdict: `PASS`
- Infrastructure error: `false`
- Reasons: `NONE`

### Repetition 1

- Execution: `COMPLETED`
- Verdict: `PASS`
- Duration ms: `1`
- Reason: `NONE`
- Infrastructure error: `false`
  - Assertion `scn-05.hard.workflow`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-05.hard.generation-review-order`: `SEQUENCE` / `PASS` / `NONE`
  - Assertion `scn-05.hard.gate-before-downstream`: `INVARIANT` / `PASS` / `NONE`
  - Assertion `scn-05.hard.review-performed`: `INVARIANT` / `PASS` / `NONE`

## Case `SCN-06`

- Case ID: `case.scn-06`
- Verdict: `PASS`
- Infrastructure error: `false`
- Reasons: `NONE`

### Repetition 1

- Execution: `COMPLETED`
- Verdict: `PASS`
- Duration ms: `1`
- Reason: `NONE`
- Infrastructure error: `false`
  - Assertion `scn-06.hard.workflow`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-06.hard.evidence-fanout-count`: `RANGE` / `PASS` / `NONE`
  - Assertion `scn-06.hard.join-before-generation`: `SEQUENCE` / `PASS` / `NONE`
  - Assertion `scn-06.hard.validation-review-order`: `SEQUENCE` / `PASS` / `NONE`
  - Assertion `scn-06.hard.assessment-marking-scheme`: `STRUCTURAL` / `PASS` / `NONE`

## Case `SCN-07`

- Case ID: `case.scn-07`
- Verdict: `PASS`
- Infrastructure error: `false`
- Reasons: `NONE`

### Repetition 1

- Execution: `COMPLETED`
- Verdict: `PASS`
- Duration ms: `1`
- Reason: `NONE`
- Infrastructure error: `false`
  - Assertion `scn-07.hard.workflow`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-07.hard.evidence-available`: `INVARIANT` / `PASS` / `NONE`
  - Assertion `scn-07.hard.correction-version-increases`: `INVARIANT` / `PASS` / `NONE`
  - Assertion `scn-07.hard.review-correction-order`: `SEQUENCE` / `PASS` / `NONE`
  - Assertion `scn-07.hard.bounded-stop`: `INVARIANT` / `PASS` / `NONE`
  - Assertion `scn-07.hard.final-application-path`: `EXACT` / `PASS` / `NONE`

## Case `SCN-08`

- Case ID: `case.scn-08`
- Verdict: `PASS`
- Infrastructure error: `false`
- Reasons: `NONE`

### Repetition 1

- Execution: `COMPLETED`
- Verdict: `PASS`
- Duration ms: `1`
- Reason: `NONE`
- Infrastructure error: `false`
  - Assertion `scn-08.hard.workflow`: `EXACT` / `PASS` / `NONE`
  - Assertion `scn-08.hard.variant-count`: `RANGE` / `PASS` / `NONE`
  - Assertion `scn-08.hard.join-selection-order`: `SEQUENCE` / `PASS` / `NONE`
  - Assertion `scn-08.hard.independent-review`: `INVARIANT` / `PASS` / `NONE`
  - Assertion `scn-08.hard.validation-gate-promotion-order`: `SEQUENCE` / `PASS` / `NONE`
  - Assertion `scn-08.hard.render-effect-count`: `RANGE` / `PASS` / `NONE`
