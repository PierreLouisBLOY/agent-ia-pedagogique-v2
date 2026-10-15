"""Explicit OFF-only composition. Never autoloaded or granted provider authority."""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from backend.adapters.inbound.application.p1_campaign_inspection import P1CampaignInspectionInbound
from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import mapping
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    BoundChainV2,
    bind_chain_v2,
)
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
from backend.infrastructure.composition.factories.p0_normal_profile import (
    read_descriptor,
    verify_source_package,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import descriptor
from backend.infrastructure.composition.factories.p0_rejected_profile import (
    _ancestors,
    _anchor,
    _document,
    _external,
    _native,
    _orientation,
    _proof,
)
from backend.modules.work_orchestration.application.queries.inspect_p1_campaign import (
    InspectP1Campaign,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionRequest,
)
from backend.shared_kernel.correlation import CorrelationId

if TYPE_CHECKING:
    from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
    from backend.modules.work_orchestration.application.services.p0_creation import (
        P0CreationService,
    )

PLAN_FIELDS = {"schema", "operation", "baseline_commit", "source_tree", "source_manifest", "package",
    "historical_profile_envelope", "historical_adoption_control", "origin_tip_permission_sha256",
    "anchor", "manifest", "operator_delegation", "target_runtime", "saved_root_native_identity",
    "receipt_root_native_identity", "issued_at_utc", "expires_at_utc", "continuity_enabled",
    "ledger_writes_allowed", "provider_calls_allowed"}


def _json(value: object, *, canonical_required: bool = True) -> Mapping[str, object]:
    return cast(Mapping[str, object], read_descriptor(value, canonical_required=canonical_required))


def _historical(plan: Mapping[str, object], saved_root: Path) -> BoundChainV2:
    """Hydrate historical authority as evidence, without any generation object."""
    envelope = _json(plan["historical_profile_envelope"])
    current = _proof(envelope, saved_root=saved_root)
    profile = mapping(envelope["profile"], "P0_UNKNOWN_OFF_HISTORICAL_PROFILE")
    manifest = _json(profile["continuity_manifest"])
    anchor = _anchor(profile["continuity_anchor"])
    original = _anchor(anchor["original_anchor"])
    disposition = _json(profile["rejected_disposition"])
    evidence = _json(disposition["observed_evidence"])
    _orientation(disposition, mapping(disposition["target_attempt"], "P0_UNKNOWN_OFF_REJECTED_TARGET"))
    proofs, manifests = _ancestors(manifest["ancestors"], saved_root)
    control_desc = descriptor(plan["historical_adoption_control"])
    control = _json(control_desc)
    pair = mapping(control.get("profile_envelopes"), "P0_UNKNOWN_OFF_HISTORICAL_PAIR")
    closed(pair, {"off", "on"}, "P0_UNKNOWN_OFF_HISTORICAL_PAIR")
    loaded = {k: _json(v) for k, v in pair.items()}
    profiles = {k: mapping(v["profile"], "P0_UNKNOWN_OFF_HISTORICAL_PROFILE") for k, v in loaded.items()}
    if (profiles["off"]["continuity_enabled"] is not False
        or profiles["on"]["continuity_enabled"] is not True
        or canonical(loaded["on"]) != canonical(envelope)
        or any(canonical(profiles[k][name]) != canonical(profile[name]) for k in profiles
            for name in ("source_manifest", "package", "continuity_anchor", "rejected_disposition"))
        or any(mapping(p.envelope["profile"], "P0_UNKNOWN_OFF_ANCESTOR")["schema"] == "P0-NORMAL-PROFILE-4.0"
            and canonical(p.envelope) != canonical(loaded["off"]) for p in proofs)):
        raise ValueError("P0_UNKNOWN_OFF_HISTORICAL_PAIR_BINDING")
    _external(Path(str(control_desc["path"])), components={
        "observed_evidence_sha256": sha(canonical(evidence)),
        "disposition_sha256": sha(canonical(disposition)), "anchor2_sha256": sha(canonical(anchor)),
        "manifest2_sha256": {k: descriptor(v["continuity_manifest"])["sha256"] for k, v in profiles.items()},
        "profile4_OFF_sha256": sha(canonical(profiles["off"])),
        "profile4_ON_sha256": sha(canonical(profiles["on"])),
        "source_manifest_sha256": descriptor(profile["source_manifest"])["sha256"],
        "package_sha256": descriptor(profile["package"])["sha256"],
    }, operation="OFF_ON_COMPONENT_REBIND")
    return bind_chain_v2(manifest, proofs, current, anchor=anchor, original_anchor=original,
        ancestor_manifests=manifests, disposition=disposition, evidence=evidence)


class P0UnknownOffComposition:
    """Trusted exact plan/adoption inputs only; no request can configure them."""

    def __init__(self, *, plan_path: Path, adoption_path: Path, expected_owner_sha256: str,
        target: Read15RuntimeTarget, saved_root: Path, application_root: Path) -> None:
        self.path, self.adoption_path = plan_path, adoption_path
        self.expected_owner_sha256 = expected_owner_sha256
        self.target, self.saved_root, self.application_root = target, saved_root, application_root
        _, self.plan_sha256 = _document(plan_path)
        self._validate()
        self.reader = P0UnknownOffReader(loader=self._validate, plan_sha256=self.plan_sha256,
            clock=lambda: datetime.now(UTC))
        self.request = P1CampaignInspectionRequest("p1-inspection:" + self.plan_sha256, self.plan_sha256)
        self.inbound = P1CampaignInspectionInbound(InspectP1Campaign(self.reader,
            inspection_ref=self.request.inspection_ref, expected_plan_or_profile_sha256=self.plan_sha256))

    def _validate(self) -> ValidatedUnknownOff:
        plan, pin = _document(self.path)
        closed(plan, PLAN_FIELDS, "P0_UNKNOWN_OFF_PLAN_FIELDS")
        if (pin != self.plan_sha256 or plan["schema"] != "P0-UNKNOWN-OFF-PLAN-1.0"
            or plan["operation"] != "INSPECT_UNKNOWN_LOCAL_OFF" or plan["continuity_enabled"] is not False
            or plan["ledger_writes_allowed"] is not False
            or type(plan["provider_calls_allowed"]) is not int or plan["provider_calls_allowed"] != 0
            or not digest(plan["origin_tip_permission_sha256"])
            or any(type(plan[k]) is not str or re.fullmatch(r"[0-9a-f]{40}", str(plan[k])) is None
                for k in ("baseline_commit", "source_tree"))
            or not utc(plan["issued_at_utc"]) <= datetime.now(UTC) < utc(plan["expires_at_utc"])):
            raise ValueError("P0_UNKNOWN_OFF_PLAN_POLICY")
        anchor, manifest = _json(plan["anchor"]), _json(plan["manifest"])
        closed(anchor, ANCHOR_FIELDS, "P0_UNKNOWN_OFF_ANCHOR_FIELDS")
        closed(manifest, MANIFEST_FIELDS, "P0_UNKNOWN_OFF_MANIFEST_FIELDS")
        disposition = _json(manifest["unknown_disposition"])
        disposition_target(disposition)
        components = {"plan_sha256": pin, "anchor_sha256": descriptor(plan["anchor"])["sha256"],
            "manifest_sha256": descriptor(plan["manifest"])["sha256"],
            "disposition_sha256": descriptor(manifest["unknown_disposition"])["sha256"],
            "source_manifest_sha256": descriptor(plan["source_manifest"])["sha256"],
            "package_sha256": descriptor(plan["package"])["sha256"]}
        control, _ = _document(self.adoption_path)
        book, owner = _json(control["book"]), _json(control["owner_evidence"], canonical_required=False)
        validate_adoption(control, book, owner,
            owner_raw_sha256=str(descriptor(control["owner_evidence"])["sha256"]),
            expected_owner_sha256=self.expected_owner_sha256, components=components)
        verify_source_package(plan, application_root=self.application_root)
        source = _json(plan["source_manifest"])
        if source["source_commit"] != plan["baseline_commit"] or source["source_tree"] != plan["source_tree"]:
            raise ValueError("P0_UNKNOWN_OFF_SOURCE_BINDING")
        chain = _historical(plan, self.saved_root)
        profile = mapping(chain.current.envelope["profile"], "P0_UNKNOWN_OFF_ORIGIN_PROFILE")
        runtime = mapping(plan["target_runtime"], "P0_UNKNOWN_OFF_RUNTIME")
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
            raise ValueError("P0_UNKNOWN_OFF_CONTEXT_BINDING")
        for key in ("orientation_adoption", "prior_design_review"):
            read_descriptor(anchor[key], json_document=False)
        self.target.validate()
        validate_owner_diagnostic(_json(disposition["owner_diagnostic"], canonical_required=False),
            chain=chain, disposition=disposition)
        return ValidatedUnknownOff(plan, pin, chain, manifest, disposition, _json(profile["tariff"]))

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        service.generation, endpoint.generation_bound, endpoint.consent_execute = None, False, None

        def snapshot() -> dict[str, object]:
            outcome = self.inbound.inspect(request=self.request,
                correlation_id=CorrelationId("P1_UNKNOWN_LOCAL_OFF"))
            if not outcome.success or outcome.data is None:
                raise ValueError("P0_UNKNOWN_OFF_APPLICATION_INSPECTION_REFUSED")
            return outcome.data.as_dict()

        endpoint.campaign_snapshot = snapshot

    def close(self) -> None:
        pass
