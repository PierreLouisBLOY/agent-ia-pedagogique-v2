"""Pure HARDEN create/count bytes; no credential, count call or dispatch."""

import json

from backend.adapters.outbound.generation.openai.harden_contract import (
    HARDEN_CONTRACT_ID,
    harden_output_schema,
)
from backend.adapters.outbound.openai.contracts import OpenAIReasoningEffort, OpenAIResponsesRequest
from backend.adapters.outbound.openai.schema import lower_openai_strict_schema
from backend.infrastructure.composition.factories.r3_harden_profile import validate_harden_profile
from backend.infrastructure.config.schemas.provider import ModelProfileConfig


def r3_harden_request_parameters(
    request: OpenAIResponsesRequest, *, model_profile: ModelProfileConfig
) -> dict[str, object]:
    validate_harden_profile(model_profile)
    if (
        request.model != model_profile.model_code.value
        or type(request.max_output_tokens) is not int
        or request.max_output_tokens != 8192
        or request.service_tier != "default"
        or request.reasoning_effort is not OpenAIReasoningEffort.LOW
        or request.schema_name != "pedagogical_generation"
        or request.output_schema != lower_openai_strict_schema(harden_output_schema())
    ):
        raise ValueError("R3_HARDEN_PROFILE_REJECTED")
    payload = json.loads(request.input_json)
    if (
        type(payload) is not dict
        or payload.get("objective") != "HARDEN_DOSSIER_3"
        or payload.get("operation") != "TRANSFORM"
        or payload.get("production_kind") != "ASSESSMENT"
        or payload.get("expected_sections") != ["R3_RESULT_JSON"]
        or type(payload.get("output_contract")) is not dict
        or payload["output_contract"].get("harden_contract_id") != HARDEN_CONTRACT_ID
    ):
        raise ValueError("R3_HARDEN_OPERATION_REJECTED")
    body = {
        "background": False,
        "model": request.model,
        "instructions": request.instructions,
        "input": request.input_json,
        "max_output_tokens": 8192,
        "service_tier": "default",
        "store": False,
        "stream": False,
        "reasoning": {"effort": "low"},
        "tools": [],
        "tool_choice": "none",
        "text": {
            "format": {
                "type": "json_schema",
                "name": request.schema_name,
                "schema": request.output_schema,
                "strict": True,
            }
        },
    }
    json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return body


def r3_harden_count_parameters(
    request: OpenAIResponsesRequest, *, model_profile: ModelProfileConfig
) -> dict[str, object]:
    body = r3_harden_request_parameters(request, model_profile=model_profile)
    return {
        key: body[key]
        for key in ("model", "instructions", "input", "text", "reasoning", "tools", "tool_choice")
    }
