from __future__ import annotations

import json

import pytest

from backend.adapters.outbound.generation.openai import (
    OpenAIGenerationAdapter,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.agent_runtime.agents.generation import (
    GenerationOperation,
    GenerationPort,
    GenerationPortError,
    GenerationPortErrorCode,
    GenerationPortRequest,
    GenerationPortResultStatus,
)
from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderConfigurationError,
    ProviderConfigurationErrorCode,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    EnvironmentProviderSecretResolver,
    ProviderCredentialRef,
)
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from tests.support.openai_generation_fakes import (
    RecordingOpenAIResponsesTransport,
    RecordingOpenAITransportFactory,
)

_SYNTHETIC_SECRET = "synthetic-openai-secret-never-log"


def _provider(*, code: str = "openai") -> ProviderProfileConfig:
    return ProviderProfileConfig(
        ProviderProfileId("openai-provider"),
        ProviderCode(code),
        ProviderCredentialRef("OPENAI_API_KEY"),
    )


def _model(
    *,
    model_code: str = "gpt-5.6-terra",
    workloads: tuple[ProviderWorkloadKind, ...] = (
        ProviderWorkloadKind.GENERATION,
        ProviderWorkloadKind.CORRECTION,
    ),
    structured: bool = True,
) -> ModelProfileConfig:
    return ModelProfileConfig(
        ModelProfileId("openai-model-primary"),
        ProviderProfileId("openai-provider"),
        ModelCode(model_code),
        ModelContextLimits(1_050_000, 900_000, 128_000),
        ProviderInvocationLimits(
            max_attempts=5,
            call_timeout_milliseconds=45_000,
            max_output_tokens=64_000,
        ),
        workloads,
        structured_output_required=structured,
    )


def _request(
    operation: GenerationOperation = GenerationOperation.GENERATE,
) -> GenerationPortRequest:
    target_version = None
    target_ref = None
    if operation is GenerationOperation.CORRECT:
        target_version = ObjectVersionRef(
            TypedEntityRef(TypedEntityId("production", "lesson-1")),
            VersionRef("v3"),
        )
    elif operation is GenerationOperation.TRANSFORM:
        target_ref = "production:lesson-1"
    return GenerationPortRequest(
        operation=operation,
        source_step_id="step-openai-1",
        production_kind="lesson_plan",
        objective="Construire une séance structurée",
        output_format="markdown",
        pedagogical_context={"grade": "CM1", "language": "fr"},
        resolved_inputs={"evidence": {"facts": ["A", "B"]}},
        constraints={"duration_minutes": 45},
        evidence_refs=("evidence:one",),
        target_ref=target_ref,
        target_version_ref=target_version,
        expected_sections=("Objectifs", "Activités"),
        output_contract={"tone": "clear"},
    )


def _payload(
    *,
    outcome: str = "OUTPUT",
    sections: list[dict[str, str]] | None = None,
    warnings: list[dict[str, str]] | None = None,
    uncertainties: list[dict[str, str]] | None = None,
) -> str:
    return json.dumps(
        {
            "outcome": outcome,
            "sections": sections
            if sections is not None
            else [
                {"code": "Objectifs", "text": "Comprendre la notion."},
                {"code": "Activités", "text": "Manipuler puis expliquer."},
            ],
            "warnings": warnings or [],
            "uncertainties": uncertainties or [],
        }
    )


def _adapter(
    response: OpenAIResponsesResponse | None = None,
    *,
    error: OpenAITransportError | None = None,
    model: ModelProfileConfig | None = None,
) -> tuple[
    OpenAIGenerationAdapter,
    RecordingOpenAIResponsesTransport,
    RecordingOpenAITransportFactory,
]:
    transport = RecordingOpenAIResponsesTransport(response=response, error=error)
    factory = RecordingOpenAITransportFactory(transport)
    adapter = OpenAIGenerationAdapter(
        provider_profile=_provider(),
        model_profile=model or _model(),
        secret_resolver=EnvironmentProviderSecretResolver(
            {"OPENAI_API_KEY": _SYNTHETIC_SECRET}
        ),
        transport_factory=factory,
    )
    return adapter, transport, factory


def test_generate_maps_bounded_request_and_valid_structured_response() -> None:
    response = OpenAIResponsesResponse(
        status=OpenAIResponseStatus.COMPLETED,
        output_text=_payload(),
        usage=OpenAIResponseUsage(125, 25, 75, 200),
    )
    adapter, transport, factory = _adapter(response)

    result = adapter.generate(request=_request())

    assert isinstance(adapter, GenerationPort)
    assert result.status is GenerationPortResultStatus.SUCCEEDED
    assert result.content == (
        "Objectifs\nComprendre la notion.\n\n"
        "Activités\nManipuler puis expliquer."
    )
    assert result.structured_payload == {
        "sections": {
            "Objectifs": "Comprendre la notion.",
            "Activités": "Manipuler puis expliquer.",
        }
    }
    assert result.execution_metadata == {
        "provider_code": "openai",
        "provider_profile_id": "openai-provider",
        "model_profile_id": "openai-model-primary",
        "model_code": "gpt-5.6-terra",
        "response_status": "completed",
        "input_tokens": 125,
        "cached_input_tokens": 25,
        "output_tokens": 75,
        "total_tokens": 200,
    }
    assert len(transport.calls) == 1
    provider_request = transport.calls[0]
    assert provider_request.model == "gpt-5.6-terra"
    assert provider_request.max_output_tokens == 64_000
    sent = json.loads(provider_request.input_json)
    assert sent["operation"] == "GENERATE"
    assert sent["resolved_inputs"] == {"evidence": {"facts": ["A", "B"]}}
    assert sent["expected_sections"] == ["Objectifs", "Activités"]
    assert "non-authoritative" in provider_request.instructions
    assert provider_request.output_schema["additionalProperties"] is False
    assert factory.build_calls == [("ProviderSecretValue([REDACTED])", 45.0)]
    rendered = repr((adapter, provider_request, result, factory.build_calls))
    assert _SYNTHETIC_SECRET not in rendered


@pytest.mark.parametrize(
    "operation",
    (GenerationOperation.TRANSFORM, GenerationOperation.CORRECT),
)
def test_transform_and_correction_use_the_same_port_without_routing(
    operation: GenerationOperation,
) -> None:
    adapter, transport, _ = _adapter(
        OpenAIResponsesResponse(
            status=OpenAIResponseStatus.COMPLETED,
            output_text=_payload(),
        )
    )

    result = adapter.generate(request=_request(operation))

    assert result.operation is operation
    assert len(transport.calls) == 1
    assert json.loads(transport.calls[0].input_json)["operation"] == operation.value
    if operation is GenerationOperation.CORRECT:
        assert json.loads(transport.calls[0].input_json)["target_version_ref"] == {
            "entity_id": "lesson-1",
            "entity_type": "production",
            "version": "v3",
        }
        assert "For CORRECT" in transport.calls[0].instructions
    else:
        assert json.loads(transport.calls[0].input_json)["target_ref"] == (
            "production:lesson-1"
        )
        assert "For TRANSFORM" in transport.calls[0].instructions


def test_partial_and_incomplete_outputs_preserve_closed_limitations() -> None:
    adapter, _, _ = _adapter(
        OpenAIResponsesResponse(
            status=OpenAIResponseStatus.INCOMPLETE,
            output_text=_payload(
                uncertainties=[{"code": "SOURCE_GAP", "message": "Source limitée."}]
            ),
        )
    )

    result = adapter.generate(request=_request())

    assert result.status is GenerationPortResultStatus.PARTIAL
    assert result.warnings == ({"code": "OPENAI_RESPONSE_INCOMPLETE"},)
    assert result.uncertainties == (
        {"code": "SOURCE_GAP", "message": "Source limitée."},
    )


def test_explicit_refusal_and_insufficient_evidence_are_distinct() -> None:
    refused, _, _ = _adapter(
        OpenAIResponsesResponse(status=OpenAIResponseStatus.REFUSED)
    )
    refused_result = refused.generate(request=_request())
    assert refused_result.status is GenerationPortResultStatus.REFUSED
    assert refused_result.content is None

    insufficient, _, _ = _adapter(
        OpenAIResponsesResponse(
            status=OpenAIResponseStatus.COMPLETED,
            output_text=_payload(
                outcome="INSUFFICIENT_EVIDENCE",
                sections=[],
                uncertainties=[
                    {"code": "EVIDENCE_GAP", "message": "Aucune source suffisante."}
                ],
            ),
        )
    )
    insufficient_result = insufficient.generate(request=_request())
    assert (
        insufficient_result.status
        is GenerationPortResultStatus.INSUFFICIENT_EVIDENCE
    )
    assert insufficient_result.content is None


@pytest.mark.parametrize(
    "output_text",
    (
        "not-json",
        json.dumps({"outcome": "OUTPUT"}),
        _payload(sections=[{"code": "Unknown", "text": "Invalid."}]),
        _payload(sections=[{"code": "Objectifs", "text": "Only one."}]),
        _payload(
            outcome="INSUFFICIENT_EVIDENCE",
            sections=[],
            uncertainties=[],
        ),
    ),
)
def test_malformed_or_incoherent_structured_output_fails_closed(
    output_text: str,
) -> None:
    adapter, _, _ = _adapter(
        OpenAIResponsesResponse(
            status=OpenAIResponseStatus.COMPLETED,
            output_text=output_text,
        )
    )

    with pytest.raises(GenerationPortError) as raised:
        adapter.generate(request=_request())

    assert raised.value.code is GenerationPortErrorCode.INVALID_RESPONSE
    assert raised.value.safe_reason == "OPENAI_RESPONSE_DOES_NOT_MATCH_CONTRACT"
    assert output_text not in str(raised.value)


@pytest.mark.parametrize("code", tuple(OpenAITransportErrorCode))
def test_transport_failures_are_closed_and_never_retried(
    code: OpenAITransportErrorCode,
) -> None:
    adapter, transport, _ = _adapter(error=OpenAITransportError(code))

    with pytest.raises(GenerationPortError) as raised:
        adapter.generate(request=_request())

    assert raised.value.code is GenerationPortErrorCode.UNAVAILABLE
    assert raised.value.safe_reason == f"OPENAI_TRANSPORT_{code.value}"
    assert len(transport.calls) == 1


def test_missing_secret_fails_closed_before_transport_construction() -> None:
    transport = RecordingOpenAIResponsesTransport(
        response=OpenAIResponsesResponse(status=OpenAIResponseStatus.REFUSED)
    )
    factory = RecordingOpenAITransportFactory(transport)
    adapter = OpenAIGenerationAdapter(
        provider_profile=_provider(),
        model_profile=_model(),
        secret_resolver=EnvironmentProviderSecretResolver({}),
        transport_factory=factory,
    )

    with pytest.raises(GenerationPortError) as raised:
        adapter.generate(request=_request())

    assert raised.value.safe_reason == "OPENAI_CREDENTIAL_UNAVAILABLE"
    assert factory.build_calls == []
    assert transport.calls == []


@pytest.mark.parametrize(
    ("provider", "model"),
    (
        (_provider(code="other-provider"), _model()),
        (_provider(), _model(structured=False)),
    ),
)
def test_adapter_rejects_non_openai_or_non_structured_configuration(
    provider: ProviderProfileConfig,
    model: ModelProfileConfig,
) -> None:
    transport = RecordingOpenAIResponsesTransport(
        response=OpenAIResponsesResponse(status=OpenAIResponseStatus.REFUSED)
    )
    with pytest.raises(ProviderConfigurationError) as raised:
        OpenAIGenerationAdapter(
            provider_profile=provider,
            model_profile=model,
            secret_resolver=EnvironmentProviderSecretResolver({}),
            transport_factory=RecordingOpenAITransportFactory(transport),
        )
    assert (
        raised.value.code
        is ProviderConfigurationErrorCode.INVALID_PROVIDER_CONFIGURATION
    )


def test_operation_requires_the_selected_profile_workload() -> None:
    adapter, _, _ = _adapter(
        OpenAIResponsesResponse(status=OpenAIResponseStatus.REFUSED),
        model=_model(workloads=(ProviderWorkloadKind.GENERATION,)),
    )
    with pytest.raises(ProviderConfigurationError) as raised:
        adapter.generate(request=_request(GenerationOperation.CORRECT))
    assert raised.value.code is ProviderConfigurationErrorCode.INCOMPATIBLE_MODEL_WORKLOAD
