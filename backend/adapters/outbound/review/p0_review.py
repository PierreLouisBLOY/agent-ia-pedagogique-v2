"""Reuse AG-04/CAP-V01 for P0; no SDK, credential or ambient transport."""
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from backend.agent_runtime.agents.review import (
    ResolvedReviewTarget,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewPort,
    ReviewPreparationRequest,
    ReviewResultMaterializationRequest,
)
from backend.agent_runtime.agents.review.review_security_model import ReviewSecurityPolicy
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    InvocationStatus,
    ReviewDimension,
    ReviewRequest,
    ReviewStatus,
)
from backend.core_contracts.capability import CapabilityId
from backend.infrastructure.composition.bindings.r3_agents import version_target
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    items,
    object_data,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


class P0ReviewAdapter:
    def __init__(self, port: ReviewPort, *, authorize: Callable[[Mapping[str, object]], bool]) -> None:
        self.port, self.permission = port, authorize

    def authorize(self, *, request: Mapping[str, object]) -> bool:
        return self.permission(request)

    def review(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        production = object_data(request["production"])
        target = version_target(str(production["production_ref"]), str(production["version_ref"]))
        now = Instant(datetime.now(UTC))
        meta = ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, "p0-review", "p0-review", None,
            CorrelationId("p0-review"), now, ActorRef(ActorKind.AGENT, "AG-04"), InvocationStatus.PLANNED)
        evidence = object_data(request["evidence_pack"])
        canonical = ReviewRequest(meta, target, tuple(ReviewDimension),
            {"scope": "P0_REQUEST_EVIDENCE_PRODUCTION", "no_promotion": True},
            tuple(str(r["evidence_id"]) for r in items(evidence["passages"], 8)),
            {}, {}, {"separate_from_generation": True, "external_oracle_excluded": True})
        agent = ReviewerAgent(ReviewCoordinator(self.port))
        prepared, result = agent.semantic_review(request=ReviewPreparationRequest(
            CapabilityId("CAP-V01"), canonical,
            ResolvedReviewTarget(target, structured_payload={k: production[k] for k in (
                "title", "context", "sections", "questions", "corrections", "marking")}),
            resolved_inputs={"passages": evidence["passages"], "plan": request["plan"],
                             "structural_validation": request["validation"]},
            output_contract={"contract_id": "P0-REVIEW-1.0", "no_authority": True}))
        status = ReviewStatus.COMPLETED if result.status.value == "SUCCEEDED" else ReviewStatus.INCOMPLETE
        output_meta = ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, meta.run_id, meta.step_id, None,
            meta.correlation_id, now, ActorRef(ActorKind.AGENT, "AG-04"), status)
        report = agent.build_review_result(request=ReviewResultMaterializationRequest(
            prepared, result, output_meta, "p0-review",
            security_policy=ReviewSecurityPolicy(allow_whole_target_locator=True)))
        return {"contract_id": "P0-REVIEW-1.0", "status": report.meta.status.value,
            "production_ref": production["production_ref"], "version_ref": production["version_ref"],
            "bundle_sha256": request["bundle_sha256"], "overall_assessment": report.overall_assessment.value,
            "correction_required": report.correction_required,
            "coverage": [d.value for d in report.coverage],
            "instruction_coverage": "FULL" if ReviewDimension.INSTRUCTION in report.coverage else "PARTIAL",
            "findings": [{"finding_id": f.finding_id, "dimension": f.dimension.value, "severity": f.severity.value,
                "description": f.description, "rationale": f.rationale, "target_locator": as_plain(f.target_locator),
                "correction_required": f.correction_required, "evidence_refs": [str(r) for r in f.evidence_refs]}
                for f in report.findings],
            "limitations": as_plain(report.limitations), "evidence_refs_used": [str(r) for r in report.evidence_refs_used],
            "created_at": now.value.isoformat(), "promotion": "NOT_PERFORMED"}
