"""Concrete AG02/AG03 bindings; all authority comes from the compiled delegation."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import replace
from typing import cast

from backend.agent_runtime.agents.evidence import (
    EvidenceAgent,
    EvidenceFetchRequest,
    EvidenceSecurityScanner,
    EvidenceSetBuildRequest,
)
from backend.agent_runtime.agents.generation import (
    GenerationCoordinator,
    GenerationGuardDisposition,
    GenerationGuardPolicy,
    GenerationGuardRequest,
    GenerationOutputGuard,
    GenerationPort,
    GenerationPortResultStatus,
    GenerationPreparationRequest,
    GeneratorAgent,
    ProductionCandidateBuildRequest,
)
from backend.agent_runtime.contracts import (
    ActorKind,
    ActorRef,
    AgentId,
    AgentInvocation,
    AgentResult,
    AgentResultStatus,
    ContractMeta,
    DelegationResult,
    EvidenceRequest,
    EvidenceSet,
    ProductionCandidate,
    ProductionRequest,
    StepSpec,
)
from backend.agent_runtime.policy import (
    CapabilityAuthorizationPolicy,
    PermissionOperation,
    PolicyDisposition,
    ScopeCheck,
)
from backend.agent_runtime.runtime import Plan, RunState
from backend.agent_runtime.security.content_isolation import label_evidence_item
from backend.core_contracts.capability import CapabilityId
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    OUTPUT_CONTRACT_ID,
    SECTION_IDS,
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.shared_kernel.time import Instant

SYNTHETIC_PROVENANCE = "SUPPORT_SYNTHETIQUE_R2 — aucune source officielle attestée"


class ConversationAgentBindings:
    def __init__(
        self, *, request: ConversationDraftRequest,
        evidence: Callable[[], AbstractContextManager[EvidenceAgent]], generation: GenerationPort,
        capability_policy: CapabilityAuthorizationPolicy, new_id: Callable[[str], str],
    ) -> None:
        self.request, self.evidence_factory, self.generation = request, evidence, generation
        self.policy, self.new_id = capability_policy, new_id
        self.evidence_set: EvidenceSet | None = None
        self.candidate: ProductionCandidate | None = None
        self.operations = {"CAP-E01": 0, "CAP-E02": 0, "CAP-E03": 0, "CAP-G01": 0}
        self.references: tuple[Mapping[str, object], ...] = ()
        self.trace: list[str] = []

    def _authorize(self, invocation: AgentInvocation, code: str, now: Instant) -> None:
        delegation = invocation.delegation
        if delegation is None or invocation.attempt != 1:
            raise ConversationRejected("GENERATION_NOT_AUTHORIZED")
        ceiling = 3 if code == "CAP-E02" else 1
        if self.operations[code] >= ceiling:
            raise ConversationRejected("SESSION_CAPACITY_REACHED")
        scope = delegation.permission_scope
        decision = self.policy.evaluate(
            agent_id=invocation.agent_id, scope=scope,
            check=ScopeCheck(principal=scope.principal, capability_id=CapabilityId(code),
                             operation=PermissionOperation.READ if code.startswith("CAP-E")
                             else PermissionOperation.CREATE, resource_scope=scope.resource_scope,
                             constraints=scope.constraints, requested_budget=scope.budget,
                             evaluated_at=now),
        )
        if decision.disposition is not PolicyDisposition.ALLOW:
            raise ConversationRejected("GENERATION_NOT_AUTHORIZED")
        self.operations[code] += 1

    def execute(self, *, plan: Plan, step: StepSpec, run_state: RunState,
                invocation: AgentInvocation, attempt: int, now: Instant) -> DelegationResult[object]:
        if invocation.delegation is None or attempt != 1:
            raise ConversationRejected("GENERATION_NOT_AUTHORIZED")
        planned_meta = replace(invocation.meta, actor=ActorRef(ActorKind.AGENT, invocation.agent_id.value),
                               created_at=now)
        meta = ContractMeta(schema_version=planned_meta.schema_version, run_id=planned_meta.run_id,
            step_id=planned_meta.step_id, parent_step_id=planned_meta.parent_step_id,
            correlation_id=planned_meta.correlation_id, created_at=now, actor=planned_meta.actor,
            status=AgentResultStatus.SUCCEEDED, trace_flags=planned_meta.trace_flags)
        if invocation.agent_id is AgentId.AG_02 and step.capability_id == CapabilityId("CAP-E01"):
            self._authorize(invocation, "CAP-E01", now)
            evidence_request = EvidenceRequest(
                meta=planned_meta,
                search_goal=" OR ".join('"' + topic.replace('"', '""') + '"' for topic in (
                    *cast(tuple[str, ...], self.request.context.values["topics"]), "questions",
                )),
                source_policy={"kinds": ("canonical",)}, filters={"active": True},
                required_authority={"basis": "canonical-registry"}, max_items=3,
            )
            with self.evidence_factory() as agent:
                if agent.retrieval_coordinator.admissibility_port is None:
                    raise ConversationRejected("INSUFFICIENT_EVIDENCE")
                self.trace.append("EvidenceAgent.search_evidence")
                retrieval = agent.search_evidence(request=evidence_request)
                if not 1 <= len(retrieval.ranked_candidates) <= 3:
                    raise ConversationRejected("INSUFFICIENT_EVIDENCE")
                materialized = []
                for index, fused_item in enumerate(retrieval.ranked_candidates):
                    self._authorize(invocation, "CAP-E02", now)
                    self.trace.append("EvidenceAgent.fetch_evidence_item")
                    fetched = agent.fetch_evidence_item(request=EvidenceFetchRequest(
                        f"r2.evidence.{index + 1}", evidence_request, retrieval, fused_item,
                    ))
                    if ("CONTENT_TRUNCATED" in fetched.limitations
                            or not fetched.item.excerpt_or_summary
                            or len(fetched.item.excerpt_or_summary) > 1000
                            or fetched.item.checksum_or_version is None):
                        raise ConversationRejected("INSUFFICIENT_EVIDENCE")
                    materialized.append(fetched)
                self._authorize(invocation, "CAP-E03", now)
                self.trace.append("EvidenceAgent.build_evidence_set")
                evidence_set = agent.build_evidence_set(build_request=EvidenceSetBuildRequest(
                    evidence_request, meta, retrieval, tuple(materialized),
                ))
            # Snapshot is closed before any call to the generation port.
            assessment = EvidenceSecurityScanner().assess(evidence_set=evidence_set)
            if evidence_set.conflicts or assessment.suspicious_evidence_ids:
                raise ConversationRejected("INSUFFICIENT_EVIDENCE")
            references = []
            for item in evidence_set.evidence_items:
                source, locator, version = item.source_ref, item.locator, item.checksum_or_version
                if any(not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9:._-]{1,240}", value)
                       is None for value in (source, locator, version)):
                    raise ConversationRejected("INSUFFICIENT_EVIDENCE")
                references.append({"evidence_id": item.evidence_id, "source_ref": source,
                                   "locator": locator, "version_ref": version,
                                   "checksum_sha256": hashlib.sha256(
                                       str(item.excerpt_or_summary).encode()).hexdigest(),
                                   "provenance_label": SYNTHETIC_PROVENANCE,
                                   "declared_used": False})
            self.evidence_set, self.references = evidence_set, tuple(references)
            result_ref = "r2-evidence-" + self.request.generation_id[4:]
        elif invocation.agent_id is AgentId.AG_03 and step.capability_id == CapabilityId("CAP-G01"):
            if self.evidence_set is None or self.candidate is not None:
                raise ConversationRejected("INSUFFICIENT_EVIDENCE")
            self._authorize(invocation, "CAP-G01", now)
            evidence_items = self.evidence_set.evidence_items
            canonical = ProductionRequest(
                meta=planned_meta, production_kind="ASSESSMENT",
                brief=self.request.brief, output_format="structured-sections",
                pedagogical_context=self.request.context.as_dict(), expected_sections=SECTION_IDS,
                evidence_refs=tuple(item.evidence_id for item in evidence_items),
            )
            preparation = GenerationPreparationRequest(
                capability_id=CapabilityId("CAP-G01"), request=canonical,
                output_contract={"id": OUTPUT_CONTRACT_ID},
                resolved_inputs={"evidence": tuple({
                    "evidence_id": item.evidence_id, "text": item.excerpt_or_summary,
                    "source_ref": item.source_ref, "locator": item.locator,
                    "version_or_checksum": item.checksum_or_version,
                    "provenance_label": SYNTHETIC_PROVENANCE,
                } for item in evidence_items)},
                labeled_evidence=tuple(label_evidence_item(item) for item in evidence_items),
            )
            generator = GeneratorAgent(GenerationCoordinator(self.generation))
            self.trace.extend(("GeneratorAgent.generate_production", "GenerationCoordinator"))
            prepared, technical = generator.generate_production(request=preparation)
            self.trace.append("GenerationOutputGuard.assess")
            assessment_generation = GenerationOutputGuard().assess(request=GenerationGuardRequest(
                prepared, technical, GenerationGuardPolicy(
                    grounding_required=True, require_structured_payload=True,
                    required_payload_keys=("sections",), allowed_payload_keys=("sections",),
                    section_container_key="sections",
                ),
            ))
            if (assessment_generation.disposition not in {
                GenerationGuardDisposition.ALLOW, GenerationGuardDisposition.ALLOW_WITH_WARNINGS,
            } or not technical.evidence_refs_used):
                raise ConversationRejected("GENERATION_OUTPUT_INVALID")
            result_meta = replace(meta, status=AgentResultStatus.SUCCEEDED
                                  if technical.status is GenerationPortResultStatus.SUCCEEDED
                                  else AgentResultStatus.PARTIAL)
            self.trace.append("GeneratorAgent.build_candidate")
            self.candidate = generator.build_candidate(request=ProductionCandidateBuildRequest(
                canonical, prepared, technical, assessment_generation, result_meta, self.new_id("prod"),
            ))
            result_ref = self.candidate.production_id
        else:
            raise ConversationRejected("GENERATION_NOT_AUTHORIZED")
        agent_result: AgentResult[object] = AgentResult(meta=meta, invocation_id=invocation.invocation_id,
            payload={"result_ref": result_ref}, artifact_refs=(result_ref,))
        return DelegationResult(
            delegation_id=invocation.delegation.delegation_id, source_agent=invocation.agent_id,
            delegation=invocation.delegation,
            agent_result=agent_result,
        )
