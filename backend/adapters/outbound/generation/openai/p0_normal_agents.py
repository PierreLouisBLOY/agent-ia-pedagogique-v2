"""Explicit P0 projection through canonical AG03 and unchanged output guards."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import cast

from backend.adapters.outbound.generation.openai.p0_content import CONTENT_FIELDS, bind_p0_content
from backend.agent_runtime.agents.generation.generation_coordination_model import (
    GenerationPreparationRequest,
)
from backend.agent_runtime.agents.generation.generation_coordinator import GenerationCoordinator
from backend.agent_runtime.agents.generation.generation_guard import GenerationOutputGuard
from backend.agent_runtime.agents.generation.generation_guard_model import (
    GenerationGuardDisposition,
    GenerationGuardPolicy,
    GenerationGuardRequest,
)
from backend.agent_runtime.agents.generation.generation_model import GenerationPortResult
from backend.agent_runtime.contracts import EvidenceItem, LabeledEvidenceItem, ProductionRequest
from backend.agent_runtime.contracts.common import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
)
from backend.agent_runtime.contracts.invocation import InvocationStatus
from backend.agent_runtime.contracts.security import (
    ContentOrigin,
    ContentRole,
    ContentSecurityDisposition,
    ContentTrustClass,
    ContentTrustLabel,
    LabeledContent,
    SecurityBoundary,
)
from backend.agent_runtime.security.content_isolation import (
    ContentIsolationContext,
    InstructionDataBoundaryPolicy,
    scan_content_threats,
)
from backend.agent_runtime.security.tool_application import assess_structured_boundary_content
from backend.core_contracts.capability import CapabilityId
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, object_data
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


def agent_preparation(dispatch: Mapping[str, object], now: datetime) -> GenerationPreparationRequest:
    data = object_data(as_plain(dispatch))
    context, lineage = object_data(data["context"]), object_data(data["lineage"])
    refs = cast(list[dict[str, object]], data["references"])
    evidence = object_data(data["evidence"])
    labeled = []
    for ref in refs:
        identity, source = str(ref["evidence_id"]), str(ref["source_ref"])
        text = cast(str, evidence[identity])
        label = ContentTrustLabel(ContentOrigin.EVIDENCE, ContentRole.EVIDENCE, ContentTrustClass.UNTRUSTED, source)
        content = LabeledContent(identity, text, label, identity)
        assessment = InstructionDataBoundaryPolicy().assess(
            content=content, context=ContentIsolationContext(SecurityBoundary.EVIDENCE),
            signals=scan_content_threats(text, content_ref=identity, logical_location="p0_evidence"))
        labeled.append(LabeledEvidenceItem(EvidenceItem(identity, source, "LOCAL_REFERENCE", str(ref["locator"]),
            Instant(now), authority={"authority": "NONE"}, excerpt_or_summary=text,
            checksum_or_version=str(ref["checksum_or_version"])), content, assessment))
    app_label = ContentTrustLabel(ContentOrigin.APPLICATION_OUTPUT, ContentRole.RESULT,
                                 ContentTrustClass.UNTRUSTED, "p0:prepared-context")
    inputs, input_assessment = assess_structured_boundary_content(context, content_ref="p0:prepared-context",
        label=app_label, boundary=SecurityBoundary.APPLICATION,
        forbidden_keys={"credential", "permission_scope", "handler", "gate_decision"}, root_location="p0_context")
    if input_assessment.disposition in {ContentSecurityDisposition.QUARANTINE, ContentSecurityDisposition.REJECT_CONTENT}:
        raise ValueError("P0_NORMAL_INPUT_QUARANTINED")
    meta = ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, str(lineage["source_run_id"]), str(lineage["source_step_id"]),
                        None, CorrelationId(str(lineage["source_request_id"])), Instant(now),
                        ActorRef(ActorKind.AGENT, "AG-03"), InvocationStatus.PLANNED)
    canonical = ProductionRequest(meta, str(context["resource_type"]),
        "; ".join(cast(list[str], context["objectives"])), "P0_STRUCTURED_CONTENT",
        pedagogical_context=context, constraints={"context_sha256": data["context_sha256"],
                                                 "source_usage_declaration": "NOT_IN_OUTPUT_SCHEMA"},
        evidence_refs=tuple(str(ref["evidence_id"]) for ref in refs))
    return GenerationPreparationRequest(CapabilityId("CAP-G01"), canonical,
        resolved_inputs={"evidence": evidence}, output_contract={"fields": sorted(CONTENT_FIELDS)},
        labeled_evidence=tuple(labeled), labeled_inputs=inputs, input_security_assessments=(input_assessment,))


def parse_content(text: str) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        if len(dict(pairs)) != len(pairs):
            raise ValueError("P0_NORMAL_OUTPUT_DUPLICATE_KEY")
        return dict(pairs)
    if not isinstance(text, str) or not text or len(text.encode()) > 128000:
        raise ValueError("P0_NORMAL_OUTPUT_SIZE")
    result = json.loads(text, object_pairs_hook=unique,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("P0_NORMAL_OUTPUT_NONFINITE")))
    return object_data(result, CONTENT_FIELDS)


def guard_and_bind(dispatch: Mapping[str, object], coordinator: GenerationCoordinator,
                   preparation: GenerationPreparationRequest, result: GenerationPortResult, *,
                   observer: Callable[[Mapping[str, object]], None] | None = None) -> dict[str, object]:
    # Preparing is effect-free; recovery reuses it without execute/generate.
    prepared = coordinator.prepare(request=preparation)
    assessment = GenerationOutputGuard().assess(request=GenerationGuardRequest(prepared, result,
        GenerationGuardPolicy(require_structured_payload=True, required_payload_keys=tuple(sorted(CONTENT_FIELDS)),
                              allowed_payload_keys=tuple(sorted(CONTENT_FIELDS)))))
    if assessment.disposition not in {GenerationGuardDisposition.ALLOW, GenerationGuardDisposition.ALLOW_WITH_WARNINGS}:
        raise ValueError("P0_NORMAL_OUTPUT_GUARD_" + assessment.disposition.value)
    # The six-field provider schema does not declare actual evidence use. Input
    # references are attached truthfully; grounding/review are still reserves.
    bound = bind_p0_content(dispatch, result.structured_payload)
    if observer is not None:
        observer({"contract_id": "P0-GENERATION-CONTROLS-1.0", "production_ref": bound.production_ref,
            "version_ref": bound.version_ref, "context_sha256": dispatch["context_sha256"], "bundle_sha256": bound.sha256,
            "guard_disposition": assessment.disposition.value,
            "guard_warnings": [{"code": sig.code.value, "location": sig.logical_location} for sig in assessment.security_signals],
            "provided_evidence_refs": list(preparation.request.evidence_refs), "declared_evidence_refs_used": [],
            "source_usage_declaration": "NOT_IN_OUTPUT_SCHEMA", "source_status": "RESERVE", "review_state": "NOT_RUN"})
    return cast(dict[str, object], as_plain(bound.data))
