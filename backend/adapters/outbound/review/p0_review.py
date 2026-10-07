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
from backend.agent_runtime.agents.review.review_security_model import (
    ReviewMetadataPolicyVersion,
    ReviewSecurityPolicy,
)
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
from backend.modules.quality_evaluation.contracts.dto.p0_review_report import (
    DIAGNOSTIC_CONTRACT,
    HISTORICAL_CONTRACT,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


class P0ReviewAdapter:
    def __init__(self, port: ReviewPort, *, authorize: Callable[[Mapping[str, object]], bool],
                 metadata_policy_version: ReviewMetadataPolicyVersion = ReviewMetadataPolicyVersion.HISTORICAL) -> None:
        if type(metadata_policy_version) is not ReviewMetadataPolicyVersion:
            raise TypeError("metadata policy version must be a closed review enum")
        self.port, self.permission = port, authorize
        self.metadata_policy_version = metadata_policy_version

    def authorize(self, *, request: Mapping[str, object]) -> bool:
        return self.permission(request)

    def review(self, *, request: Mapping[str, object]) -> Mapping[str, object]:
        production = object_data(request["production"])
        contract = DIAGNOSTIC_CONTRACT if self.metadata_policy_version is ReviewMetadataPolicyVersion.NEGATIVE_AUTHORITY_DIAGNOSTICS_V1 else HISTORICAL_CONTRACT
        target = version_target(str(production["production_ref"]), str(production["version_ref"]))
        now = Instant(datetime.now(UTC))
        meta = ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, "p0-review", "p0-review", None,
            CorrelationId("p0-review"), now, ActorRef(ActorKind.AGENT, "AG-04"), InvocationStatus.PLANNED)
        evidence = object_data(request["evidence_pack"])
        # AG-04 receives the same immutable programme/version/selection as AG-03.
        # It cannot infer an enrichment or an admission from a shared notion label.
        constraints: dict[str, object] = {"scope": "P0_REQUEST_EVIDENCE_PRODUCTION", "no_promotion": True}
        if evidence.get("institutional_resolution") is not None:
            constraints["institutional_alignment"] = evidence["institutional_resolution"]
        if evidence.get("review_axes") is not None:
            constraints["separate_review_axes"] = evidence["review_axes"]
        reviewed = {k: production[k] for k in ("title", "context", "sections", "questions", "corrections", "marking")}
        if production.get("course_chapter") is not None:
            from backend.modules.pedagogical_design.contracts.dto.course_chapter import (
                CourseChapter,
            )

            chapter = CourseChapter(object_data(production["course_chapter"]))
            chapter.bind_production(str(production["production_ref"]))
            content = chapter.projection(teacher=True)
            content.pop("media_assets", None)
            reviewed["course_chapter"] = content
            visuals = chapter.media_review_context()
            if visuals:
                constraints["visual_review_requirements"] = {
                    "axes": ["exactitude", "niveau", "utilite", "coherence", "absence_surinterpretation"],
                    "scope": "EVERY_VISUAL_EXPLICIT_FINDING_IF_UNVERIFIED",
                    "pixel_inspection": "SEPARATE_REQUIRED", "pedagogical_acceptance": "NOT_PERFORMED"}
                reviewed["visuals"] = visuals
        canonical = ReviewRequest(meta, target, tuple(ReviewDimension),
            constraints,
            tuple(str(r["evidence_id"]) for r in items(evidence["passages"], 8)),
            {}, {}, {"separate_from_generation": True, "external_oracle_excluded": True})
        agent = ReviewerAgent(ReviewCoordinator(self.port))
        prepared, result = agent.semantic_review(request=ReviewPreparationRequest(
            CapabilityId("CAP-V01"), canonical,
            ResolvedReviewTarget(target, structured_payload=reviewed),
            resolved_inputs={"passages": evidence["passages"], "plan": request["plan"],
                             "structural_validation": request["validation"]},
            output_contract={"contract_id": contract, "no_authority": True}))
        status = ReviewStatus.COMPLETED if result.status.value == "SUCCEEDED" else ReviewStatus.INCOMPLETE
        output_meta = ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, meta.run_id, meta.step_id, None,
            meta.correlation_id, now, ActorRef(ActorKind.AGENT, "AG-04"), status)
        report = agent.build_review_result(request=ReviewResultMaterializationRequest(
            prepared, result, output_meta, "p0-review",
            security_policy=ReviewSecurityPolicy(allow_whole_target_locator=True,
                metadata_policy_version=self.metadata_policy_version)))
        output = {"contract_id": contract, "status": report.meta.status.value,
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
        if self.metadata_policy_version is ReviewMetadataPolicyVersion.NEGATIVE_AUTHORITY_DIAGNOSTICS_V1:
            output["uncertainties"] = as_plain(result.uncertainties)
        return output
