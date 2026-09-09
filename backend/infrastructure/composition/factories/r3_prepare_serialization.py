"""Contextual R3 PREPARE serialization; no R2 change or live authority."""
from __future__ import annotations

import json

from backend.adapters.outbound.generation.openai.prepare_contract import prepare_output_schema
from backend.adapters.outbound.openai.contracts import OpenAIReasoningEffort, OpenAIResponsesRequest
from backend.adapters.outbound.openai.schema import lower_openai_strict_schema
from backend.infrastructure.config.schemas.provider import ModelProfileConfig, ProviderWorkloadKind


def r3_prepare_request_parameters(
    request: OpenAIResponsesRequest, *, model_profile: ModelProfileConfig, operation: str,
) -> dict[str, object]:
    """Validate explicit profile/invocation bounds before serializing without clamping.

    This closed R3 successor admits the historical 4096 and approved 8192 profile
    reservations. It does not alter the R2 serializer or grant dispatch authority.
    """
    limits, context = model_profile.invocation_limits, model_profile.context_limits
    bound = limits.max_output_tokens
    if (operation != "PREPARE_SUPPLEMENTS" or not model_profile.enabled
            or not model_profile.structured_output_required
            or model_profile.supported_workloads != (ProviderWorkloadKind.GENERATION,)
            or model_profile.model_code.value != "gpt-5.6-terra"
            or request.model != model_profile.model_code.value
            or limits.max_attempts != 1 or limits.call_timeout_milliseconds != 90000
            or type(bound) is not int or bound not in (4096, 8192)
            or context.reserved_output_tokens != bound
            or limits.max_input_tokens != context.max_provider_input_tokens
            or limits.max_total_tokens != context.max_provider_input_tokens + bound
            or limits.max_total_tokens > context.context_window_tokens
            or type(request.max_output_tokens) is not int
            or not 0 < request.max_output_tokens <= bound
            or request.service_tier != "default"
            or request.reasoning_effort is not OpenAIReasoningEffort.LOW):
        raise ValueError("R3_PREPARE_PROFILE_LIMIT_REJECTED")
    try:
        payload = json.loads(request.input_json)
    except (ValueError, TypeError):
        raise ValueError("R3_PREPARE_OPERATION_REJECTED") from None
    if (type(payload) is not dict or payload.get("operation") != "TRANSFORM"
            or payload.get("objective") != operation or payload.get("production_kind") != "ASSESSMENT"
            or payload.get("expected_sections") != ["R3_RESULT_JSON"]
            or not isinstance(payload.get("output_contract"), dict)
            or payload["output_contract"].get("contract_id") != "R3-TRANSFORMATION-1.0"
            or request.schema_name != "pedagogical_generation"
            or request.output_schema != lower_openai_strict_schema(prepare_output_schema())):
        raise ValueError("R3_PREPARE_OPERATION_REJECTED")
    return {"background": False, "model": request.model, "instructions": request.instructions,
        "input": request.input_json, "max_output_tokens": request.max_output_tokens, "service_tier": "default",
        "store": False, "stream": False, "reasoning": {"effort": "low"},
        "tools": [], "tool_choice": "none", "text": {"format": {
            "type": "json_schema", "name": request.schema_name,
            "schema": request.output_schema, "strict": True}}}
