# V5.1 — Privacy-safe parser diagnostics

Every V5.1 parser failure exposes a closed safe diagnostic containing:

- error code;
- field or JSON path;
- expected and observed type;
- expected enum, bound or invariant;
- allowlisted scalar value, or `observed_value_sha256`;
- observed length;
- in-memory SHA-256 of the complete response;
- Anthropic stop reason;
- parser/schema status.

Only short enum-like tokens and integer score values may appear directly. Check
identifiers, evidence, rationale, arbitrary objects and invalid JSON content are
represented by a hash. The exception stores only the safe diagnostic.

The response-processing record contains `raw_response_persisted = false` and
never contains `output_text`. Tests use a unique pedagogical rationale and prove
that it appears in neither the pre-parse snapshot nor the failure snapshot.

`RAW_RESPONSE_PERSISTENCE = NONE`.
