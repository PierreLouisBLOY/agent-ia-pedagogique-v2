"""Normal launcher composition for an adopted stable, unarmed pilot recipe."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, cast

from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    money,
    sha,
)
from backend.adapters.outbound.generation.openai.p0_pilot_mixed_ledger import P0PilotMixedLedger
from backend.adapters.outbound.persistence.p0_pilot_confirmation import P0PilotConfirmationStore
from backend.adapters.outbound.persistence.p0_pilot_incident import P0PilotIncidentDisposition
from backend.infrastructure.composition.factories.p0_normal_profile import (
    LocalTokenizerHelper,
    read_descriptor,
    strict_document,
    verify_source_package,
    windows_operator,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import descriptor
from backend.infrastructure.composition.factories.p0_pilot_effect_startup import (
    P0PilotEffectStartup,
)
from backend.infrastructure.composition.factories.p0_pilot_on_demand_binding import (
    P0PilotOnDemandBinding,
)
from backend.infrastructure.composition.factories.p0_pilot_on_demand_contract import (
    DOCUMENTS,
    RECOVERY_OPERATION,
    RETAINED_OPERATION,
    validate_recipe,
)
from backend.infrastructure.composition.factories.p0_pilot_on_demand_finalizer import (
    Effect,
    P0PilotOnDemandFinalizer,
)
from backend.infrastructure.composition.factories.p0_product_consent import product_source_reader
from backend.infrastructure.filesystem import capture_secure_path, read_file_nofollow
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.work_orchestration.application.queries.p0_source_admission import (
    ReadP0SourceAdmission,
)

if TYPE_CHECKING:
    from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
    from backend.adapters.inbound.application.lot2_saved_production import (
        Lot2SavedProductionInbound,
    )
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
    from backend.infrastructure.composition.factories.p0_pilot_candidate_projection_off import (
        P0PilotCandidateProjectionOffComposition,
    )
    from backend.infrastructure.composition.factories.p0_pilot_read_off import (
        P0PilotReadOffComposition,
    )
    from backend.modules.work_orchestration.application.services.p0_creation import (
        P0CreationService,
    )


_FIELDS = {"schema", "status", "candidate_scope_sha256", "read_scope_sha256",
    "recipe", "normal_profile", "financial_admission", "templates",
    "frozen_inventory", "historical_diagnostics", "confirmation_root",
    "documents_root"}
_RECOVERY_FIELDS = _FIELDS | {"incident"}
_CANDIDATE = "58cf32a15f9b696f889855ac7831ade8d762439d6a49d2b144bc7ff14b90b044"


def isolated_roots(*roots: Path) -> None:
    """Keep new temporal records outside every retained store, including aliases."""
    identities = [capture_secure_path(root, allowed_root=root) for root in roots]
    if any(not identity.is_directory for identity in identities):
        raise ValueError("P1_PILOT_ON_DEMAND_ROOT_REQUIRED")
    for index, left in enumerate(identities):
        for right in identities[index + 1:]:
            if (left.same_identity(right)
                or left.path.is_relative_to(right.path)
                or right.path.is_relative_to(left.path)):
                raise ValueError("P1_PILOT_ON_DEMAND_ROOT_ALIAS")


class P0PilotOnDemandStartup:
    """OFF at startup; only a final Application command can construct an effect."""

    generation = None

    def __init__(self, *, path: Path, expected_sha256: str,
                 candidate_scope_sha256: str, read_scope_sha256: str,
                 candidate: P0PilotCandidateProjectionOffComposition,
                 historical: P0PilotReadOffComposition,
                 target: Read15RuntimeTarget, saved_root: Path,
                 application_root: Path) -> None:
        raw = read_file_nofollow(path, allowed_root=path.parent, maximum_bytes=32_768)
        if sha(raw) != expected_sha256:
            raise ValueError("P1_PILOT_ON_DEMAND_PROFILE_CHANGED")
        profile = strict_document(raw)
        retained = profile.get("schema") == "P1-PILOT-ON-DEMAND-RETAINED-CHILD-1.0"
        recovery = retained or profile.get("schema") == "P1-PILOT-ON-DEMAND-RECOVERY-1.0"
        closed(profile, _RECOVERY_FIELDS if recovery else _FIELDS,
            "P1_PILOT_ON_DEMAND_PROFILE_FIELDS")
        if (profile["schema"] != "P1-PILOT-ON-DEMAND-STARTUP-1.0"
            and not recovery):
            raise ValueError("P1_PILOT_ON_DEMAND_PROFILE_NOT_ADOPTED")
        if (profile["status"] != "OWNER_ADOPTED_EXACT_STABLE_PROFILE"
            or profile["candidate_scope_sha256"] != candidate_scope_sha256
            or profile["read_scope_sha256"] != read_scope_sha256):
            raise ValueError("P1_PILOT_ON_DEMAND_PROFILE_NOT_ADOPTED")
        recipe = cast(Mapping[str, object], read_descriptor(profile["recipe"]))
        normal = cast(Mapping[str, object], read_descriptor(profile["normal_profile"]))
        if normal.get("schema") != "P0-NORMAL-PROFILE-1.0":
            # This pilot's admitted CANONICAL_NOTION_ONLY reader is the V1
            # source reader. Contextual profile receipts require another
            # exact adoption and are outside this one-candidate lot.
            raise ValueError("P1_PILOT_ON_DEMAND_SOURCE_READER_CHANGED")
        templates = {key: cast(Mapping[str, object], read_descriptor(
            cast(Mapping[str, object], profile["templates"])[key])) for key in DOCUMENTS}
        if set(cast(Mapping[str, object], profile["templates"])) != set(DOCUMENTS):
            raise ValueError("P1_PILOT_ON_DEMAND_TEMPLATE_FIELDS")
        validate_recipe(recipe, templates, normal)
        if (recovery != (recipe["operation"] in {RECOVERY_OPERATION, RETAINED_OPERATION})
            or retained != (recipe["operation"] == RETAINED_OPERATION)):
            raise ValueError("P1_PILOT_INCIDENT_RECIPE_CHANGED")
        self.incident: P0PilotIncidentDisposition | None = None
        if recovery:
            incident_value = cast(Mapping[str, object], profile["incident"])
            effect_incident = templates["effect"].get("incident")
            if (not isinstance(incident_value, Mapping)
                or not isinstance(effect_incident, Mapping)
                or canonical(incident_value) != canonical(effect_incident)):
                raise ValueError("P1_PILOT_INCIDENT_PROFILE_CHANGED")
            from backend.adapters.outbound.persistence.p0_pilot_retained_child import (
                compose_incident,
            )
            self.incident = compose_incident(incident_value,
                confirmation_root=Path(str(profile["confirmation_root"])),
                receipt_root=Path(str(normal["receipt_root"])),
                documents_root=Path(str(profile["documents_root"])), retained_child=retained)
            if self.incident.command != recipe["incident_command_id"]:
                raise ValueError("P1_PILOT_INCIDENT_PROFILE_CHANGED")
        if (recipe["request_sha256"] != _CANDIDATE
            or recipe["normal_profile_sha256"] != descriptor(profile["normal_profile"])["sha256"]
            or recipe["source_admission_manifest_sha256"] !=
                descriptor(normal["source_admission_manifest"])["sha256"]
            or recipe["institutional_catalog_sha256"] != normal["institutional_catalog_sha256"]
            or recipe["tariff_sha256"] != descriptor(normal["tariff"])["sha256"]
            or recipe["tokenizer_manifest_sha256"] != descriptor(normal["tokenizer_manifest"])["sha256"]):
            raise ValueError("P1_PILOT_ON_DEMAND_PROFILE_BINDING")
        isolated_roots(Path(str(profile["confirmation_root"])),
            Path(str(profile["documents_root"])), saved_root,
            Path(str(normal["receipt_root"])))
        # The complete code inventory and native Application catalogue are
        # verified by the same normal-profile validators, without provider I/O.
        target.validate()
        verify_source_package(normal, application_root=application_root)
        from backend.infrastructure.composition.factories.institutional_catalog import (
            inspect_institutional_catalog,
        )
        if sha(canonical(inspect_institutional_catalog(target, read=True))) != recipe[
                "institutional_catalog_sha256"]:
            raise ValueError("P1_PILOT_ON_DEMAND_CATALOG_CHANGED")
        tariff = cast(Mapping[str, object], read_descriptor(normal["tariff"]))
        tokenizer = cast(Mapping[str, object], read_descriptor(normal["tokenizer_manifest"]))
        admission = cast(Mapping[str, object], read_descriptor(profile["financial_admission"]))
        if (sha(canonical(admission)) != recipe["financial_admission_sha256"]
            or admission.get("schema") != "LU-P1-PILOT-OWNER-FINANCIAL-PACKAGE-ADMISSION-1.0"
            or admission.get("status") != "ADMITTED_FOR_THIS_PROFILE_ONLY_NO_WINDOW"
            or admission.get("candidate_request_sha256") != _CANDIDATE
            or admission.get("candidate_request_bytes") != 19857
            or admission.get("source_package_sha256") != descriptor(normal["package"])["sha256"]
            or admission.get("source_manifest_sha256") != descriptor(normal["source_manifest"])["sha256"]
            or tariff.get("owner_admission_sha256") != recipe["financial_admission_sha256"]
            or admission.get("tokenizer_manifest_sha256") != recipe["tokenizer_manifest_sha256"]
            or admission.get("conservative_bound_usd") != "0.1237945"
            or admission.get("tariff_input_usd_per_million") != tariff.get("input_usd_per_million")
            or admission.get("cache_write_multiplier") != tariff.get("input_multiplier")
            or admission.get("tariff_output_usd_per_million") != tariff.get("output_usd_per_million")
            or admission.get("tiktoken_version") != tokenizer.get("package_version")
            or admission.get("encoding") != "o200k_base"):
            raise ValueError("P1_PILOT_ON_DEMAND_FINANCIAL_ADMISSION_REQUIRED")
        read_descriptor(normal["tariff_evidence"], json_document=False)
        exact = candidate._store.read()
        if exact is None:
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        candidate._restore(exact)
        request = object_data(exact["request"])
        body = NormalP0GenerationAdapter.body(build_p0_content_request(request))
        if len(body) != 19857 or sha(body) != recipe["request_sha256"]:
            raise ValueError("P1_PILOT_EXACT_CANDIDATE_REQUIRED")
        counted = LocalTokenizerHelper(tokenizer, str(recipe["tokenizer_manifest_sha256"]),
            application_root=application_root)(body)
        if (type(counted.get("all_string_values_and_keys_tokens")) is not int
            or type(counted.get("serialized_json_tokens")) is not int):
            raise ValueError("P1_PILOT_ON_DEMAND_TOKENIZER_CHANGED")
        tokens = max(cast(int, counted["all_string_values_and_keys_tokens"]),
            cast(int, counted["serialized_json_tokens"]))
        upper = max(len(body), tokens) + 10000
        cost = (Decimal(upper) * money(tariff["input_usd_per_million"])
            * money(tariff["input_multiplier"])
            + Decimal(4096) * money(tariff["output_usd_per_million"])) / Decimal(1000000)
        if (counted.get("encoding") != "o200k_base"
            or counted.get("manifest_sha256") != recipe["tokenizer_manifest_sha256"]
            or counted.get("request_sha256") != recipe["request_sha256"]
            or counted.get("provider_calls") != 0
            or tokens != 5296 or upper != 29857
            or cost != money("0.1237945")):
            raise ValueError("P1_PILOT_ON_DEMAND_FINANCIAL_CALCULATION_CHANGED")
        source_manifest = cast(Mapping[str, object], read_descriptor(
            normal["source_admission_manifest"], canonical_required=False))
        source = ReadP0SourceAdmission(source_manifest,
            manifest_sha256=str(recipe["source_admission_manifest_sha256"]),
            adopted_manifest_sha256=str(recipe["source_admission_manifest_sha256"]),
            owner_admission_sha256=str(templates["permission"]["owner_decision_sha256"]))
        self.source_receipts = product_source_reader(target=target, admission=source)
        self.candidate, self.historical = candidate, historical
        self.candidate_scope_sha256 = candidate_scope_sha256
        self.read_scope_sha256 = read_scope_sha256
        self.target, self.saved_root = target, saved_root
        self.recipe, self.templates, self.normal = recipe, templates, normal
        self.store = candidate._store
        self.financial = {"tariff_sha256": recipe["tariff_sha256"],
            "tokenizer_manifest_sha256": recipe["tokenizer_manifest_sha256"],
            "admission_sha256": recipe["financial_admission_sha256"],
            "input_upper_tokens": 29857, "max_output_tokens": 4096,
            "input_usd_per_million": "2.00", "input_multiplier": "1.25",
            "output_usd_per_million": "12.00", "cost_bound_usd": "0.1237945",
            "admission_status": "OWNER_ADMITTED_EXACT_PILOT"}
        self.confirmation = P0PilotConfirmationStore(Path(str(profile["confirmation_root"])),
            recipe_sha256=sha(canonical(recipe)), baseline_slots=5 if retained else 4 if recovery else 3,
            right_id=str(recipe["right_id"]) if retained else None)
        self.documents_root = Path(str(profile["documents_root"]))
        self.frozen_inventory = profile["frozen_inventory"]
        self.historical_diagnostics = profile["historical_diagnostics"]
        self.application_root = application_root
        self._finalizer: P0PilotOnDemandFinalizer | None = None
        self._recovery_effects: list[Effect] = []

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint
             ) -> Callable[[Lot2SavedProductionInbound], None]:
        def make_effect(effect_path: Path, effect_sha: str,
                        pending_check: Callable[[Mapping[str, object]], None]) -> Effect:
            incident_roots = ({"incident_confirmation_root": self.confirmation.root,
                "incident_documents_root": self.documents_root}
                if getattr(self, "incident", None) is not None else {})
            effect = P0PilotEffectStartup(path=effect_path, expected_sha256=effect_sha,
                candidate_scope_sha256=self.candidate_scope_sha256,
                read_scope_sha256=self.read_scope_sha256,
                candidate=self.candidate, historical=self.historical,
                target=self.target, saved_root=self.saved_root,
                pending_check=pending_check, **incident_roots)
            return cast(Effect, effect)

        finalizer = P0PilotOnDemandFinalizer(recipe=self.recipe,
            templates=self.templates, normal_profile=self.normal,
            documents_root=self.documents_root, confirmation=self.confirmation,
            service=service, effect_factory=make_effect,
            incident=getattr(self, "incident", None))
        binding = P0PilotOnDemandBinding(candidate=self.candidate, store=self.store,
            recipe=self.recipe, financial_evidence=self.financial,
            admission_reader=self.source_receipts, finalize=finalizer.execute)
        binding.bind(service, endpoint)
        def revoke(payload: Mapping[str, object]) -> dict[str, object]:
            data = object_data(payload, {"recipe_sha256"})
            recipe_sha = sha(canonical(self.recipe))
            if data["recipe_sha256"] != recipe_sha:
                raise ValueError("P1_PILOT_REVOCATION_RECIPE_CHANGED")
            frozen = cast(Mapping[str, object], read_descriptor(
                self.frozen_inventory, canonical_required=False))
            diagnostics = cast(Mapping[str, object], read_descriptor(
                self.historical_diagnostics, canonical_required=False))
            if (frozen.get("schema") != "LU-P1-OWNER-TWENTY-NATIVE-IDENTITIES-1.0"
                or not isinstance(frozen.get("frozen_inventory"), list)
                or diagnostics.get("schema") != "P1-PILOT-HISTORICAL-DIAGNOSTICS-1.0"
                or not isinstance(diagnostics.get("frozen_inventory"), list)):
                raise ValueError("P1_PILOT_REVOCATION_INVENTORY_CHANGED")
            ledger = P0PilotMixedLedger(root=Path(str(self.normal["receipt_root"])),
                permission=self.templates["permission"],
                historical=self.historical._validate,
                frozen_inventory=cast(list[Mapping[str, object]], frozen["frozen_inventory"]),
                frozen_inventory_sha256=str(frozen["inventory_sha256"]),
                candidate_request_sha256=str(self.recipe["request_sha256"]),
                candidate_preparation_sha256=str(self.recipe["preparation_sha256"]),
                candidate_context_sha256=str(self.recipe["context_sha256"]),
                candidate_reference_set_sha256=str(self.recipe["reference_set_sha256"]),
                clock=lambda: datetime.now(UTC), broker_identity=self,
                historical_extras=cast(list[Mapping[str, object]],
                    diagnostics["frozen_inventory"]),
                incident=getattr(self, "incident", None))
            with ledger.locked():
                marker = self.confirmation.revoke(ledger=ledger,
                    now=datetime.now(UTC), operator=str(windows_operator()["windows_sid"]))
            return {"state": "PILOT_REVOKED", "recipe_sha256": recipe_sha,
                "revocation_sha256": marker, "provider_attempts": 0}
        endpoint.pilot_revoke_execute = revoke
        self._finalizer = finalizer

        def recover(saved: Lot2SavedProductionInbound) -> None:
            """Publish a captured response after restart; never arm a dispatch."""
            pending = self.confirmation.retained_pending()
            if pending is None:
                return
            incident = getattr(self, "incident", None)
            if incident is not None:
                # The retained 406A PENDING is a separate, still uncertain
                # command. Only a new-recipe PENDING can be recovered here.
                incident.read()
            command = str(pending["command_id"])
            paths = {key: self.documents_root / f"p0-derived.{command}.{key}.json"
                for key in DOCUMENTS}
            for key in DOCUMENTS:
                raw = read_file_nofollow(paths[key], allowed_root=self.documents_root,
                    maximum_bytes=131_072)
                if sha(raw) != pending[f"{key}_sha256"]:
                    raise ValueError("P1_PILOT_RECOVERY_DOCUMENT_CHANGED")

            def no_dispatch(_request: Mapping[str, object]) -> None:
                raise ValueError("P1_PILOT_RECOVERY_CANNOT_DISPATCH")

            effect = make_effect(paths["effect"], str(pending["effect_sha256"]),
                no_dispatch)
            self._recovery_effects.append(effect)
            confirmed = effect.generation.confirmed_dispatches()
            if not confirmed:
                return
            if len(confirmed) != 1 or service.generation is not None:
                raise ValueError("P1_PILOT_RECOVERY_BINDING_CHANGED")
            from backend.infrastructure.composition.factories.local_browser import (
                bind_confirmed_p0_publication,
            )
            service.generation = effect.generation
            try:
                bind_confirmed_p0_publication(service, saved, effect.generation)
            finally:
                service.generation = None

        return recover

    def close(self) -> None:
        if self._finalizer is not None:
            self._finalizer.close()
        for effect in self._recovery_effects:
            effect.close()
        self.candidate.close()
