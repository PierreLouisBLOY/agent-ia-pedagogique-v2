"""Unarmed Application binding for one recoverable pilot candidate."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.persistence.p0_pilot_candidate_off import P0PilotCandidateOffStore
from backend.infrastructure.composition.factories.p0_pilot_candidate_projection_off import (
    P0PilotCandidateProjectionOffComposition,
)
from backend.infrastructure.composition.factories.p0_pilot_on_demand_contract import (
    RECOVERY_OPERATION,
    RETAINED_OPERATION,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService
from backend.modules.work_orchestration.application.services.p0_pilot_on_demand_consent import (
    P0PilotOnDemandConsentService,
)


class P0PilotOnDemandBinding:
    """The stable route is present, while service.generation remains absent."""

    generation = None

    def __init__(self, *, candidate: P0PilotCandidateProjectionOffComposition,
                 store: P0PilotCandidateOffStore,
                 recipe: Mapping[str, object],
                 financial_evidence: Mapping[str, object],
                 admission_reader: Callable[[Mapping[str, object]], Sequence[Mapping[str, object]]],
                 finalize: Callable[[Mapping[str, object], Sequence[Mapping[str, object]],
                                    Mapping[str, object], Mapping[str, object], datetime],
                                   dict[str, object]]) -> None:
        if (recipe.get("schema") != ("P1-PILOT-CONFIRMATION-RECIPE-1.1"
            if recipe.get("operation") == RETAINED_OPERATION else "P1-PILOT-CONFIRMATION-RECIPE-1.0")
            or recipe.get("operation") not in {
                "ONE_MANUAL_CREATE_REATTEMPT_OF_UNKNOWN", RECOVERY_OPERATION, RETAINED_OPERATION}
            or recipe.get("approved_cost_bound_usd") != "0.1237945"
            or financial_evidence.get("tariff_sha256") != recipe.get("tariff_sha256")
            or financial_evidence.get("tokenizer_manifest_sha256") !=
                recipe.get("tokenizer_manifest_sha256")
            or financial_evidence.get("admission_sha256") !=
                recipe.get("financial_admission_sha256")
            or financial_evidence.get("cost_bound_usd") != "0.1237945"):
            raise ValueError("P1_PILOT_ON_DEMAND_RECIPE_REQUIRED")
        self.candidate, self.store = candidate, store
        self.recipe = dict(recipe)
        self.recipe_sha256 = sha(canonical(recipe))
        self.financial_evidence = dict(financial_evidence)
        self.admission_reader, self.finalize = admission_reader, finalize

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        if service.generation is not None or endpoint.consent_execute is not None:
            raise ValueError("P1_PILOT_ON_DEMAND_BINDING_CONFLICT")
        self.candidate.bind(service, endpoint)
        record = self.store.read()
        if record is None:
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        self.candidate._restore(record)
        request = object_data(record["request"])
        raw = NormalP0GenerationAdapter.body(build_p0_content_request(request))
        preview = object_data(record["preview"])
        if (len(raw) != 19857
            or sha(raw) != self.recipe["request_sha256"]
            or request.get("context_sha256") != self.recipe["context_sha256"]
            or sha(canonical(request.get("references"))) != self.recipe["reference_set_sha256"]
            or record["preparation_sha256"] != fingerprint(request)
            or preview["request_sha256"] != sha(raw)
            or preview["request_body_utf8"] != raw.decode("utf-8")):
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        ref, pin = str(record["preparation_ref"]), str(record["preparation_sha256"])
        service.prepared[ref] = request

        def prepared(value: str, expected: str) -> Mapping[str, object]:
            fresh = self.store.read()
            resident = service.prepared.get(value)
            if (fresh is None or value != ref or expected != pin
                or fresh["preparation_ref"] != ref
                or fresh["preparation_sha256"] != pin
                or fingerprint(fresh["request"]) != pin
                or resident is None or fingerprint(resident) != pin):
                raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
            return resident

        def stable(request_value: Mapping[str, object],
                   receipts: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
            prepared(ref, pin)
            body = NormalP0GenerationAdapter.body(build_p0_content_request(request_value))
            if sha(body) != sha(raw) or canonical(request_value) != canonical(request):
                raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
            parameters = json.loads(body)
            if not isinstance(parameters, dict):
                raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
            selected = {key: parameters[key] for key in (
                "model", "max_output_tokens", "reasoning", "service_tier",
                "store", "stream", "background", "tools", "tool_choice")}
            return {"schema": "P1-PILOT-STABLE-PREVIEW-1.0",
                "recipe_sha256": self.recipe_sha256,
                "context_sha256": request["context_sha256"],
                "reference_set_sha256": sha(canonical(request["references"])),
                "request_sha256": sha(raw), "request_bytes": len(raw),
                "request_body_utf8": raw.decode("utf-8"),
                "provider": "OPENAI", "model": "gpt-5.6-terra",
                "endpoint": "https://api.openai.com/v1/responses",
                "cost_bound_usd": "0.1237945", "source_receipts": list(receipts),
                "request_parameters": selected,
                "financial_evidence": self.financial_evidence}

        consent = P0PilotOnDemandConsentService(prepared_reader=prepared,
            admission_reader=self.admission_reader, stable_preview=stable,
            finalize=self.finalize)
        endpoint.consent_execute = consent.execute
        if self.recipe["operation"] == RETAINED_OPERATION:
            from backend.adapters.inbound.api.p0_pilot_command_followup import (
                P0PilotCommandFollowup,
            )
            endpoint.pilot_command_followup = P0PilotCommandFollowup(consent.execute)
        endpoint.pilot_preview_execute = None
        endpoint.pilot_effect_binding = "ON_DEMAND_UNARMED"
        if self.recipe["operation"] in {RECOVERY_OPERATION, RETAINED_OPERATION}:
            endpoint.pilot_recovery_incident = str(self.recipe["incident_command_id"])
        endpoint.generation_bound = False
