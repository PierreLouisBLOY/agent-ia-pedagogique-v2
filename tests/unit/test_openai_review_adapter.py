from __future__ import annotations

import json

import pytest

from backend.adapters.outbound.openai import (
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.adapters.outbound.openai.schema import (
    OpenAIProviderSchemaError,
    OpenAIProviderSchemaErrorCode,
)
from backend.adapters.outbound.review.openai import OpenAIReviewAdapter
from backend.adapters.outbound.review.openai.mapping import build_openai_review_request
from backend.agent_runtime.agents.review import (
    ReviewOperation,
    ReviewPortError,
    ReviewPortErrorCode,
    ReviewPortRequest,
    ReviewPortResultStatus,
)
from backend.agent_runtime.contracts import BudgetSpec, ReviewDimension
from backend.core_contracts.capability import CapabilityId
from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
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

_SECRET = "synthetic-openai-review-secret"


def _provider() -> ProviderProfileConfig:
    return ProviderProfileConfig(
        ProviderProfileId("openai-review-provider"),
        ProviderCode("openai"),
        ProviderCredentialRef("OPENAI_REVIEW_API_KEY"),
    )


def _model() -> ModelProfileConfig:
    return ModelProfileConfig(
        ModelProfileId("openai.gpt-5.6-sol.review"),
        ProviderProfileId("openai-review-provider"),
        ModelCode("gpt-5.6-sol"),
        ModelContextLimits(1_050_000, 900_000, 128_000),
        ProviderInvocationLimits(1, 30_000, max_output_tokens=32_000),
        (ProviderWorkloadKind.REVIEW,),
        structured_output_required=True,
    )


def _request(
    operation: ReviewOperation = ReviewOperation.SEMANTIC_REVIEW,
    *,
    budget: BudgetSpec | None = None,
    evidence_refs: tuple[str, ...] = ("evidence:alpha", "evidence:beta"),
) -> ReviewPortRequest:
    return ReviewPortRequest(
        source_step_id="step-review-provider",
        operation=operation,
        capability_id=CapabilityId(
            "CAP-V01" if operation is ReviewOperation.SEMANTIC_REVIEW else "CAP-V02"
        ),
        target_production_ref=ObjectVersionRef(
            TypedEntityRef(TypedEntityId("production", "lesson-provider")),
            VersionRef("v2"),
        ),
        review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.PEDAGOGY),
        target_content="Une leçon synthétique bornée.",
        target_payload={"sections": ["intro"]},
        criteria={"required": ["exact", "adapted"]},
        evidence_refs=evidence_refs,
        coverage_context={"scope": ["intro"]},
        resolved_inputs={"finding_ids": ["finding-1"]},
        output_contract={"type": "technical_review"},
        review_budget=budget,
    )


def _semantic_payload(
    *,
    limitations: list[dict[str, str]] | None = None,
    warnings: list[dict[str, str]] | None = None,
    uncertainties: list[dict[str, str]] | None = None,
) -> str:
    return json.dumps(
        {
            "outcome": "OUTPUT",
            "structured_payload": {
                "overall_assessment": "acceptable",
                "correction_required": False,
                "coverage": ["REV-ACC", "REV-PED"],
                "confidence": {"level": "high", "basis": "bounded evidence"},
            },
            "technical_findings": [],
            "limitations": limitations or [],
            "warnings": warnings or [],
            "uncertainties": uncertainties or [],
            "evidence_refs_used": ["evidence:alpha"],
        }
    )


def _assessment_payload() -> str:
    return json.dumps(
        {
            "outcome": "OUTPUT",
            "structured_payload": {
                "assessed_finding_ids": ["finding-1"],
                "blocking_finding_ids": [],
                "correction_finding_ids": [],
                "overall_assessment": "acceptable",
                "correction_required": False,
                "confidence": {"level": "medium", "basis": "finding snapshot"},
            },
            "technical_findings": [],
            "limitations": [],
            "warnings": [],
            "uncertainties": [],
            "evidence_refs_used": [],
        }
    )


def _adapter(
    response: OpenAIResponsesResponse | None = None,
    *,
    error: OpenAITransportError | None = None,
) -> tuple[OpenAIReviewAdapter, RecordingOpenAIResponsesTransport]:
    transport = RecordingOpenAIResponsesTransport(response=response, error=error)
    return (
        OpenAIReviewAdapter(
            provider_profile=_provider(),
            model_profile=_model(),
            secret_resolver=EnvironmentProviderSecretResolver(
                {"OPENAI_REVIEW_API_KEY": _SECRET}
            ),
            transport_factory=RecordingOpenAITransportFactory(transport),
        ),
        transport,
    )


@pytest.mark.parametrize(
    ("operation", "payload", "instruction_fragment"),
    (
        (ReviewOperation.SEMANTIC_REVIEW, _semantic_payload(), "SEMANTIC_REVIEW"),
        (ReviewOperation.ASSESS_FINDINGS, _assessment_payload(), "ASSESS_FINDINGS"),
    ),
)
def test_review_maps_both_operations_to_distinct_bounded_requests(
    operation: ReviewOperation,
    payload: str,
    instruction_fragment: str,
) -> None:
    adapter, transport = _adapter(
        OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, payload)
    )

    result = adapter.review(request=_request(operation))

    assert result.status is ReviewPortResultStatus.SUCCEEDED
    assert result.operation is operation
    assert len(transport.calls) == 1
    provider_request = transport.calls[0]
    assert provider_request.model == "gpt-5.6-sol"
    assert provider_request.schema_name == "technical_pedagogical_review"
    assert instruction_fragment in provider_request.instructions
    assert "approve" in provider_request.instructions
    mapped = json.loads(provider_request.input_json)
    assert mapped["source_step_id"] == "step-review-provider"
    assert mapped["target_production_ref"] == {
        "entity_type": "production",
        "entity_id": "lesson-provider",
        "version": "v2",
    }
    assert mapped["review_dimensions"] == ["REV-ACC", "REV-PED"]
    assert mapped["target_content"] == "Une leçon synthétique bornée."
    assert set(provider_request.output_schema["required"]) == {
        "outcome",
        "structured_payload",
        "technical_findings",
        "limitations",
        "warnings",
        "uncertainties",
        "evidence_refs_used",
    }


def test_review_maps_partial_refusal_and_safe_token_metadata() -> None:
    response = OpenAIResponsesResponse(
        OpenAIResponseStatus.INCOMPLETE,
        _semantic_payload(limitations=[{"code": "LIMITED", "message": "partial"}]),
        OpenAIResponseUsage(100, 20, 30, 130),
    )
    adapter, _ = _adapter(response)
    partial = adapter.review(request=_request())
    assert partial.status is ReviewPortResultStatus.PARTIAL
    assert partial.execution_metadata == {
        "provider_code": "openai",
        "provider_profile_id": "openai-review-provider",
        "model_profile_id": "openai.gpt-5.6-sol.review",
        "model_code": "gpt-5.6-sol",
        "response_status": "incomplete",
        "input_tokens": 100,
        "cached_input_tokens": 20,
        "output_tokens": 30,
        "total_tokens": 130,
    }
    assert set(partial.execution_metadata).isdisjoint(
        {"target", "prompt", "secret", "response_id"}
    )

    refused, _ = _adapter(OpenAIResponsesResponse(OpenAIResponseStatus.REFUSED))
    refusal = refused.review(request=_request())
    assert refusal.status is ReviewPortResultStatus.REFUSED
    assert refusal.technical_findings == ()


@pytest.mark.parametrize(
    "output_text",
    (
        "not-json",
        json.dumps({"outcome": "OUTPUT"}),
        _semantic_payload().replace('"overall_assessment"', '"approved"'),
        _semantic_payload().replace('"acceptable"', '"unexpected-assessment"'),
        _semantic_payload().replace('"evidence:alpha"', '"evidence:foreign"'),
    ),
)
def test_review_rejects_malformed_missing_authority_or_foreign_lineage(
    output_text: str,
) -> None:
    adapter, _ = _adapter(
        OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, output_text)
    )
    with pytest.raises(ReviewPortError) as raised:
        adapter.review(request=_request())
    assert raised.value.code is ReviewPortErrorCode.INVALID_RESPONSE


@pytest.mark.parametrize("code", tuple(OpenAITransportErrorCode))
def test_review_closes_all_transport_errors(code: OpenAITransportErrorCode) -> None:
    adapter, _ = _adapter(error=OpenAITransportError(code))
    with pytest.raises(ReviewPortError) as raised:
        adapter.review(request=_request())
    assert raised.value.code is ReviewPortErrorCode.UNAVAILABLE
    assert _SECRET not in str(raised.value)


def test_review_rejects_zero_budget_before_transport() -> None:
    adapter, transport = _adapter(
        OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, _semantic_payload())
    )
    with pytest.raises(ReviewPortError) as raised:
        adapter.review(request=_request(budget=BudgetSpec(max_tokens=0)))
    assert raised.value.code is ReviewPortErrorCode.REQUEST_REJECTED
    assert transport.calls == []


def test_review_provider_schema_lowers_unsupported_array_keywords() -> None:
    without_refs = build_openai_review_request(
        request=_request(evidence_refs=()),
        model_profile=_model(),
    ).output_schema
    serialized = json.dumps(without_refs, sort_keys=True)
    assert '"not"' not in serialized
    assert '"uniqueItems"' not in serialized
    root_properties = without_refs["properties"]
    assert type(root_properties) is dict
    evidence_refs_used = root_properties["evidence_refs_used"]
    assert type(evidence_refs_used) is dict
    assert evidence_refs_used["maxItems"] == 0
    findings = root_properties["technical_findings"]
    assert type(findings) is dict
    finding_items = findings["items"]
    assert type(finding_items) is dict
    finding_properties = finding_items["properties"]
    assert type(finding_properties) is dict
    finding_refs = finding_properties["evidence_refs"]
    assert type(finding_refs) is dict
    assert finding_refs["maxItems"] == 0

    with_refs = build_openai_review_request(
        request=_request(),
        model_profile=_model(),
    ).output_schema
    with_refs_serialized = json.dumps(with_refs, sort_keys=True)
    assert '"not"' not in with_refs_serialized
    assert '"uniqueItems"' not in with_refs_serialized


def test_review_post_validation_still_rejects_duplicate_sequences() -> None:
    payload = json.loads(_semantic_payload())
    payload["structured_payload"]["coverage"] = ["REV-ACC", "REV-ACC"]
    adapter, _ = _adapter(
        OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, json.dumps(payload))
    )
    with pytest.raises(ReviewPortError) as raised:
        adapter.review(request=_request())
    assert raised.value.code is ReviewPortErrorCode.INVALID_RESPONSE


def test_review_schema_failure_stops_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_schema(_: dict[str, object]) -> dict[str, object]:
        raise OpenAIProviderSchemaError(
            OpenAIProviderSchemaErrorCode.UNSUPPORTED_KEYWORD
        )

    monkeypatch.setattr(
        "backend.adapters.outbound.review.openai.mapping.lower_openai_strict_schema",
        reject_schema,
    )
    adapter, transport = _adapter(
        OpenAIResponsesResponse(OpenAIResponseStatus.COMPLETED, _semantic_payload())
    )
    with pytest.raises(ReviewPortError) as raised:
        adapter.review(request=_request())
    assert raised.value.code is ReviewPortErrorCode.REQUEST_REJECTED
    assert transport.calls == []
