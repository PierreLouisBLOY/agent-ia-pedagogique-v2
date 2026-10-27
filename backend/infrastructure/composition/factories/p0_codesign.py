"""Explicit composition on the normal P0 service; no alternate generator/startup."""
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from backend.adapters.outbound.evidence.p0_active_application import (
    ApplicationEvidenceSearch,
    CoDesignEvidenceSources,
)
from backend.adapters.outbound.evidence.p0_prepared_snapshot import PreparedEvidenceSnapshot
from backend.adapters.outbound.generation.p0_codesign_agents import CoDesignGenerator
from backend.adapters.outbound.generation.p0_codesign_runtime import NativeCoDesign
from backend.agent_runtime.agents.evidence.evidence_agent import EvidenceAgent
from backend.agent_runtime.agents.evidence.retrieval_coordination_model import (
    RetrievalCoordinationPolicy,
)
from backend.agent_runtime.agents.evidence.retrieval_coordinator import RetrievalCoordinator
from backend.agent_runtime.agents.evidence.retrieval_model import RetrievalChannel
from backend.agent_runtime.agents.generation import GenerationPort
from backend.agent_runtime.contracts import BudgetSpec
from backend.agent_runtime.runtime.execution.prelaunch import PreLaunchGuard
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, object_data
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.quality_evaluation.ports.outbound.p0_review import P0ReviewPort
from backend.modules.resource_library.domain.value_objects.search_text import SearchText
from backend.modules.resource_library.ports.inbound.local_search import LocalSearchInbound
from backend.shared_kernel.correlation import CorrelationId


class P0CoDesignBinding:
    def __init__(self, *, search: LocalSearchInbound, generation: GenerationPort, review: P0ReviewPort,
                 guard: PreLaunchGuard, envelope: BudgetSpec, permission_scope_ref: str,
                 authorize: Callable[[Mapping[str, object]], bool]) -> None:
        self.search, self.generation, self.review = search, generation, review
        self.guard, self.envelope, self.authorize = guard, envelope, authorize
        self.permission_scope_ref = permission_scope_ref

    def authorize_chain(self, *, request: Mapping[str, object]) -> bool:
        try:
            SearchText(str(request["evidence_query"]))
        except ValueError:
            raise ValueError("P0_CODESIGN_SEARCH_QUERY_REQUIRED") from None
        return self.envelope.max_retries == 0 and self.authorize(request)

    def run(self, *, request: Mapping[str, object],
            validate_variant: Callable[[Mapping[str, object]], Mapping[str, object]],
            validate_review: Callable[[Mapping[str, object]], None]) -> Mapping[str, object]:
        production = P0Production(object_data(request["production"]))
        dispatch = {key: as_plain(production.data[key]) for key in
            ("context", "context_sha256", "production_ref", "version_ref", "references", "lineage")}
        dispatch.update(contract_id="R6-P0-DISPATCH-1.0", evidence=as_plain(request["evidence"]))
        sources = CoDesignEvidenceSources(PreparedEvidenceSnapshot(dispatch, datetime.now(UTC)),
            ApplicationEvidenceSearch(self.search, CorrelationId(str(request["command_id"]))))
        channels = (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL)
        evidence = EvidenceAgent(RetrievalCoordinator(sources,
            RetrievalCoordinationPolicy(channels, channels, 8, 8, 60), sources), sources)
        runtime = NativeCoDesign(generator=CoDesignGenerator(self.generation), reviewer=self.review,
            evidence=evidence, guard=self.guard, envelope=self.envelope,
            permission_scope_ref=self.permission_scope_ref, chain_authorize=self.authorize)
        return runtime.run(request=request, validate_variant=validate_variant, validate_review=validate_review)
