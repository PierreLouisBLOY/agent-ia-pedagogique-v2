"""GenerationPort adapter backed by one selected OpenAI model profile."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import NoReturn, cast

from backend.adapters.outbound.generation.openai.mapping import (
    CONVERSATION_OUTPUT_CONTRACT_ID,
    build_openai_request,
    conversation_evidence_ids,
)
from backend.adapters.outbound.generation.parse_diagnostic import (
    ParseCode,
    ParseDiagnostic,
    ParseStage,
)
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
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
        "_before_request", "_on_dispatch", "_on_response", "_on_parsing",
        "_parse_diagnostic",
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
        self._before_request: Callable[[OpenAIResponsesRequest], None] | None = None
        self._on_dispatch: Callable[[], None] | None = None
        self._on_response: Callable[[OpenAIResponsesResponse], None] | None = None
        self._on_parsing: Callable[[str], None] | None = None
        self._parse_diagnostic = ParseDiagnostic(enabled=False)

    def parse_diagnostic(self) -> dict[str, str | None]:
        """Private metadata snapshot, never included in the GenerationPort result."""
        return self._parse_diagnostic.snapshot()

    def bind_conversation_execution(self, *, before_request: Callable[[OpenAIResponsesRequest], None],
        on_dispatch: Callable[[], None], on_response: Callable[[OpenAIResponsesResponse], None],
        on_parsing: Callable[[str], None]) -> None:
        """Explicit R2 instrumentation/preflight; no default acquisition or authority."""
        if self._before_request is not None:
            raise ValueError("R2_EXECUTION_ALREADY_BOUND")
        self._before_request, self._on_dispatch = before_request, on_dispatch
        self._on_response, self._on_parsing = on_response, on_parsing

    def __repr__(self) -> str:
        return (
            "OpenAIGenerationAdapter("
            f"provider_profile_id={self._provider_profile.profile_id.value!r}, "
            f"model_profile_id={self._model_profile.model_profile_id.value!r})"
        )

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self._parse_diagnostic = ParseDiagnostic(enabled=False)
        if type(request) is not GenerationPortRequest:
            raise TypeError("request must be a GenerationPortRequest")
        self._parse_diagnostic = ParseDiagnostic(enabled=(
            request.objective in {"PREPARE_SUPPLEMENTS", "HARDEN_DOSSIER_3"}
            and request.output_contract.get("contract_id") == "R3-TRANSFORMATION-1.0"))
        _require_supported_operation(request.operation, self._model_profile)
        provider_request = build_openai_request(
            request=request,
            model_profile=self._model_profile,
        )
        if self._before_request is not None:
            self._before_request(provider_request)  # Before resolver and transport construction.
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
            if self._on_dispatch is not None:
                self._on_dispatch()
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
        if self._on_response is not None:
            self._on_response(response)  # Captured privately before any pedagogical parsing.
        try:
            result = _map_response(request=request, response=response,
                provider_profile=self._provider_profile, model_profile=self._model_profile,
                diagnostic=self._parse_diagnostic)
        except Exception:
            if self._on_parsing is not None:
                self._on_parsing("FAILED")
            raise
        if self._on_parsing is not None:
            self._on_parsing("REFUSED" if response.status is OpenAIResponseStatus.REFUSED else
                "INCOMPLETE" if response.status is OpenAIResponseStatus.INCOMPLETE else "SUCCEEDED")
        return result


def _map_response(
    *,
    request: GenerationPortRequest,
    response: OpenAIResponsesResponse,
    provider_profile: ProviderProfileConfig,
    model_profile: ModelProfileConfig,
    diagnostic: ParseDiagnostic | None = None,
) -> GenerationPortResult:
    trace = diagnostic if diagnostic is not None else ParseDiagnostic(enabled=False)
    with trace.capture():
        return _map_response_body(request=request, response=response,
            provider_profile=provider_profile, model_profile=model_profile, diagnostic=trace)


def _map_response_body(
    *,
    request: GenerationPortRequest,
    response: OpenAIResponsesResponse,
    provider_profile: ProviderProfileConfig,
    model_profile: ModelProfileConfig,
    diagnostic: ParseDiagnostic,
) -> GenerationPortResult:
    from backend.adapters.outbound.generation.openai.harden_contract import is_harden_request
    from backend.adapters.outbound.generation.openai.harden_materialization import (
        materialized_harden_text,
    )
    from backend.adapters.outbound.generation.openai.locator_materialization import (
        materialized_prepare_text,
    )
    from backend.adapters.outbound.generation.openai.prepare_contract import (
        is_prepare_request,
    )

    with diagnostic.at(ParseStage.ENVELOPE, expected=(AttributeError, TypeError),
                       code=ParseCode.RESPONSE_ENVELOPE_INVALID):
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
    from backend.adapters.outbound.generation.openai.p0_codesign_contract import (
        CONTRACT,
        map_response,
    )
    if request.output_contract.get("contract_id") == CONTRACT:
        return map_response(request, response, metadata)
    if is_prepare_request(request) or is_harden_request(request):
        text = (materialized_harden_text(response.output_text, request, diagnostic)
                if is_harden_request(request)
                else materialized_prepare_text(response.output_text, request, diagnostic))
        incomplete = response.status is OpenAIResponseStatus.INCOMPLETE
        with diagnostic.at(ParseStage.DOMAIN_MAP, expected=(TypeError, ValueError),
                           code=ParseCode.DOMAIN_MAPPING_FAILURE):
            return GenerationPortResult(
                source_step_id=request.source_step_id,
                operation=request.operation,
                status=(GenerationPortResultStatus.PARTIAL if incomplete
                        else GenerationPortResultStatus.SUCCEEDED),
                content="R3_RESULT_JSON\n" + text,
                structured_payload={"sections": {"R3_RESULT_JSON": text}},
                warnings=({"code": "OPENAI_RESPONSE_INCOMPLETE"},) if incomplete else (),
                execution_metadata=metadata,
            )
    conversation = request.output_contract.get("id") == CONVERSATION_OUTPUT_CONTRACT_ID
    payload = _parse_payload(response.output_text, conversation=conversation, diagnostic=diagnostic)
    used: tuple[str, ...] = ()
    if conversation:
        value = payload["evidence_ids_used"]
        if (not isinstance(value, list) or any(not isinstance(item, str) for item in value)
                or len(set(value)) != len(value)
                or not set(value).issubset(conversation_evidence_ids(request))):
            diagnostic.fail(ParseCode.SCHEMA_VALIDATION_FAILURE)
            _invalid_response()
        used = tuple(value)
    outcome = payload["outcome"]
    warnings = _limitations(payload["warnings"], "warnings", diagnostic=diagnostic)
    uncertainties = _limitations(payload["uncertainties"], "uncertainties", diagnostic=diagnostic)
    if outcome == "INSUFFICIENT_EVIDENCE":
        if payload["sections"] or not uncertainties:
            diagnostic.fail(ParseCode.CARDINALITY_INVALID)
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
        diagnostic.fail(ParseCode.ENUM_INVALID if isinstance(outcome, str) else ParseCode.TYPE_MISMATCH)
        _invalid_response()

    sections = _sections(payload["sections"], request.expected_sections, diagnostic=diagnostic)
    if conversation and (
        any(len(text.strip()) < 20 or "exercice à compléter" in text.casefold()
            for text in sections.values())
        or sum(len(text.encode("utf-8")) for text in sections.values()) > 65536
    ):
        diagnostic.fail(ParseCode.SCHEMA_VALIDATION_FAILURE)
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
        diagnostic.fail(ParseCode.CARDINALITY_INVALID)
        _invalid_response()
    with diagnostic.at(ParseStage.DOMAIN_MAP, expected=(TypeError, ValueError),
                       code=ParseCode.DOMAIN_MAPPING_FAILURE):
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


def _parse_payload(output_text: str | None, *, conversation: bool = False,
                   diagnostic: ParseDiagnostic | None = None) -> Mapping[str, object]:
    diagnostic = diagnostic if diagnostic is not None else ParseDiagnostic(enabled=False)
    diagnostic.begin(ParseStage.TEXT_EXTRACT)
    if output_text is None:
        diagnostic.fail(ParseCode.OUTPUT_TEXT_MISSING)
        _invalid_response()
    diagnostic.begin(ParseStage.JSON_DECODE)
    try:
        payload = json.loads(output_text, object_pairs_hook=_unique_object) if conversation else (
            json.loads(output_text)
        )
    except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
        diagnostic.fail(ParseCode.JSON_DECODE_FAILURE)
        _invalid_response()
    diagnostic.begin(ParseStage.SCHEMA_VALIDATE)
    keys = _EXPECTED_PAYLOAD_KEYS | ({"evidence_ids_used"} if conversation else set())
    if not isinstance(payload, dict) or set(payload) != keys:
        if not isinstance(payload, dict):
            diagnostic.fail(ParseCode.TYPE_MISMATCH)
        elif "sections" not in payload:
            diagnostic.begin(ParseStage.OUTPUT_EXTRACT)
            diagnostic.fail(ParseCode.STRUCTURED_OUTPUT_MISSING)
        elif keys - set(payload):
            diagnostic.fail(ParseCode.REQUIRED_FIELD_MISSING)
        else:
            diagnostic.fail(ParseCode.SCHEMA_VALIDATION_FAILURE)
        _invalid_response()
    return cast(dict[str, object], payload)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_OUTPUT_KEY")
        result[key] = value
    return result


def _sections(value: object, expected: tuple[str, ...], *,
              diagnostic: ParseDiagnostic | None = None) -> dict[str, str]:
    diagnostic = diagnostic if diagnostic is not None else ParseDiagnostic(enabled=False)
    diagnostic.begin(ParseStage.SCHEMA_VALIDATE)
    if not isinstance(value, list) or not value:
        diagnostic.fail(ParseCode.TYPE_MISMATCH if not isinstance(value, list)
                        else ParseCode.CARDINALITY_INVALID)
        _invalid_response()
    sections: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"code", "text"}:
            if not isinstance(item, dict):
                diagnostic.fail(ParseCode.TYPE_MISMATCH)
            elif "text" not in item:
                diagnostic.begin(ParseStage.TEXT_EXTRACT)
                diagnostic.fail(ParseCode.OUTPUT_TEXT_MISSING)
            elif "code" not in item:
                diagnostic.fail(ParseCode.REQUIRED_FIELD_MISSING)
            else:
                diagnostic.fail(ParseCode.SCHEMA_VALIDATION_FAILURE)
            _invalid_response()
        code = item["code"]
        text = item["text"]
        if not isinstance(code, str) or not code.strip():
            diagnostic.fail(ParseCode.TYPE_MISMATCH if not isinstance(code, str)
                            else ParseCode.SCHEMA_VALIDATION_FAILURE)
            _invalid_response()
        if not isinstance(text, str) or not text.strip() or code in sections:
            diagnostic.fail(ParseCode.TYPE_MISMATCH if not isinstance(text, str)
                            else ParseCode.CARDINALITY_INVALID if code in sections
                            else ParseCode.OUTPUT_TEXT_MISSING)
            _invalid_response()
        sections[code] = text
    if expected and tuple(sections) != expected:
        diagnostic.fail(ParseCode.CARDINALITY_INVALID)
        _invalid_response()
    return sections


def _limitations(value: object, field_name: str, *,
                 diagnostic: ParseDiagnostic | None = None) -> tuple[Mapping[str, object], ...]:
    diagnostic = diagnostic if diagnostic is not None else ParseDiagnostic(enabled=False)
    diagnostic.begin(ParseStage.SCHEMA_VALIDATE)
    if not isinstance(value, list):
        diagnostic.fail(ParseCode.TYPE_MISMATCH)
        _invalid_response()
    limitations: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"code", "message"}:
            diagnostic.fail(ParseCode.TYPE_MISMATCH if not isinstance(item, dict)
                            else ParseCode.REQUIRED_FIELD_MISSING if {"code", "message"} - set(item)
                            else ParseCode.SCHEMA_VALIDATION_FAILURE)
            _invalid_response()
        code = item["code"]
        message = item["message"]
        if not isinstance(code, str) or not code.strip():
            diagnostic.fail(ParseCode.TYPE_MISMATCH if not isinstance(code, str)
                            else ParseCode.SCHEMA_VALIDATION_FAILURE)
            _invalid_response()
        if not isinstance(message, str) or not message.strip():
            diagnostic.fail(ParseCode.TYPE_MISMATCH if not isinstance(message, str)
                            else ParseCode.SCHEMA_VALIDATION_FAILURE)
            _invalid_response()
        limitations.append({"code": code, "message": message})
    if len(limitations) > 16:
        diagnostic.fail(ParseCode.CARDINALITY_INVALID)
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
