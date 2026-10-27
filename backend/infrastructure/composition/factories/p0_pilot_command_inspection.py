"""Application inspection composition for an adopted recipe, without startup effects."""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from backend.adapters.inbound.application.p1_campaign_inspection import P1CampaignInspectionInbound
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, closed, utc
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
    P0ContinuityProductLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_reader import (
    ValidatedUnknownOff,
)
from backend.adapters.outbound.persistence.p0_pilot_command_reader import (
    P0PilotCommandReader,
    ValidatedPilotCommandInspection,
)
from backend.adapters.outbound.persistence.p0_pilot_retained_child import compose_incident
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.p0_normal_profile import read_descriptor
from backend.infrastructure.composition.factories.p0_normal_profile_contract import descriptor
from backend.infrastructure.composition.factories.p0_pilot_on_demand_contract import (
    DOCUMENTS,
    RECOVERY_OPERATION,
    RETAINED_OPERATION,
    derive,
    validate_recipe,
)
from backend.infrastructure.composition.factories.p0_pilot_read_off import P0PilotReadOffComposition
from backend.infrastructure.composition.factories.p0_pilot_read_scope_off import P0PilotReadScopeOff
from backend.modules.work_orchestration.application.queries.inspect_p1_campaign import (
    InspectP1Campaign,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionRequest,
)
from backend.shared_kernel.correlation import CorrelationId

PROFILE_FIELDS = {"schema", "status", "candidate_scope_sha256", "read_scope_sha256",
    "recipe", "normal_profile", "financial_admission", "templates", "frozen_inventory",
    "historical_diagnostics", "confirmation_root", "documents_root", "incident"}
CANDIDATE = "58cf32a15f9b696f889855ac7831ade8d762439d6a49d2b144bc7ff14b90b044"


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("P1_PILOT_INSPECTION_OBJECT_REQUIRED")
    return cast(Mapping[str, object], value)


class P0PilotCommandInspectionComposition:
    """Does not construct P0PilotOnDemandStartup, an effect, a grant or recovery."""

    generation = None

    def __init__(self, *, profile_path: Path, expected_sha256: str,
            historical_loader: Callable[[], ValidatedUnknownOff],
            clock: Callable[[], datetime] = lambda: datetime.now(UTC),
            command_id: str | None = None) -> None:
        self._command_id = command_id
        if command_id is not None and re.fullmatch(r"[0-9a-f]{32}", command_id) is None:
            raise ValueError("P1_PILOT_INSPECTION_COMMAND_REQUIRED")
        self._descriptor = {"path": str(profile_path), "sha256": expected_sha256}
        self._historical, self._clock = historical_loader, clock
        self._validate()
        reader = P0PilotCommandReader(loader=self._validate,
            profile_sha256=expected_sha256, clock=clock)
        self.request = P1CampaignInspectionRequest("p1-inspection:" + expected_sha256,
            expected_sha256)
        self.inbound = P1CampaignInspectionInbound(InspectP1Campaign(reader,
            inspection_ref=self.request.inspection_ref,
            expected_plan_or_profile_sha256=expected_sha256))

    def _validate(self) -> ValidatedPilotCommandInspection:
        profile = _mapping(read_descriptor(self._descriptor))
        closed(profile, PROFILE_FIELDS, "P1_PILOT_INSPECTION_PROFILE_FIELDS")
        retained = profile["schema"] == "P1-PILOT-ON-DEMAND-RETAINED-CHILD-1.0"
        if (profile["schema"] not in {"P1-PILOT-ON-DEMAND-RECOVERY-1.0",
                "P1-PILOT-ON-DEMAND-RETAINED-CHILD-1.0"}
                or profile["status"] != "OWNER_ADOPTED_EXACT_STABLE_PROFILE"):
            raise ValueError("P1_PILOT_INSPECTION_ADOPTED_PROFILE_REQUIRED")
        recipe = _mapping(read_descriptor(profile["recipe"]))
        normal = _mapping(read_descriptor(profile["normal_profile"]))
        templates_raw = _mapping(profile["templates"])
        if set(templates_raw) != set(DOCUMENTS):
            raise ValueError("P1_PILOT_INSPECTION_TEMPLATES_CHANGED")
        templates = {key: _mapping(read_descriptor(templates_raw[key])) for key in DOCUMENTS}
        validate_recipe(recipe, templates, normal)
        if (recipe["operation"] != (RETAINED_OPERATION if retained else RECOVERY_OPERATION)
                or recipe["normal_profile_sha256"] != descriptor(profile["normal_profile"])["sha256"]
                or normal.get("schema") != "P0-NORMAL-PROFILE-1.0"
                or recipe["request_sha256"] != CANDIDATE):
            raise ValueError("P1_PILOT_INSPECTION_RECIPE_CHANGED")
        incident_value = _mapping(profile["incident"])
        if canonical(incident_value) != canonical(templates["effect"].get("incident")):
            raise ValueError("P1_PILOT_INSPECTION_PARENT_CHANGED")
        receipt_root = Path(str(normal["receipt_root"]))
        confirmation_root = Path(str(profile["confirmation_root"]))
        documents_root = Path(str(profile["documents_root"]))
        parent = compose_incident(incident_value, confirmation_root=confirmation_root,
            receipt_root=receipt_root, documents_root=documents_root, retained_child=retained)
        parent_record = parent.proposed()
        if (parent.command != recipe["incident_command_id"]
                or parent.expected_sha256 != recipe["incident_disposition_sha256"]
                or recipe["parent_unknown_request_sha256"] != parent_record["parent_unknown_request_sha256"]
                or recipe["request_sha256"] != parent_record["candidate_request_sha256"]
                or retained and self._command_id is None
                or self._command_id in {item.command for item in parent.retained()}):
            raise ValueError("P1_PILOT_INSPECTION_PARENT_OR_COMMAND_CHANGED")
        historical = self._historical()
        historical_profile = _mapping(historical.chain.current.envelope["profile"])
        if (Path(str(historical_profile["receipt_root"])) != receipt_root
                or templates["permission"]["permission_namespace_sha256"] !=
                    historical.chain.manifest["campaign_namespace_sha256"]):
            raise ValueError("P1_PILOT_INSPECTION_ORIGINAL_LOCK_REQUIRED")
        # The existing continuity implementation uses OPEN_EXISTING and retains
        # the original exclusive handle; it cannot publish a missing LOCK.
        ledger = P0ContinuityProductLedger(root=receipt_root,
            permission=historical.chain.current.permission,
            chain_loader=lambda: self._historical().chain,
            broker_identity=self, clock=self._clock)

        def expected_documents(pending: Mapping[str, object]) -> Mapping[str, Mapping[str, object]]:
            command = str(pending["command_id"])
            paths = {key: documents_root / f"p0-derived.{command}.{key}.json"
                for key in DOCUMENTS}
            return derive(recipe, templates, normal,
                at=utc(pending["issued_at_utc"]), paths=paths)

        return ValidatedPilotCommandInspection(str(self._descriptor["sha256"]),
            recipe, confirmation_root, documents_root, receipt_root, parent,
            ledger.locked, expected_documents, self._command_id)

    def inspect(self) -> dict[str, object]:
        outcome = self.inbound.inspect(request=self.request,
            correlation_id=CorrelationId("P1_PILOT_COMMAND_INSPECTION"))
        if not outcome.success or outcome.data is None:
            failure = outcome.application_failure
            raise ValueError(failure.message_key if failure is not None
                else "P1_PILOT_COMMAND_INSPECTION_REFUSED")
        return outcome.data.as_dict()


def compose_p0_pilot_command_inspection(*, profile_path: Path, expected_sha256: str,
        read_scope_path: Path, read_scope_sha256: str, body_scope_sha256: str,
        pilot_runtime_sha256: str, historical_application_root: Path,
        command_id: str | None = None
        ) -> P0PilotCommandInspectionComposition:
    """Reuse the same OFF read authority/target factories as the normal CLI."""
    scope = P0PilotReadScopeOff(path=read_scope_path,
        expected_sha256=read_scope_sha256,
        pilot_body_scope_sha256=body_scope_sha256,
        pilot_runtime_sha256=pilot_runtime_sha256)
    adopted = _mapping(read_descriptor({"path": str(profile_path), "sha256": expected_sha256}))
    if adopted["read_scope_sha256"] != read_scope_sha256:
        raise ValueError("P1_PILOT_INSPECTION_READ_SCOPE_CHANGED")
    plan = _mapping(read_descriptor({"path": str(scope.plan_path),
        "sha256": scope.expected[0]}))
    runtime = _mapping(plan["target_runtime"])
    saved = _mapping(plan["saved_root_native_identity"])
    historical = P0PilotReadOffComposition(scope=scope, plan_path=scope.plan_path,
        adoption_path=scope.adoption_path, expected_owner_sha256=scope.expected[2],
        target=Read15RuntimeTarget(Path(str(runtime["path"])),
            Path(str(runtime["data_root"])), str(runtime["sha256"])),
        saved_root=Path(str(saved["path"])), application_root=historical_application_root)
    return P0PilotCommandInspectionComposition(profile_path=profile_path,
        expected_sha256=expected_sha256, historical_loader=historical._validate,
        command_id=command_id)
