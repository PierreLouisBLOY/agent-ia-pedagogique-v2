"""R3 uses the existing generic section transport; no edits to frozen R2 mapping."""
import json
from collections.abc import Mapping

from backend.adapters.outbound.generation.parse_diagnostic import (
    ParseCode,
    ParseDiagnostic,
    ParseStage,
)
from backend.agent_runtime.agents.generation import GenerationPort
from backend.infrastructure.composition.bindings.r3_agents import transform
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    AssessmentRevisionRequest,
)


def parse_revision_result(payload: Mapping[str, object], *,
                          diagnostic: ParseDiagnostic | None = None) -> Mapping[str, object]:
    trace = diagnostic if diagnostic is not None else ParseDiagnostic(enabled=False)
    with trace.capture():
        return _parse_revision_body(payload, trace)


def _parse_revision_body(payload: Mapping[str, object], diagnostic: ParseDiagnostic) -> Mapping[str, object]:
    diagnostic.begin(ParseStage.OUTPUT_EXTRACT)
    value = payload.get("sections")
    try:
        sections = object_data(value, {"R3_RESULT_JSON"})
    except ValueError:
        diagnostic.fail(ParseCode.STRUCTURED_OUTPUT_MISSING if value is None
                        else ParseCode.TYPE_MISMATCH if not isinstance(value, Mapping)
                        else ParseCode.REQUIRED_FIELD_MISSING if "R3_RESULT_JSON" not in value
                        else ParseCode.SCHEMA_VALIDATION_FAILURE)
        raise
    diagnostic.begin(ParseStage.TEXT_EXTRACT)
    raw = sections["R3_RESULT_JSON"]
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 128 * 1024:
        diagnostic.fail(ParseCode.TYPE_MISMATCH if not isinstance(raw, str)
                        else ParseCode.CARDINALITY_INVALID)
        raise ValueError("R3_GENERATION_OUTPUT")
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        output: dict[str, object] = {}
        for key, value in values:
            if key in output:
                diagnostic.fail(ParseCode.SCHEMA_VALIDATION_FAILURE)
                raise ValueError("R3_DUPLICATE_KEY")
            output[key] = value
        return output
    def invalid(value: str) -> object:
        diagnostic.fail(ParseCode.SCHEMA_VALIDATION_FAILURE)
        raise ValueError("R3_NON_FINITE")
    def depth(value: object, level: int = 0) -> None:
        if level > 16:
            diagnostic.fail(ParseCode.CARDINALITY_INVALID)
            raise ValueError("R3_DEPTH")
        if isinstance(value, dict):
            for item in value.values():
                depth(item, level + 1)
        elif isinstance(value, list):
            for item in value:
                depth(item, level + 1)
    with diagnostic.at(ParseStage.JSON_DECODE, expected=(json.JSONDecodeError,),
                       code=ParseCode.JSON_DECODE_FAILURE):
        data = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    diagnostic.begin(ParseStage.SCHEMA_VALIDATE)
    depth(data)
    with diagnostic.at(ParseStage.DOMAIN_MAP, expected=(TypeError, ValueError),
                       code=ParseCode.DOMAIN_MAPPING_FAILURE):
        return object_data(data)


class AssessmentRevisionAdapter:
    def __init__(self, port: GenerationPort) -> None:
        self._port = port
        self._parse_diagnostic = ParseDiagnostic(enabled=False)

    def parse_diagnostic(self) -> dict[str, str | None]:
        """Private inner-parser snapshot; not an Application return value."""
        return self._parse_diagnostic.snapshot()

    def propose(self, request: AssessmentRevisionRequest) -> Mapping[str, object]:
        self._parse_diagnostic = ParseDiagnostic(enabled=request.operation in {"PREPARE_SUPPLEMENTS", "HARDEN_DOSSIER_3"})
        return parse_revision_result(transform(self._port, request), diagnostic=self._parse_diagnostic)
