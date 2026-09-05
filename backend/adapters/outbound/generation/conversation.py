"""M04 neutral port to the existing runtime and the real AG03 candidate."""
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from decimal import Decimal
from typing import cast

from backend.agent_runtime.agents.evidence import EvidenceAgent
from backend.agent_runtime.agents.generation import GenerationPort
from backend.agent_runtime.policy import CapabilityAuthorizationPolicy
from backend.infrastructure.composition.bindings.conversation_agents import (
    ConversationAgentBindings,
)
from backend.infrastructure.composition.bindings.conversation_routing import (
    execute_conversation_plan,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    SECTION_IDS,
    ConversationDraft,
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.shared_kernel.time import Instant


class ConversationGenerationAdapter:
    def __init__(self, *, evidence: Callable[[], AbstractContextManager[EvidenceAgent]],
                 generation: GenerationPort, clock: Callable[[], Instant],
                 new_id: Callable[[str], str], reserved_cost: Decimal,
                 policy: CapabilityAuthorizationPolicy | None = None) -> None:
        self.evidence, self.generation, self.clock = evidence, generation, clock
        self.new_id, self.reserved_cost = new_id, reserved_cost
        self.policy = policy or CapabilityAuthorizationPolicy()
        self.last_trace: tuple[str, ...] = ()

    def generate(self, request: ConversationDraftRequest) -> ConversationDraft:
        if type(request) is not ConversationDraftRequest:
            raise ConversationRejected("CONTEXT_NOT_CONFIRMED")
        agents = ConversationAgentBindings(request=request, evidence=self.evidence,
                                           generation=self.generation, capability_policy=self.policy,
                                           new_id=self.new_id)
        try:
            execute_conversation_plan(agents, clock=self.clock, reserved_cost=self.reserved_cost)
        finally:
            self.last_trace = tuple(agents.trace)
        candidate = agents.candidate
        if candidate is None or candidate.content is None:
            raise ConversationRejected("GENERATION_OUTPUT_INVALID")
        sections = candidate.structured_payload.get("sections")
        if not isinstance(sections, Mapping) or tuple(sections) != SECTION_IDS:
            raise ConversationRejected("GENERATION_OUTPUT_INVALID")
        refs = tuple({**ref, "declared_used": ref["evidence_id"] in candidate.evidence_refs_used}
                     for ref in agents.references)
        limitations = ["CANDIDATE — NON VALIDÉE : contrôle pédagogique réservé à R3.",
                       "SUPPORT_SYNTHETIQUE_R2 — aucune source officielle attestée.",
                       "Conservation volatile : perdue à l’arrêt du processus."]
        if candidate.warnings or candidate.uncertainties:
            limitations.append("Le générateur a signalé des limites ; une revue humaine est nécessaire.")
        return ConversationDraft(
            candidate.production_id, candidate.content,
            tuple({"section_id": key, "text": cast(str, value)} for key, value in sections.items()),
            refs, {"source_run_id": candidate.lineage["source_run_id"],
                   "source_step_id": candidate.lineage["source_step_id"],
                   "evidence_set_ref": "r2-evidence-" + request.generation_id[4:]},
            tuple(limitations),
        )
