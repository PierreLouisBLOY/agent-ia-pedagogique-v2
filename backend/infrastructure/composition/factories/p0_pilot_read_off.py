"""Distinct OFF Application inspection after P1 expiry; historical plan is evidence."""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from backend.adapters.inbound.application.p1_campaign_inspection import P1CampaignInspectionInbound
from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import mapping
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_contract import (
    ANCHOR_FIELDS,
    MANIFEST_FIELDS,
    disposition_target,
    validate_adoption,
    validate_owner_diagnostic,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_reader import (
    P0UnknownOffReader,
    ValidatedUnknownOff,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.p0_normal_profile import (
    read_descriptor,
    verify_source_package,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import descriptor
from backend.infrastructure.composition.factories.p0_pilot_read_scope_off import P0PilotReadScopeOff
from backend.infrastructure.composition.factories.p0_rejected_profile import _document, _native
from backend.infrastructure.composition.factories.p0_unknown_off import PLAN_FIELDS, _historical
from backend.modules.work_orchestration.application.queries.inspect_p1_campaign import (
    InspectP1Campaign,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionRequest,
)
from backend.shared_kernel.correlation import CorrelationId


def _json(value: object, *, canonical_required: bool = True) -> Mapping[str, object]:
    loaded = read_descriptor(value, canonical_required=canonical_required)
    if not isinstance(loaded, Mapping):
        raise ValueError("P1_PILOT_READ_DESCRIPTOR_REQUIRED")
    return loaded


class P0PilotReadOffComposition:
    """No generation, writer, credential or ON binding; only the inspection inbound."""

    generation = None

    def __init__(self, *, scope: P0PilotReadScopeOff, plan_path: Path,
        adoption_path: Path, expected_owner_sha256: str, target: Read15RuntimeTarget,
        saved_root: Path, application_root: Path) -> None:
        if plan_path != scope.plan_path or adoption_path != scope.adoption_path:
            raise ValueError("P1_PILOT_READ_EXACT_DESCRIPTORS_REQUIRED")
        self.scope = scope
        self.path, self.adoption_path = plan_path, adoption_path
        self.expected_owner_sha256 = expected_owner_sha256
        self.target, self.saved_root, self.application_root = target, saved_root, application_root
        self.plan_sha256 = scope.expected[0]
        self._validate()
        reader = P0UnknownOffReader(loader=self._validate, plan_sha256=self.plan_sha256,
            clock=lambda: datetime.now(UTC))
        self.request = P1CampaignInspectionRequest("p1-inspection:" + self.plan_sha256,
            self.plan_sha256)
        self.inbound = P1CampaignInspectionInbound(InspectP1Campaign(reader,
            inspection_ref=self.request.inspection_ref,
            expected_plan_or_profile_sha256=self.plan_sha256))

    def _validate(self) -> ValidatedUnknownOff:
        self.scope.validate()
        plan, pin = _document(self.path)
        closed(plan, PLAN_FIELDS, "P1_PILOT_READ_HISTORICAL_PLAN_FIELDS")
        if (pin != self.plan_sha256 or plan["schema"] != "P0-UNKNOWN-OFF-PLAN-1.0"
            or plan["operation"] != "INSPECT_UNKNOWN_LOCAL_OFF"
            or plan["continuity_enabled"] is not False
            or plan["ledger_writes_allowed"] is not False
            or type(plan["provider_calls_allowed"]) is not int
            or plan["provider_calls_allowed"] != 0
            or not digest(plan["origin_tip_permission_sha256"])
            or any(type(plan[k]) is not str or re.fullmatch(r"[0-9a-f]{40}", str(plan[k])) is None
                for k in ("baseline_commit", "source_tree"))):
            raise ValueError("P1_PILOT_READ_HISTORICAL_PLAN_CHANGED")
        anchor, manifest = _json(plan["anchor"]), _json(plan["manifest"])
        closed(anchor, ANCHOR_FIELDS, "P1_PILOT_READ_ANCHOR_FIELDS")
        closed(manifest, MANIFEST_FIELDS, "P1_PILOT_READ_MANIFEST_FIELDS")
        disposition = _json(manifest["unknown_disposition"])
        disposition_target(disposition)
        components = {"plan_sha256": pin, "anchor_sha256": descriptor(plan["anchor"])["sha256"],
            "manifest_sha256": descriptor(plan["manifest"])["sha256"],
            "disposition_sha256": descriptor(manifest["unknown_disposition"])["sha256"],
            "source_manifest_sha256": descriptor(plan["source_manifest"])["sha256"],
            "package_sha256": descriptor(plan["package"])["sha256"]}
        control, control_sha = _document(self.adoption_path)
        if control_sha != self.scope.expected[1]:
            raise ValueError("P1_PILOT_READ_ADOPTION_CHANGED")
        book = _json(control["book"])
        owner = _json(control["owner_evidence"], canonical_required=False)
        validate_adoption(control, book, owner,
            owner_raw_sha256=str(descriptor(control["owner_evidence"])["sha256"]),
            expected_owner_sha256=self.expected_owner_sha256, components=components)
        if self.expected_owner_sha256 != self.scope.expected[2]:
            raise ValueError("P1_PILOT_READ_OWNER_CHANGED")
        verify_source_package(plan, application_root=self.application_root)
        source = _json(plan["source_manifest"])
        if source["source_commit"] != plan["baseline_commit"] or source["source_tree"] != plan["source_tree"]:
            raise ValueError("P1_PILOT_READ_SOURCE_CHANGED")
        chain = _historical(plan, self.saved_root)
        profile = mapping(chain.current.envelope["profile"], "P1_PILOT_READ_ORIGIN_PROFILE")
        runtime = mapping(plan["target_runtime"], "P1_PILOT_READ_RUNTIME")
        if (anchor["schema"] != "P0-UNKNOWN-OFF-ANCHOR-1.0"
            or manifest["schema"] != "P0-UNKNOWN-OFF-MANIFEST-1.0"
            or plan["origin_tip_permission_sha256"] != chain.current.permission_sha256
            or canonical(manifest["anchor"]) != canonical(plan["anchor"])
            or canonical(manifest["historical_manifest"]) != canonical(profile["continuity_manifest"])
            or canonical(anchor["prior_anchor"]) != canonical(profile["continuity_anchor"])
            or canonical(anchor["original_anchor"]) != canonical(chain.anchor["original_anchor"])
            or any(anchor[k] != chain.manifest[k] for k in
                ("root_permission_sha256", "campaign_namespace_sha256", "root_lock_sha256"))
            or canonical(anchor["owner_diagnostic"]) != canonical(disposition["owner_diagnostic"])
            or canonical(plan["operator_delegation"]) != canonical(profile["operator_delegation"])
            or canonical(runtime) != canonical(profile["runtime"])
            or Path(str(runtime["path"])) != self.target.runtime_path
            or Path(str(runtime["data_root"])) != self.target.data_root
            or runtime["sha256"] != self.target.expected_sha256
            or Path(str(profile["saved_root"])) != self.saved_root
            or canonical(plan["saved_root_native_identity"]) != canonical(_native(self.saved_root))
            or canonical(plan["receipt_root_native_identity"]) != canonical(_native(Path(str(profile["receipt_root"]))))
            or not utc(chain.root.permission["issued_at_utc"]) <= utc(plan["issued_at_utc"])
                < utc(plan["expires_at_utc"]) <= utc(chain.root.permission["expires_at_utc"])):
            raise ValueError("P1_PILOT_READ_HISTORICAL_BINDING")
        for key in ("orientation_adoption", "prior_design_review"):
            read_descriptor(anchor[key], json_document=False)
        self.target.validate()
        validate_owner_diagnostic(_json(disposition["owner_diagnostic"], canonical_required=False),
            chain=chain, disposition=disposition)
        self.scope.validate()
        return ValidatedUnknownOff(plan, pin, chain, manifest, disposition, _json(profile["tariff"]))

    def inspect(self) -> dict[str, object]:
        outcome = self.inbound.inspect(request=self.request,
            correlation_id=CorrelationId("P1_PILOT_READ_OFF"))
        if not outcome.success or outcome.data is None:
            raise ValueError("P1_PILOT_READ_APPLICATION_INSPECTION_REFUSED")
        self.scope.validate()
        return outcome.data.as_dict()
