"""Explicit R2 composition; no ambient configuration or credential inspection."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from secrets import token_urlsafe
from typing import TYPE_CHECKING, NoReturn
from uuid import uuid4

from backend.adapters.inbound.api.conversation import ConversationEndpoint
from backend.adapters.inbound.api.production import ProductionEndpoint
from backend.adapters.inbound.application.conversation import (
    ConversationApplicationInbound,
    ConversationInputError,
)
from backend.adapters.inbound.application.production import ProductionUseCaseInbound
from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.evidence.sqlite import (
    SQLiteEvidenceDocumentContentAdapter,
    SQLiteEvidenceSearchAdapter,
)
from backend.adapters.outbound.generation.openai import OpenAIGenerationAdapter
from backend.adapters.outbound.openai import OpenAIResponsesTransportFactory
from backend.adapters.outbound.persistence.conversation_memory import ConversationMemoryStore
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.search.local import SQLiteLocalSearchAdapter
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter
from backend.agent_runtime.agents.evidence import (
    EvidenceAgent,
    EvidenceMaterializationPolicy,
    RetrievalChannel,
    RetrievalCoordinationPolicy,
    RetrievalCoordinator,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    InvocationStatus,
    UseCaseRequest,
    UseCaseResult,
)
from backend.agent_runtime.orchestration import (
    WorkflowRequirements,
    WorkflowSelectionStatus,
    WorkflowSelector,
)
from backend.agent_runtime.orchestration.workflows import WorkflowKind
from backend.core_contracts.invocation import UseCaseContext
from backend.infrastructure.composition.factories.openai import build_openai_generation_adapter
from backend.infrastructure.config.effective_config.provider import EffectiveProviderConfiguration
from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderConfigurationVersion,
    ProviderCostLimit,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderRouteConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretResolver,
)
from backend.modules.pedagogical_context.application.services.conversation_context import (
    ConversationContextService,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.application.queries.read_production import (
    ReadProductionQuery,
)
from backend.modules.work_orchestration.application.services.conversation import (
    ConversationService,
    initial_conversation,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.modules.work_orchestration.ports.outbound.generation_job import (
    GenerationJobPort,
    GenerationJobResult,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

if TYPE_CHECKING:
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget


@dataclass(frozen=True, slots=True)
class ConversationEvidenceClock:
    def now(self) -> Instant:
        return Instant(datetime.now(UTC))


@contextmanager
def conversation_evidence(target: Read15RuntimeTarget) -> Iterator[EvidenceAgent]:
    """Only the explicitly supplied synthetic target; hash verified before SQLite open."""
    target.validate()
    connection = connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)
    try:
        search = SQLiteEvidenceSearchAdapter(BusinessSearchAdapter(connection))
        coordinator = RetrievalCoordinator(
            search_port=search, admissibility_port=search,
            policy=RetrievalCoordinationPolicy(
                (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL),
                (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL), 10, 3, 60,
            ),
        )
        content = SQLiteEvidenceDocumentContentAdapter(DocumentContentAccessAdapter(connection),
                                                        ConversationEvidenceClock())
        with SQLiteLocalSearchAdapter(connection).read_snapshot():
            yield EvidenceAgent(coordinator, content, EvidenceMaterializationPolicy(1000))
    finally:
        connection.close()


class UnapprovedGenerationJob:
    """Real product refusal: no live authority may be inferred from implementation approval."""
    def authorize(self, request: ConversationDraftRequest) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def start(self, request: ConversationDraftRequest) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def poll(self) -> GenerationJobResult | None:
        return None

    def close(self) -> None:
        return None


def conversation_provider_configuration() -> EffectiveProviderConfiguration:
    """Pure proposed profile. Neither configuration nor a cost ceiling grants live authority.

    The 32768 input allowance remains unproved: default product dispatch stays disabled.
    This function never reads environment, a secret, a configuration file or a runtime.
    """
    provider_id = ProviderProfileId("openai.r2")
    model_id = ModelProfileId("openai.gpt-5.6-terra.generation")
    return EffectiveProviderConfiguration(
        ProviderConfigurationVersion(1, 0),
        (ProviderProfileConfig(provider_id, ProviderCode("openai"),
                               ProviderCredentialRef("openai.r2.generation")),),
        (ModelProfileConfig(model_id, provider_id, ModelCode("gpt-5.6-terra"),
            ModelContextLimits(1_050_000, 32768, 4096),
            ProviderInvocationLimits(1, 90000, 32768, 4096, 36864,
                                     ProviderCostLimit(140000, "USD")),
            (ProviderWorkloadKind.GENERATION,), structured_output_required=True),),
        (ProviderRouteConfig(ProviderWorkloadKind.GENERATION, model_id),),
    )


def build_conversation_generation_adapter(*, secret_resolver: ProviderSecretResolver,
    transport_factory: OpenAIResponsesTransportFactory) -> OpenAIGenerationAdapter:
    """Explicit existing-factory binding, inert until invoked by an authorized caller.

    No default resolver/transport acquisition: synthetic validation injects test-only doubles.
    Product CLI does not bind this function before a separately approved live handoff.
    """
    return build_openai_generation_adapter(configuration=conversation_provider_configuration(),
        workload_kind=ProviderWorkloadKind.GENERATION, secret_resolver=secret_resolver,
        transport_factory=transport_factory)


def proposed_conversation_cost() -> Decimal:
    """Conservative documented proposal, not a verified input bound or owner approval."""
    return (Decimal(32768) * Decimal("2") * Decimal("1.25") +
            Decimal(4096) * Decimal("12")) / Decimal(1_000_000)


def observe_conversation_ambiguity() -> None:
    decision = WorkflowSelector().select(WorkflowRequirements(
        blocking_ambiguity=True, human_gate_required=True,
        external_evidence_required=True, production_required=True))
    if (decision.status is not WorkflowSelectionStatus.WAITING_HUMAN
            or decision.stages or decision.overlays != (WorkflowKind.WF_10,)):
        raise ConversationRejected("APPLICATION_FAILURE")
    # WF-10 is observed, never compiled, dispatched or granted an application action.


@dataclass(frozen=True, slots=True)
class ConversationComposition:
    service: ConversationService
    endpoint: ConversationEndpoint
    production: ProductionEndpoint


def build_conversation(*, jobs: GenerationJobPort | None = None) -> ConversationComposition:
    def clock() -> datetime:
        return datetime.now(UTC)
    def new_id(prefix: str) -> str:
        return prefix + ":" + uuid4().hex
    identifier = new_id("conv")
    expires = clock() + timedelta(hours=2)
    store = ConversationMemoryStore(initial_conversation(identifier, expires))
    service = ConversationService(conversation_id=identifier, store=store,
        jobs=jobs if jobs is not None else UnapprovedGenerationJob(), contexts=ConversationContextService(),
        new_id=new_id, clock=clock, expires_at=expires, ambiguity_observer=observe_conversation_ambiguity)
    inbound = ProductionUseCaseInbound(ReadProductionQuery(store), conversation_id=identifier)

    def read(production: str, version: str, correlation: str) -> UseCaseResult[object, object]:
        try:
            service.snapshot()  # Expiration/access gate; no polling, provider, credential or SQLite.
        except ConversationRejected as error:
            raise ConversationInputError(error.code) from None
        corr = CorrelationId(correlation)
        request = UseCaseRequest(meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0, "r2-read", "r2-read-production", None, corr, Instant(clock()),
            ActorRef(ActorKind.APPLICATION, "r2-read"), InvocationStatus.PLANNED),
            use_case_id="application.read_production", payload={"production_ref": production, "version_ref": version},
            actor_context=UseCaseContext(corr))
        return inbound.invoke(request=request)
    return ConversationComposition(service, ConversationEndpoint(ConversationApplicationInbound(service),
                                    token_urlsafe(32)), ProductionEndpoint(read))
