from __future__ import annotations

from datetime import UTC, datetime

from backend.adapters.outbound.openai import OpenAIResponsesResponse, OpenAIResponseStatus
from backend.adapters.outbound.review.openai import OpenAIReviewAdapter
from backend.agent_runtime.agents.review import (
    ResolvedReviewTarget,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewPortResultStatus,
    ReviewPreparationRequest,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    InvocationStatus,
    ReviewDimension,
    ReviewRequest,
)
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
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant
from tests.support.openai_generation_fakes import (
    RecordingOpenAIResponsesTransport,
    RecordingOpenAITransportFactory,
)
from tests.unit.test_openai_review_adapter import _semantic_payload


def test_real_reviewer_agent_and_coordinator_preserve_ag04_boundary() -> None:
    target_ref = ObjectVersionRef(
        TypedEntityRef(TypedEntityId("production", "review-agent-target")),
        VersionRef("v1"),
    )
    canonical = ReviewRequest(
        meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0,
            "run-openai-review",
            "step-openai-review",
            None,
            CorrelationId("corr-openai-review"),
            Instant(datetime(2026, 8, 28, 14, 0, tzinfo=UTC)),
            ActorRef(ActorKind.AGENT, AgentId.AG_04.value),
            InvocationStatus.PLANNED,
        ),
        target_production_ref=target_ref,
        review_dimensions=(ReviewDimension.ACCURACY, ReviewDimension.PEDAGOGY),
        criteria={"required": ["exact", "adapted"]},
        evidence_refs=("evidence:alpha", "evidence:beta"),
    )
    provider_id = ProviderProfileId("openai-review-provider")
    transport = RecordingOpenAIResponsesTransport(
        response=OpenAIResponsesResponse(
            OpenAIResponseStatus.COMPLETED,
            _semantic_payload(),
        )
    )
    adapter = OpenAIReviewAdapter(
        provider_profile=ProviderProfileConfig(
            provider_id,
            ProviderCode("openai"),
            ProviderCredentialRef("OPENAI_REVIEW_API_KEY"),
        ),
        model_profile=ModelProfileConfig(
            ModelProfileId("openai.gpt-5.6-sol.review"),
            provider_id,
            ModelCode("gpt-5.6-sol"),
            ModelContextLimits(1_050_000, 900_000, 128_000),
            ProviderInvocationLimits(1, 30_000, max_output_tokens=32_000),
            (ProviderWorkloadKind.REVIEW,),
            structured_output_required=True,
        ),
        secret_resolver=EnvironmentProviderSecretResolver(
            {"OPENAI_REVIEW_API_KEY": "synthetic"}
        ),
        transport_factory=RecordingOpenAITransportFactory(transport),
    )
    reviewer = ReviewerAgent(ReviewCoordinator(adapter))

    prepared, result = reviewer.semantic_review(
        request=ReviewPreparationRequest(
            CapabilityId("CAP-V01"),
            canonical,
            ResolvedReviewTarget(target_ref, content="Une leçon synthétique bornée."),
            resolved_inputs={"pedagogical_level": "CM1"},
            output_contract={"type": "technical_review"},
        )
    )

    assert result.status is ReviewPortResultStatus.SUCCEEDED
    assert result.source_step_id == canonical.meta.step_id
    assert result.evidence_refs_used == ("evidence:alpha",)
    assert prepared.port_request.target_production_ref == target_ref
    assert len(transport.calls) == 1
    assert not hasattr(adapter, "approve")
    assert not hasattr(adapter, "promote")
