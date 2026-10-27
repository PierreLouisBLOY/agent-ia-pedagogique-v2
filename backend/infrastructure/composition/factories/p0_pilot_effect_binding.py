"""Explicit conditional Application binding for the retained pilot candidate.

No CLI autoload: the factory caller must provide a separately adopted pilot
authority, mixed-history broker and Application source reader.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_pilot_effect_gate import P0PilotEffectGate
from backend.adapters.outbound.persistence.p0_pilot_candidate_off import P0PilotCandidateOffStore
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService
from backend.modules.work_orchestration.application.services.p0_pilot_effect_consent import (
    P0PilotEffectConsentService,
)


class P0PilotEffectBinding:
    def __init__(self, *, store: P0PilotCandidateOffStore, effect: P0PilotEffectGate,
                 source_receipts: Callable[[Mapping[str, object]], Sequence[Mapping[str, object]]],
                 expected_request_sha256: str, expected_preparation_sha256: str,
                 expected_context_sha256: str, expected_reference_set_sha256: str) -> None:
        self.store, self.effect, self.source_receipts = store, effect, source_receipts
        self.expected = (expected_request_sha256, expected_preparation_sha256,
            expected_context_sha256, expected_reference_set_sha256)

    def activate(self, service: P0CreationService) -> P0PilotEffectConsentService:
        """Install the exact gate after final confirmation; retain inbound routing."""
        if service.generation is not None:
            raise ValueError("P1_PILOT_EFFECT_BINDING_CONFLICT")
        record = self.store.read()
        if record is None:
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        request = object_data(record["request"])
        preview = object_data(record["preview"])
        raw = NormalP0GenerationAdapter.body(build_p0_content_request(request))
        actual = (sha(raw), fingerprint(request), request.get("context_sha256"),
            sha(canonical(request.get("references"))))
        if (actual != self.expected or preview.get("request_sha256") != actual[0]
            or preview.get("request_bytes") != len(raw)
            or preview.get("request_body_utf8") != raw.decode("utf-8")
            or record["preparation_sha256"] != actual[1]
            or preview.get("effect_permitted") is not False):
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        ref = str(record["preparation_ref"])
        existing = service.prepared.get(ref)
        if existing is not None and fingerprint(existing) != actual[1]:
            raise ValueError("P1_PILOT_PREPARATION_CONFLICT")
        service.prepared[ref] = request

        def prepared(value: str, pin: str) -> Mapping[str, object]:
            fresh = self.store.read()
            if (fresh is None or fresh["preparation_ref"] != value
                or fresh["preparation_sha256"] != pin or pin != actual[1]
                or fingerprint(fresh["request"]) != actual[1]):
                raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
            # The service cannot dispatch a different volatile preparation.
            resident = service.prepared.get(value)
            if resident is None or fingerprint(resident) != pin:
                raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
            return resident

        consent = P0PilotEffectConsentService(prepared_reader=prepared,
            admission_reader=self.source_receipts, permission=self.effect,
            generate=lambda command: service.execute("generate", command))
        service.generation = self.effect
        return consent

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        if endpoint.consent_execute is not None or endpoint.pilot_candidate_read is None:
            raise ValueError("P1_PILOT_EFFECT_BINDING_CONFLICT")
        consent = self.activate(service)
        endpoint.generation_bound = True
        endpoint.consent_execute = consent.execute
        endpoint.pilot_effect_binding = "EXPLICIT_CONDITIONAL_AUTHORITY"
        endpoint.pilot_preview_execute = None
