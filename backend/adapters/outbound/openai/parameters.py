"""One pure serialization shared by the cost projection and SDK transport."""
from __future__ import annotations

from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAITransportError,
    OpenAITransportErrorCode,
)


def response_parameters(request: OpenAIResponsesRequest) -> dict[str, object]:
    parameters: dict[str, object] = {
        "background": False, "input": request.input_json,
        "instructions": request.instructions, "max_output_tokens": request.max_output_tokens,
        "model": request.model, "store": False, "stream": False,
        "text": {"format": {"name": request.schema_name, "schema": request.output_schema,
                            "strict": True, "type": "json_schema"}},
        "tool_choice": "none", "tools": [],
    }
    if request.reasoning_effort is not None:
        parameters["reasoning"] = {"effort": request.reasoning_effort.value}
    if request.service_tier is not None:
        if request.service_tier != "default":
            raise OpenAITransportError(OpenAITransportErrorCode.INVALID_REQUEST)
        parameters["service_tier"] = "default"
    return parameters
