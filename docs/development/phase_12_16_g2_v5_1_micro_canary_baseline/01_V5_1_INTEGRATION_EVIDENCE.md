# V5.1 micro-canary — Integration evidence

The baseline candidate wires the V5.1 response path as follows:

1. receive a typed Anthropic response;
2. persist token usage, exact cost, stop reason, response hash and length;
3. adapt only explicitly supported response variants;
4. dispatch to the unchanged canonical V5 parser;
5. persist a safe outcome or privacy-safe diagnostic.

The integration is implemented in:

- `semantic_parser_adapter_v5_1.py` for adaptation and telemetry;
- `semantic_micro_canary_v5_1.py` for selection, identity, budget and gates.

No credential resolver or concrete transport is imported. Raw response content is
never persisted.

## Identity impact

- Parser V5.1 SHA-256:
  `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b`
- Canonical scorer SHA-256:
  `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344`
- Canonical matrix SHA-256:
  `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c`
- Call-spec matrix changed: `FALSE`

The outbound call definition and provider payload are unchanged. The dedicated
micro-canary identity binds the existing source call spec to the new local parser
SHA, so no silent reuse of the old parser is possible.
