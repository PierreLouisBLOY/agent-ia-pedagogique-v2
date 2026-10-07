"""Existing canonical agents, caller-resolved in-memory projections only."""
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

from backend.agent_runtime.agents.generation import (
    GenerationCoordinator,
    GenerationPort,
    GeneratorAgent,
)
from backend.agent_runtime.agents.generation.generation_coordination_model import (
    GenerationPreparationRequest,
)
from backend.agent_runtime.agents.review import (
    ResolvedReviewTarget,
    ReviewCoordinator,
    ReviewerAgent,
    ReviewPort,
    ReviewPreparationRequest,
    ReviewResultMaterializationRequest,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    InvocationStatus,
    ProductionRequest,
    ReviewDimension,
    ReviewRequest,
    ReviewStatus,
)
from backend.core_contracts.capability import CapabilityId
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    as_plain,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    AssessmentRevisionRequest,
)
from backend.modules.work_orchestration.contracts.dto.operation_identity import OperationIdentity
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant


def operation_meta(identity: OperationIdentity | None, actor: str) -> ContractMeta[InvocationStatus]:
    if identity is None:
        unique = uuid4().hex
        identity = OperationIdentity("run:" + unique, "step:" + unique, None, "run:" + unique)
    if type(identity) is not OperationIdentity:
        raise ValueError("OPERATION_IDENTITY_REJECTED")
    return ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, identity.run_id, identity.step_id,
        identity.parent_step_id, CorrelationId(identity.correlation_id), Instant(datetime.now(UTC)),
        ActorRef(ActorKind.AGENT, actor), InvocationStatus.PLANNED)


def operation_projection(meta: ContractMeta[InvocationStatus]) -> dict[str, object]:
    return OperationIdentity(meta.run_id, meta.step_id, meta.parent_step_id,
                             meta.correlation_id.value).as_dict()


def version_target(production_ref: str, version_ref: str) -> ObjectVersionRef:
    return ObjectVersionRef(TypedEntityRef(TypedEntityId("production", production_ref.split(":")[1])),
                            VersionRef(version_ref))


def transform(port: GenerationPort, request: AssessmentRevisionRequest, *, identity: OperationIdentity | None = None) -> Mapping[str, object]:
    from backend.infrastructure.composition.bindings.r3_harden_projection import harden_projection

    meta = operation_meta(identity, "AG-03")
    canonical = ProductionRequest(meta, "ASSESSMENT", request.operation, "JSON",
        request.context, {"scope": request.operation, "no_authority": True},
        tuple(str(r["evidence_id"]) for r in request.references),
        version_target(request.production_ref, request.base_version_ref), ("R3_RESULT_JSON",))
    prepared, result = GeneratorAgent(GenerationCoordinator(port)).transform_production(
        request=GenerationPreparationRequest(CapabilityId("CAP-G02"), canonical,
            resolved_inputs=(harden_projection(request) if request.operation == "HARDEN_DOSSIER_3" else
                {"subject": as_plain(request.subject),
                 "base_bundle": as_plain(request.base.data) if request.base else None}),
            output_contract={"contract_id": "R3-TRANSFORMATION-1.0", "strict_local_parser": True,
                "operation_identity": operation_projection(meta),
                **({"harden_contract_id": "R3-HARDEN-WIRE-1.0"} if request.operation == "HARDEN_DOSSIER_3" else {}),
                "section": "R3_RESULT_JSON", "encoding": "one JSON object, no fences, no extra keys",
                "prepare_fields": ["questions", "correction", "marking", "case_data", "limitations"],
                "harden_fields": ["dossier_3", "questions_d3", "answers_d3", "marking_d3", "scenarios_d3", "limitations"],
                "identities": {"production_ref": request.production_ref, "version_ref": request.base_version_ref},
                "source_units": "explicit EUR or kEUR label with exact subject locator; convert to EUR without guessing",
                "decimal": "canonical string with two decimals; absolute maximum 999999999.99",
                "calculation_fields": ["case_id", "metric", "value", "locator", "expression"],
                "expression": {"reference": {"ref": "totals.stable_resources"},
                    "operator": {"op": "SUB", "operands": [{"ref": "totals.stable_resources"}, {"ref": "totals.stable_uses"}]},
                    "allowed_operators": ["ADD", "SUB"], "max_depth": 4, "max_operands": 16},
                "max_calculations": 60, "no_authority": True}))
    if result.status.value != "SUCCEEDED" or result.source_step_id != prepared.port_request.source_step_id:
        raise ValueError("R3_GENERATION_OUTPUT")
    return result.structured_payload


def review(port: ReviewPort, bundle: AssessmentBundle, dimensions: tuple[str, ...], *, identity: OperationIdentity | None = None) -> dict[str, object]:
    target = version_target(bundle.production_ref, bundle.version_ref)
    now = Instant(datetime.now(UTC))
    meta = operation_meta(identity, "AG-04")
    canonical = ReviewRequest(meta, target, tuple(ReviewDimension(d) for d in dimensions),
        {"scope": "subject-correction-marking"},
        tuple(str(r["evidence_id"]) for r in items(bundle.data["references"], 3)),
        {}, {}, {"separate_from_generation": True})
    agent = ReviewerAgent(ReviewCoordinator(port))
    # Application-owned provenance/lineage labels are not pedagogical assertions.
    # Keep the subject verbatim, and bind evidence separately in the canonical request.
    # In particular the R2 negative provenance label must not be presented as source text.
    projection = {key: bundle.data[key] for key in (
        "subject", "questions", "correction", "marking", "case_data", "pedagogical_context")}
    prepared, result = agent.semantic_review(request=ReviewPreparationRequest(
        CapabilityId("CAP-V01"), canonical,
        ResolvedReviewTarget(target, content=str(object_data(bundle.data["subject"])["content"]),
                             structured_payload=projection),
        output_contract={"contract_id": "R3-REVIEW-1.0", "operation_identity": operation_projection(meta)}))
    status = ReviewStatus.COMPLETED if result.status.value == "SUCCEEDED" else ReviewStatus.INCOMPLETE
    output_meta = ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, meta.run_id, meta.step_id, meta.parent_step_id,
        meta.correlation_id, now, ActorRef(ActorKind.AGENT, "AG-04"), status)
    materialized = agent.build_review_result(request=ReviewResultMaterializationRequest(
        prepared, result, output_meta, "review:" + meta.step_id))
    return {"status": materialized.meta.status.value,
        "production_ref": bundle.production_ref, "version_ref": bundle.version_ref,
        "subject_sha256": bundle.data["subject_sha256"], "bundle_sha256": bundle.sha256,
        "findings": [{"finding_id": f.finding_id, "dimension": f.dimension.value,
            "severity": f.severity.value, "description": f.description, "rationale": f.rationale,
            "target_locator": as_plain(f.target_locator), "correction_required": f.correction_required,
            "evidence_refs": [str(r) for r in f.evidence_refs]} for f in materialized.findings],
        "overall_assessment": materialized.overall_assessment.value,
        "coverage": [d.value for d in materialized.coverage],
        "limitations": as_plain(materialized.limitations),
        "evidence_refs_used": [str(r) for r in materialized.evidence_refs_used],
        "created_at": now.value.isoformat()}
