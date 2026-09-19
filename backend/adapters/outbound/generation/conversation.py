"""M04 neutral port to the existing runtime and the real AG03 candidate."""
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from decimal import Decimal
from typing import NoReturn, cast

from backend.agent_runtime.agents.evidence import EvidenceAgent
from backend.agent_runtime.agents.generation import GenerationPort, GenerationPortRequest
from backend.agent_runtime.policy import CapabilityAuthorizationPolicy
from backend.infrastructure.composition.bindings.conversation_agents import (
    ConversationAgentBindings,
)
from backend.infrastructure.composition.bindings.conversation_routing import (
    execute_conversation_plan,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    LOCAL_REFERENCE_LABEL,
    SECTION_IDS,
    SYNTHETIC_REFERENCE_LABEL,
    ConversationDraft,
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.shared_kernel.time import Instant


class NoGenerationDispatch:
    def generate(self, *, request: GenerationPortRequest) -> NoReturn:
        raise PermissionError("REFERENCE_PREPARATION_NO_DISPATCH")


class ConversationGenerationAdapter:
    def __init__(self, *, evidence: Callable[[], AbstractContextManager[EvidenceAgent]],
                 generation: GenerationPort, clock: Callable[[], Instant],
                 new_id: Callable[[str], str], reserved_cost: Decimal,
                 policy: CapabilityAuthorizationPolicy | None = None,
                 provenance_label: str = SYNTHETIC_REFERENCE_LABEL) -> None:
        if provenance_label not in (SYNTHETIC_REFERENCE_LABEL, LOCAL_REFERENCE_LABEL):
            raise ValueError("REFERENCE_PROVENANCE_REJECTED")
        self.provenance_label = provenance_label
        self.evidence, self.generation, self.clock = evidence, generation, clock
        self.new_id, self.reserved_cost = new_id, reserved_cost
        self.policy = policy or CapabilityAuthorizationPolicy()
        self.last_trace: tuple[str, ...] = ()

    def prepare(self, *, request: ConversationDraftRequest) -> Mapping[str, object]:
        if type(request) is not ConversationDraftRequest:
            raise ConversationRejected("CONTEXT_NOT_CONFIRMED")
        agents = ConversationAgentBindings(request=request, evidence=self.evidence,
            generation=NoGenerationDispatch(), capability_policy=self.policy, new_id=self.new_id,
            provenance_label=self.provenance_label, prepare_only=True)
        try:
            execute_conversation_plan(agents, clock=self.clock, reserved_cost=Decimal("0"))
        finally:
            self.last_trace = tuple(agents.trace)
        prepared = agents.prepared_projection
        if prepared is None or agents.candidate is not None:
            raise ConversationRejected("GENERATION_OUTPUT_INVALID")
        projection = {"operation": prepared.operation.value, "source_step_id": prepared.source_step_id,
            "production_kind": prepared.production_kind, "objective": prepared.objective,
            "output_format": prepared.output_format, "pedagogical_context": as_plain(prepared.pedagogical_context),
            "resolved_inputs": as_plain(prepared.resolved_inputs), "constraints": as_plain(prepared.constraints),
            "evidence_refs": list(prepared.evidence_refs), "target_ref": None,
            "expected_sections": list(prepared.expected_sections), "output_contract": as_plain(prepared.output_contract)}
        return {"status": "READY_NOT_SENT", "projection": projection,
                "references": as_plain(agents.references), "trace": self.last_trace}

    def generate(self, request: ConversationDraftRequest) -> ConversationDraft:
        if type(request) is not ConversationDraftRequest:
            raise ConversationRejected("CONTEXT_NOT_CONFIRMED")
        agents = ConversationAgentBindings(request=request, evidence=self.evidence,
                                           generation=self.generation, capability_policy=self.policy,
                                           new_id=self.new_id, provenance_label=self.provenance_label)
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
                       self.provenance_label + ".",
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
