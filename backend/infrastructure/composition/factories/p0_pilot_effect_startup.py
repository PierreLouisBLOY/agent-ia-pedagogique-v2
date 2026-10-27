"""Explicit, fail-closed startup composition for the one retained pilot CREATE.

The OFF candidate is bound first. No provider transport, credential or ledger
writer is reachable unless a separately adopted exact effect profile loads.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    money,
    sha,
)
from backend.adapters.outbound.generation.openai.p0_pilot_effect_broker import (
    P0PilotEffectBroker,
)
from backend.adapters.outbound.generation.openai.p0_pilot_effect_gate import (
    P0PilotEffectGate,
)
from backend.adapters.outbound.openai import OpenAISDKResponsesTransportFactory
from backend.adapters.outbound.persistence.p0_pilot_candidate_off import (
    P0PilotCandidateOffStore,
)
from backend.adapters.outbound.persistence.p0_pilot_incident import (
    P0PilotIncidentDisposition,
)
from backend.infrastructure.composition.factories.p0_local_reference_context import (
    build_local_reference_resolver,
)
from backend.infrastructure.composition.factories.p0_normal_profile import (
    OpenAIEnvironmentSecretResolver,
    P0NormalProductComposition,
    PreparedLocalSecretResolver,
    read_descriptor,
    strict_document,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import (
    descriptor,
)
from backend.infrastructure.composition.factories.p0_pilot_effect_binding import (
    P0PilotEffectBinding,
)
from backend.infrastructure.composition.factories.p0_product_consent import (
    product_source_reader,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderSecretError,
    ProviderSecretErrorCode,
)
from backend.infrastructure.filesystem import read_file_nofollow

if TYPE_CHECKING:
    from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
    from backend.infrastructure.composition.factories.local_browser import (
        Read15RuntimeTarget,
    )
    from backend.infrastructure.composition.factories.p0_pilot_candidate_projection_off import (
        P0PilotCandidateProjectionOffComposition,
    )
    from backend.infrastructure.composition.factories.p0_pilot_read_off import (
        P0PilotReadOffComposition,
    )
    from backend.modules.work_orchestration.application.services.p0_creation import (
        P0CreationService,
    )


_PROFILE_FIELDS = {"schema", "status", "approved_candidate_profile_sha256",
    "candidate_scope_sha256", "read_scope_sha256", "request_sha256",
    "preparation_sha256", "context_sha256", "reference_set_sha256",
    "parent_unknown_request_sha256", "normal_profile", "authority",
    "frozen_inventory", "historical_diagnostics", "approved_cost_bound_usd"}
_RECOVERY_PROFILE_FIELDS = _PROFILE_FIELDS | {"incident"}
_CANDIDATE_PROFILE = "3078030d5524d0303f06e59859f90e2e2289128ed69761bea5a7eceffe47b3ca"
_PARENT = "176b136b4f80b11009d93713fa85e7805c851ad3c466b609a43e45c7fa84cf2b"
_CAMPAIGN_NAMESPACE = "a3269fcc9cabb2548b887f79f347e3fb7e5215bb02207ac2dd5452169a9323ab"
_FROZEN_INVENTORY = "f41b5b8a54c55b82417af9ee48f7c91ab07f5a88762a9b48b0ba2d273c8d3202"
_CANDIDATE = ("58cf32a15f9b696f889855ac7831ade8d762439d6a49d2b144bc7ff14b90b044",
    "bc1d1ea8f51a3b926e3df5dddd2a080588636ab48400307c274a66b18e05131d",
    "42365e353d2222b67aab37157beeb889fe5af18e70510d86642a91a95d2d7024",
    "da81156fb74804ba682a2223ed63474cdb64636ec0cd62a0cb7e046db3ab5d28")


class P0PilotEffectStartup:
    """One Application binding; the normal transport is retained inside its broker."""

    generation: P0PilotEffectGate

    def __init__(self, *, path: Path, expected_sha256: str,
                 candidate_scope_sha256: str, read_scope_sha256: str,
                 candidate: P0PilotCandidateProjectionOffComposition,
                 historical: P0PilotReadOffComposition, target: Read15RuntimeTarget,
                 saved_root: Path,
                 pending_check: Callable[[Mapping[str, object]], None] | None = None,
                 incident_confirmation_root: Path | None = None,
                 incident_documents_root: Path | None = None) -> None:
        raw = read_file_nofollow(path, allowed_root=path.parent, maximum_bytes=16_384)
        if sha(raw) != expected_sha256:
            raise ValueError("P1_PILOT_EFFECT_PROFILE_CHANGED")
        profile = strict_document(raw)
        retained = profile.get("schema") == "P1-PILOT-RETAINED-CHILD-EFFECT-STARTUP-1.0"
        if retained and pending_check is None:
            raise ValueError("P1_PILOT_RETAINED_CHILD_FINALIZER_REQUIRED")
        recovery = retained or profile.get("schema") == "P1-PILOT-RECOVERY-EFFECT-STARTUP-1.0"
        closed(profile, _RECOVERY_PROFILE_FIELDS if recovery else _PROFILE_FIELDS,
            "P1_PILOT_EFFECT_PROFILE_FIELDS")
        if (profile["schema"] != "P1-PILOT-EFFECT-STARTUP-1.0" and not recovery):
            raise ValueError("P1_PILOT_EFFECT_PROFILE_REJECTED")
        if (profile["status"] != "OWNER_ADOPTED_EXACT_EFFECT_PROFILE"
            or profile["approved_candidate_profile_sha256"] != _CANDIDATE_PROFILE
            or profile["candidate_scope_sha256"] != candidate_scope_sha256
            or profile["read_scope_sha256"] != read_scope_sha256
            or tuple(profile[key] for key in ("request_sha256", "preparation_sha256",
                "context_sha256", "reference_set_sha256")) != _CANDIDATE
            or profile["parent_unknown_request_sha256"] != _PARENT
            or money(profile["approved_cost_bound_usd"]) != money("0.1237945")):
            raise ValueError("P1_PILOT_EFFECT_PROFILE_REJECTED")
        if (candidate._scope["read_scope_sha256"] != read_scope_sha256
            or candidate._scope["parent_unknown_request_sha256"] != _PARENT
            or historical.scope.expected[0] != historical.plan_sha256):
            raise ValueError("P1_PILOT_EFFECT_SCOPE_BINDING")
        # The already selected OFF composition keeps the body recoverable.
        record = candidate._store.read()
        preview = record.get("preview") if record is not None else None
        if (record is None or not isinstance(preview, Mapping)
            or record["preparation_sha256"] != _CANDIDATE[1]
            or preview.get("request_sha256") != _CANDIDATE[0]
            or preview.get("context_sha256") != _CANDIDATE[2]
            or preview.get("reference_set_sha256") != _CANDIDATE[3]):
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        normal = P0NormalProductComposition(path=Path(str(descriptor(profile["normal_profile"])["path"])),
            target=target, saved_root=saved_root, credential_source="OPENAI_API_KEY")
        try:
            incident: P0PilotIncidentDisposition | None = None
            if recovery:
                value = profile["incident"]
                if (incident_confirmation_root is None or incident_documents_root is None
                    or not isinstance(value, Mapping)):
                    raise ValueError("P1_PILOT_INCIDENT_PROFILE_CHANGED")
                from backend.adapters.outbound.persistence.p0_pilot_retained_child import (
                    compose_incident,
                )
                incident = compose_incident(value, confirmation_root=incident_confirmation_root,
                    receipt_root=normal.root, documents_root=incident_documents_root,
                    retained_child=retained)
            if (normal.envelope_sha256 != descriptor(profile["normal_profile"])["sha256"]
                or normal.permission["permission_namespace_sha256"] !=
                    _CAMPAIGN_NAMESPACE
                or money(normal.permission["per_call_ceiling_usd"]) > money("0.14")
                or money(normal.permission["cumulative_ceiling_usd"]) > money("1.96")
                or normal.permission["max_calls"] != 14):
                raise ValueError("P1_PILOT_EFFECT_PERMISSION_BINDING")
            inventory_doc = cast(Mapping[str, object], read_descriptor(profile["frozen_inventory"],
                canonical_required=False))
            if (inventory_doc.get("schema") != "LU-P1-OWNER-TWENTY-NATIVE-IDENTITIES-1.0"
                or inventory_doc.get("inventory_sha256") !=
                    _FROZEN_INVENTORY):
                raise ValueError("P1_PILOT_FROZEN_INVENTORY_REQUIRED")
            inventory = inventory_doc.get("frozen_inventory")
            if not isinstance(inventory, list) or len(inventory) != 20:
                raise ValueError("P1_PILOT_FROZEN_INVENTORY_REQUIRED")
            diagnostics_doc = cast(Mapping[str, object], read_descriptor(
                profile["historical_diagnostics"], canonical_required=False))
            if (diagnostics_doc.get("schema") != "P1-PILOT-HISTORICAL-DIAGNOSTICS-1.0"
                or not isinstance(diagnostics_doc.get("frozen_inventory"), list)):
                raise ValueError("P1_PILOT_HISTORICAL_DIAGNOSTIC_PIN_REQUIRED")
            diagnostics = cast(list[Mapping[str, object]], diagnostics_doc["frozen_inventory"])

            def authority() -> Mapping[str, object]:
                # Re-read the adopted bytes at every transition. Any change stops.
                value = cast(Mapping[str, object], read_descriptor(profile["authority"]))
                if (value.get("permission_sha256") != sha(canonical(normal.permission))
                    or value.get("request_sha256") != _CANDIDATE[0]
                    or value.get("preparation_sha256") != _CANDIDATE[1]
                    or value.get("parent_unknown_request_sha256") != _PARENT):
                    raise ValueError("P1_PILOT_EFFECT_AUTHORITY_CHANGED")
                return value

            resolver = (build_local_reference_resolver(target, normal.local_context,
                revalidate=normal.identities) if normal.local_context is not None else None)
            sources = product_source_reader(target=target,
                admission=normal.local_context or normal.admission,
                institutional_resolver=resolver)

            def before_provider_attempt(request: Mapping[str, object]) -> None:
                gate.validate_current_authority(request)
                broker.revalidate_before_attempt(request)
                if pending_check is not None:
                    pending_check(request)
                # Historical/source reads may outlive the pilot's short window.
                gate.validate_current_authority(request)

            broker = P0PilotEffectBroker(permission=normal.permission,
                permission_identities=normal.identities, identity_source=normal.grant_identities,
                tariff=normal.tariff, tokenizer=normal.tokenizer, receipt_root=normal.root,
                resolver=PreparedLocalSecretResolver(normal.resolver), credential_ref=normal.resolver.ref,
                transport=OpenAISDKResponsesTransportFactory(r2_destination=True,
                    environment_key_allowed=isinstance(normal.resolver, OpenAIEnvironmentSecretResolver)),
                historical=historical._validate, frozen_inventory=inventory,
                frozen_inventory_sha256=str(inventory_doc["inventory_sha256"]),
                historical_extras=diagnostics,
                parent_unknown_request_sha256=_PARENT, candidate_request_sha256=_CANDIDATE[0],
                candidate_preparation_sha256=_CANDIDATE[1], candidate_context_sha256=_CANDIDATE[2],
                candidate_reference_set_sha256=_CANDIDATE[3], source_reader=sources,
                before_provider_attempt=before_provider_attempt,
                before_reservation=pending_check,
                approved_cost_bound_usd=str(profile["approved_cost_bound_usd"]),
                local_context_adoption=normal.local_context_adoption,
                incident=incident)
            gate = P0PilotEffectGate(broker=broker, authority=authority,
                candidate_request_sha256=_CANDIDATE[0],
                candidate_preparation_sha256=_CANDIDATE[1],
                parent_unknown_request_sha256=_PARENT,
                approved_cost_bound_usd=str(profile["approved_cost_bound_usd"]),
                expected_operation=("ONE_ADDITIONAL_MANUAL_CREATE_AFTER_2F1E" if retained
                    else "ONE_ADDITIONAL_MANUAL_CREATE_AFTER_406A" if recovery
                    else "ONE_MANUAL_CREATE_REATTEMPT_OF_UNKNOWN"))
            self.generation = gate
            self.broker = broker
            self.source_receipts = sources
            self.binding = P0PilotEffectBinding(store=P0PilotCandidateOffStore(saved_root),
                effect=gate, source_receipts=sources,
                expected_request_sha256=_CANDIDATE[0],
                expected_preparation_sha256=_CANDIDATE[1],
                expected_context_sha256=_CANDIDATE[2],
                expected_reference_set_sha256=_CANDIDATE[3])
            self.candidate, self.normal = candidate, normal
            self.profile_sha256 = expected_sha256
        except Exception:
            normal.close()
            raise

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        # build_local_read15 binds this after constructing Application with no
        # generation; publication is installed after the explicit binder.
        self.candidate.bind(service, endpoint)
        self.binding.bind(service, endpoint)

    def prepare_local_credential(self) -> None:
        """Resolve the inherited environment key before PENDING or reservation."""
        try:
            self.normal.resolver.resolve(self.normal.resolver.ref)
        except ProviderSecretError as error:
            code = ("P1_PILOT_OPENAI_API_KEY_MISSING"
                if error.code is ProviderSecretErrorCode.MISSING_PROVIDER_SECRET
                else "P1_PILOT_OPENAI_API_KEY_EMPTY")
            raise ValueError(code) from None

    def close(self) -> None:
        self.normal.close()
        self.candidate.close()
