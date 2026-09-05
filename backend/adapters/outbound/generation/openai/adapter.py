"""GenerationPort adapter backed by one selected OpenAI model profile."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import NoReturn, cast

from backend.adapters.outbound.generation.openai.mapping import (
    CONVERSATION_OUTPUT_CONTRACT_ID,
    build_openai_request,
    conversation_evidence_ids,
)
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponsesTransportFactory,
    OpenAITransportError,
)
from backend.agent_runtime.agents.generation import (
    GenerationOperation,
    GenerationPortError,
    GenerationPortErrorCode,
    GenerationPortRequest,
    GenerationPortResult,
    GenerationPortResultStatus,
)
from backend.infrastructure.config.schemas.provider import (
    ModelProfileConfig,
    ProviderConfigurationError,
    ProviderConfigurationErrorCode,
    ProviderProfileConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderSecretError,
    ProviderSecretResolver,
)

_OPENAI_PROVIDER_CODE = "openai"
_EXPECTED_PAYLOAD_KEYS = {"outcome", "sections", "warnings", "uncertainties"}


class OpenAIGenerationAdapter:
    """Provider adapter with no routing, retry, review, or promotion authority."""

    __slots__ = (
        "_model_profile",
        "_provider_profile",
        "_secret_resolver",
        "_transport_factory",
    )

    def __init__(
        self,
        *,
        provider_profile: ProviderProfileConfig,
        model_profile: ModelProfileConfig,
        secret_resolver: ProviderSecretResolver,
        transport_factory: OpenAIResponsesTransportFactory,
    ) -> None:
        _validate_configuration(provider_profile, model_profile)
        if not isinstance(secret_resolver, ProviderSecretResolver):
            raise TypeError("secret_resolver must satisfy ProviderSecretResolver")
        self._provider_profile = provider_profile
        self._model_profile = model_profile
        self._secret_resolver = secret_resolver
        self._transport_factory = transport_factory

    def __repr__(self) -> str:
        return (
            "OpenAIGenerationAdapter("
            f"provider_profile_id={self._provider_profile.profile_id.value!r}, "
            f"model_profile_id={self._model_profile.model_profile_id.value!r})"
        )

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        if type(request) is not GenerationPortRequest:
            raise TypeError("request must be a GenerationPortRequest")
        _require_supported_operation(request.operation, self._model_profile)
        provider_request = build_openai_request(
            request=request,
            model_profile=self._model_profile,
        )
        try:
            secret = self._secret_resolver.resolve(
                self._provider_profile.credential_ref
            )
            transport = self._transport_factory.build(
                secret=secret,
                timeout_seconds=(
                    self._model_profile.invocation_limits.call_timeout_milliseconds
                    / 1_000.0
                ),
            )
            response = transport.create(request=provider_request)
        except ProviderSecretError:
            raise GenerationPortError(
                GenerationPortErrorCode.UNAVAILABLE,
                "OPENAI_CREDENTIAL_UNAVAILABLE",
            ) from None
        except OpenAITransportError as error:
            raise GenerationPortError(
                GenerationPortErrorCode.UNAVAILABLE,
                f"OPENAI_TRANSPORT_{error.code.value}",
            ) from None
        return _map_response(
            request=request,
            response=response,
            provider_profile=self._provider_profile,
            model_profile=self._model_profile,
        )


def _map_response(
    *,
    request: GenerationPortRequest,
    response: OpenAIResponsesResponse,
    provider_profile: ProviderProfileConfig,
    model_profile: ModelProfileConfig,
) -> GenerationPortResult:
    metadata = _execution_metadata(response, provider_profile, model_profile)
    if response.status is OpenAIResponseStatus.REFUSED:
        return GenerationPortResult(
            source_step_id=request.source_step_id,
            operation=request.operation,
            status=GenerationPortResultStatus.REFUSED,
            warnings=({"code": "OPENAI_PROVIDER_REFUSAL"},),
            execution_metadata=metadata,
        )
    if response.status is OpenAIResponseStatus.FAILED:
        raise GenerationPortError(
            GenerationPortErrorCode.UNAVAILABLE,
            "OPENAI_RESPONSE_FAILED",
        )
    conversation = request.output_contract.get("id") == CONVERSATION_OUTPUT_CONTRACT_ID
    payload = _parse_payload(response.output_text, conversation=conversation)
    used: tuple[str, ...] = ()
    if conversation:
        value = payload["evidence_ids_used"]
        if (not isinstance(value, list) or any(not isinstance(item, str) for item in value)
                or len(set(value)) != len(value)
                or not set(value).issubset(conversation_evidence_ids(request))):
            _invalid_response()
        used = tuple(value)
    outcome = payload["outcome"]
    warnings = _limitations(payload["warnings"], "warnings")
    uncertainties = _limitations(payload["uncertainties"], "uncertainties")
    if outcome == "INSUFFICIENT_EVIDENCE":
        if payload["sections"] or not uncertainties:
            _invalid_response()
        return GenerationPortResult(
            source_step_id=request.source_step_id,
            operation=request.operation,
            status=GenerationPortResultStatus.INSUFFICIENT_EVIDENCE,
            warnings=warnings,
            uncertainties=uncertainties,
            execution_metadata=metadata,
        )
    if outcome != "OUTPUT":
        _invalid_response()

    sections = _sections(payload["sections"], request.expected_sections)
    if conversation and (
        any(len(text.strip()) < 20 or "exercice à compléter" in text.casefold()
            for text in sections.values())
        or sum(len(text.encode("utf-8")) for text in sections.values()) > 65536
    ):
        _invalid_response()
    if response.status is OpenAIResponseStatus.INCOMPLETE:
        warnings = warnings + ({"code": "OPENAI_RESPONSE_INCOMPLETE"},)
    status = (
        GenerationPortResultStatus.PARTIAL
        if warnings or uncertainties
        else GenerationPortResultStatus.SUCCEEDED
    )
    content = "\n\n".join(f"{code}\n{text}" for code, text in sections.items())
    if conversation and len(content.encode("utf-8")) > 65536:
        _invalid_response()
    return GenerationPortResult(
        source_step_id=request.source_step_id,
        operation=request.operation,
        status=status,
        content=content,
        structured_payload={"sections": sections},
        evidence_refs_used=tuple(ref for ref in request.evidence_refs if ref in used),
        warnings=warnings,
        uncertainties=uncertainties,
        execution_metadata=metadata,
    )


def _parse_payload(output_text: str | None, *, conversation: bool = False) -> Mapping[str, object]:
    if output_text is None:
        _invalid_response()
    try:
        payload = json.loads(output_text, object_pairs_hook=_unique_object) if conversation else (
            json.loads(output_text)
        )
    except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
        _invalid_response()
    keys = _EXPECTED_PAYLOAD_KEYS | ({"evidence_ids_used"} if conversation else set())
    if not isinstance(payload, dict) or set(payload) != keys:
        _invalid_response()
    return cast(dict[str, object], payload)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_OUTPUT_KEY")
        result[key] = value
    return result


def _sections(value: object, expected: tuple[str, ...]) -> dict[str, str]:
    if not isinstance(value, list) or not value:
        _invalid_response()
    sections: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"code", "text"}:
            _invalid_response()
        code = item["code"]
        text = item["text"]
        if not isinstance(code, str) or not code.strip():
            _invalid_response()
        if not isinstance(text, str) or not text.strip() or code in sections:
            _invalid_response()
        sections[code] = text
    if expected and tuple(sections) != expected:
        _invalid_response()
    return sections


def _limitations(value: object, field_name: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        _invalid_response()
    limitations: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"code", "message"}:
            _invalid_response()
        code = item["code"]
        message = item["message"]
        if not isinstance(code, str) or not code.strip():
            _invalid_response()
        if not isinstance(message, str) or not message.strip():
            _invalid_response()
        limitations.append({"code": code, "message": message})
    if len(limitations) > 16:
        raise GenerationPortError(
            GenerationPortErrorCode.INVALID_RESPONSE,
            f"OPENAI_INVALID_{field_name.upper()}",
        )
    return tuple(limitations)


def _execution_metadata(
    response: OpenAIResponsesResponse,
    provider_profile: ProviderProfileConfig,
    model_profile: ModelProfileConfig,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "provider_code": provider_profile.provider_code.value,
        "provider_profile_id": provider_profile.profile_id.value,
        "model_profile_id": model_profile.model_profile_id.value,
        "model_code": model_profile.model_code.value,
        "response_status": response.status.value,
    }
    usage_fields = {
        "input_tokens": response.usage.input_tokens,
        "cached_input_tokens": response.usage.cached_input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    metadata.update({key: value for key, value in usage_fields.items() if value is not None})
    return metadata


def _validate_configuration(
    provider: ProviderProfileConfig,
    model: ModelProfileConfig,
) -> None:
    if type(provider) is not ProviderProfileConfig:
        raise TypeError("provider_profile must be a ProviderProfileConfig")
    if type(model) is not ModelProfileConfig:
        raise TypeError("model_profile must be a ModelProfileConfig")
    if (
        not provider.enabled
        or not model.enabled
        or provider.provider_code.value != _OPENAI_PROVIDER_CODE
        or model.provider_profile_id != provider.profile_id
        or not model.structured_output_required
    ):
        raise ProviderConfigurationError(
            ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
        )


def _require_supported_operation(
    operation: GenerationOperation,
    model: ModelProfileConfig,
) -> None:
    workload = (
        ProviderWorkloadKind.CORRECTION
        if operation is GenerationOperation.CORRECT
        else ProviderWorkloadKind.GENERATION
    )
    if workload not in model.supported_workloads:
        raise ProviderConfigurationError(
            ProviderConfigurationErrorCode.INCOMPATIBLE_MODEL_WORKLOAD
        )


def _invalid_response() -> NoReturn:
    raise GenerationPortError(
        GenerationPortErrorCode.INVALID_RESPONSE,
        "OPENAI_RESPONSE_DOES_NOT_MATCH_CONTRACT",
    )
