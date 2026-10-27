"""Canonical AG-03 operations, separate from CREATE-only effect permissions."""
import json
from collections.abc import Mapping
from secrets import token_hex

from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
    content_fields_for,
)
from backend.agent_runtime.agents.generation import (
    GenerationCoordinator,
    GenerationPort,
    GeneratorAgent,
)
from backend.agent_runtime.agents.generation.generation_coordination_model import (
    GenerationPreparationRequest,
    PreparedGenerationCall,
)
from backend.agent_runtime.agents.generation.generation_correction_model import (
    CorrectionMaterializationRequest,
    CorrectionPreparationRequest,
    PreparedCorrectionCall,
    ResolvedCorrectionTarget,
)
from backend.agent_runtime.agents.generation.generation_guard import GenerationOutputGuard
from backend.agent_runtime.agents.generation.generation_guard_model import (
    GenerationGuardDisposition,
    GenerationGuardPolicy,
    GenerationGuardRequest,
)
from backend.agent_runtime.contracts import (
    AgentResultStatus,
    ContractMeta,
    CorrectionRequest,
    ProductionRequest,
)
from backend.agent_runtime.security.tool_application import label_untrusted_application_inputs
from backend.core_contracts.capability import CapabilityId
from backend.infrastructure.composition.bindings.r3_agents import operation_meta, version_target
from backend.modules.pedagogical_design.application.services.codesign_media import (
    codesign_parent_projection,
    retain_codesign_media,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.work_orchestration.contracts.dto.operation_identity import OperationIdentity
from backend.modules.work_orchestration.contracts.dto.p0_codesign_trace import (
    correction_paths,
    verify_correction_delta,
)


class CoDesignGenerator:
    def __init__(self, port: GenerationPort) -> None:
        self.agent = GeneratorAgent(GenerationCoordinator(port))

    @staticmethod
    def initial_preparation(*, parent: P0Production, evidence: Mapping[str, object], objective: str,
                            direction: str, identity: OperationIdentity) -> GenerationPreparationRequest:
        if direction not in {"V2_TO_AI", "AI_TO_V2"}:
            raise ValueError("P0_CODESIGN_DIRECTION")
        dispatch = {key: as_plain(parent.data[key]) for key in
                    ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage")}
        dispatch.update(contract_id="R6-P0-DISPATCH-1.0", evidence=as_plain(evidence))
        wire = build_p0_content_request(dispatch)
        inputs = {"parent": codesign_parent_projection(parent), "evidence": as_plain(evidence)}
        labeled, security = label_untrusted_application_inputs(inputs, content_ref="p0:codesign-input",
            forbidden_keys={"credential", "permission_scope", "handler", "gate_decision"}, root_location="codesign_input")
        if security.disposition.value in {"QUARANTINE", "REJECT_CONTENT"}:
            raise ValueError("P0_CODESIGN_INPUT_QUARANTINED")
        canonical = ProductionRequest(operation_meta(identity, "AG-03"), parent.context.resource_type, objective,
            "P0_STRUCTURED_CONTENT", parent.context.data, {"no_authority": True, "preserve_context_and_references": True},
            tuple(str(row["evidence_id"]) for row in items(parent.data["references"], 8)),
            str(parent.version_ref) if direction == "V2_TO_AI" else None)
        return GenerationPreparationRequest(CapabilityId("CAP-G02" if direction == "V2_TO_AI" else "CAP-G01"),
            canonical, resolved_inputs=inputs, labeled_inputs=labeled, input_security_assessments=(security,),
            output_contract={"contract_id": "P0-CODESIGN-CONTENT-1.0", "fields": tuple(sorted(content_fields_for(dispatch))),
                "schema": wire.output_schema, "instructions": wire.instructions})

    def propose(self, *, parent: P0Production, evidence: Mapping[str, object], objective: str,
                direction: str, identity: OperationIdentity,
                correction: CorrectionRequest | None = None) -> tuple[P0Production, Mapping[str, object]]:
        """Only content can change. Application binds fresh identity and exact parent."""
        meta = operation_meta(identity, "AG-03")
        target = version_target(parent.production_ref, parent.version_ref)
        dispatch = {key: as_plain(parent.data[key]) for key in
                    ("production_ref", "version_ref", "context", "context_sha256", "references", "lineage")}
        dispatch.update(contract_id="R6-P0-DISPATCH-1.0", evidence=as_plain(evidence))
        fields = tuple(sorted(content_fields_for(dispatch)))
        wire = build_p0_content_request(dispatch)
        output_contract = {"contract_id": "P0-CODESIGN-CONTENT-1.0", "fields": fields,
                           "schema": wire.output_schema, "instructions": wire.instructions}
        inputs = {"parent": codesign_parent_projection(parent), "evidence": as_plain(evidence)}
        labeled, security = label_untrusted_application_inputs(inputs, content_ref="p0:codesign-input",
            forbidden_keys={"credential", "permission_scope", "handler", "gate_decision"}, root_location="codesign_input")
        if security.disposition.value in {"QUARANTINE", "REJECT_CONTENT"}:
            raise ValueError("P0_CODESIGN_INPUT_QUARANTINED")
        prepared: PreparedGenerationCall | PreparedCorrectionCall
        if correction is not None:
            if correction.meta != meta or correction.target_production_ref != target:
                # created_at is deliberately part of a canonical meta; caller must
                # use the supplied correction meta, not manufacture a replacement.
                if (correction.meta.run_id, correction.meta.step_id, correction.meta.parent_step_id,
                    correction.meta.correlation_id) != (meta.run_id, meta.step_id, meta.parent_step_id, meta.correlation_id):
                    raise ValueError("P0_CODESIGN_CORRECTION_IDENTITY")
                if correction.target_production_ref != target:
                    raise ValueError("P0_CODESIGN_CORRECTION_TARGET")
            prepared, result = self.agent.correct_production(request=CorrectionPreparationRequest(
                CapabilityId("CAP-G03"), correction,
                ResolvedCorrectionTarget(target, parent.context.resource_type, "P0_STRUCTURED_CONTENT",
                    parent.context.data, structured_payload=codesign_parent_projection(parent)),
                resolved_inputs={"evidence": as_plain(evidence)}, output_contract=output_contract))
        else:
            if direction not in {"V2_TO_AI", "AI_TO_V2"}:
                raise ValueError("P0_CODESIGN_DIRECTION")
            preparation = self.initial_preparation(parent=parent, evidence=evidence, objective=objective,
                direction=direction, identity=identity)
            method = self.agent.transform_production if direction == "V2_TO_AI" else self.agent.generate_production
            prepared, result = method(request=preparation)
        assessment = GenerationOutputGuard().assess(request=GenerationGuardRequest(prepared, result,
            GenerationGuardPolicy(require_structured_payload=True, required_payload_keys=fields,
                                  allowed_payload_keys=fields)))
        if result.status.value != "SUCCEEDED" or assessment.disposition not in {
            GenerationGuardDisposition.ALLOW, GenerationGuardDisposition.ALLOW_WITH_WARNINGS}:
            raise ValueError("P0_CODESIGN_OUTPUT_REJECTED")
        dispatch["version_ref"] = "ver:" + token_hex(16)
        dispatch["lineage"] = {**object_data(dispatch["lineage"]), "parent_version_ref": parent.version_ref,
            "source_run_id": identity.run_id, "source_step_id": identity.step_id,
            "source_request_id": "req:" + identity.correlation_id}
        documentary = None
        if correction is not None:
            assert isinstance(prepared, PreparedCorrectionCall)
            # C-12 validates declared addressed/unresolved findings. These remain
            # declarations; only the fresh independent review assesses the child.
            _, corrected = self.agent.build_correction(request=CorrectionMaterializationRequest(
                correction, prepared.target, prepared, result, assessment,
                ContractMeta(correction.meta.schema_version, correction.meta.run_id, correction.meta.step_id,
                    correction.meta.parent_step_id, correction.meta.correlation_id, correction.meta.created_at,
                    correction.meta.actor, AgentResultStatus.SUCCEEDED, correction.meta.trace_flags),
                parent.production_ref, version_target(parent.production_ref, str(dispatch["version_ref"]))))
            documentary = {"contract_id": "P0-C11C12-DOCUMENTARY-1.0", "review_ref": correction.review_ref,
                "parent_bundle_sha256": parent.sha256, "finding_ids": list(correction.finding_ids),
                "allowed_paths": as_plain(correction.allowed_changes["paths"]),
                "addressed_findings": list(corrected.addressed_findings), "unresolved_findings": list(corrected.unresolved_findings),
                "change_summary": corrected.change_summary, "resolution": "FRESH_REVIEW_REQUIRED",
                "new_warnings_json": json.dumps(as_plain(corrected.new_warnings), ensure_ascii=False, sort_keys=True, separators=(",", ":"))}
        candidate = retain_codesign_media(parent, bind_p0_content(dispatch, result.structured_payload))
        if correction is not None:
            from typing import cast
            paths = cast(tuple[tuple[str | int, ...], ...], correction.allowed_changes["paths"])
            verify_correction_delta(parent, candidate, paths)
        controls = {"guard_disposition": assessment.disposition.value,
            "guard_signals": [{"code": signal.code.value, "location": signal.logical_location} for signal in assessment.security_signals],
            "warnings_json": json.dumps(as_plain(result.warnings), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "uncertainties_json": json.dumps(as_plain(result.uncertainties), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "execution_metadata_json": json.dumps(as_plain(result.execution_metadata), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "provided_evidence_refs": list(preparation.request.evidence_refs) if correction is None else list(correction.evidence_refs),
            "declared_evidence_refs_used": list(result.evidence_refs_used),
            "source_usage_declaration": "TECHNICAL_DECLARATION_NOT_VALIDATION", "bundle_sha256": candidate.sha256}
        return candidate, {"correction": documentary, "controls": controls}


def correction_request(parent: P0Production, report: Mapping[str, object], identity: OperationIdentity) -> CorrectionRequest:
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
        fingerprint,
        items,
    )

    if (report.get("status") != "completed"
            or report.get("bundle_sha256") != parent.sha256 or report.get("version_ref") != parent.version_ref):
        raise ValueError("P0_CODESIGN_REVIEW_REQUIRED")
    findings = tuple(str(row["finding_id"]) for row in items(report["findings"], 32)
                     if row["correction_required"] or row.get("severity") == "blocking")
    paths = correction_paths(parent, report)
    return CorrectionRequest(operation_meta(identity, "AG-03"), version_target(parent.production_ref, parent.version_ref),
        "review:" + fingerprint(report), findings,
        tuple(str(row["evidence_id"]) for row in items(parent.data["references"], 8)),
        preserve_constraints={"context_sha256": parent.data["context_sha256"], "references": as_plain(parent.data["references"])},
        allowed_changes={"paths": paths, "finding_ids": findings},
        forbidden_changes={"identity_context_sources": True, "promotion": True},
        expected_delta={"review_findings": as_plain(report["findings"]), "resolution_requires_new_review": True})
