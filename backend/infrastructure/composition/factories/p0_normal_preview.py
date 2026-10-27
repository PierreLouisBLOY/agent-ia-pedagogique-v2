"""Read-only preparation on a PROPOSED normal profile, never an adopted source receipt."""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal import NormalP0GenerationAdapter
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, preflight, sha
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    prospective_grant,
    validate_permission,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    items,
    object_data,
)
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService

if TYPE_CHECKING:
    from backend.infrastructure.composition.factories.p0_normal_profile import (
        P0NormalProductComposition,
    )


def bind_normal_proposal(owner: P0NormalProductComposition, service: P0CreationService,
                         endpoint: P0CreationEndpoint) -> None:
    if (owner.mode != "prepare-only" or owner.decision["status"] != "PROPOSED"
            or owner.generation is not None or owner.has_resolver
            or service.generation is not None or endpoint.consent_execute is not None):
        raise ValueError("P0_NORMAL_PROPOSAL_BINDING")

    def preview(operation: str, payload: Mapping[str, object]) -> dict[str, object]:
        if operation != "consent_preview":
            raise ValueError("P0_NORMAL_OWNER_ADOPTION_REQUIRED")
        data = object_data(payload, {"command_id", "preparation_ref", "preparation_sha256"})
        value = service.prepared.get(str(data["preparation_ref"]))
        if value is None or sha(canonical(value)) != data["preparation_sha256"]:
            raise ValueError("P0_PREPARATION_CHANGED")
        owner.identities()
        now = datetime.now(UTC)
        context = object_data(value["context"])
        validate_permission(owner.permission, identities=owner.identities(), now=now,
            family=str(context["resource_type"]), level=str(context["level"]))
        manifest = owner.source_manifest
        if (manifest.get("schema") != "P0-SOURCE-ADMISSION-MANIFEST-1.0"
                or manifest.get("status") != "NON_ADOPTE"
                or sha(canonical(manifest["entries"])) != manifest.get("source_scope_sha256")):
            raise ValueError("P0_NORMAL_PROPOSAL_SOURCE_MANIFEST")
        references = items(value["references"], 8)
        sources = []
        for ref in references:
            matches = [entry for entry in items(manifest["entries"], 20_000)
                if all(entry.get(k) == ref.get(v) for k, v in (
                    ("source_ref", "source_ref"), ("locator", "locator"),
                    ("checksum_or_version", "checksum_or_version"), ("excerpt_sha256", "excerpt_sha256")))]
            if len(matches) != 1:
                raise ValueError("P0_NORMAL_PROPOSAL_SOURCE_NOT_IN_MANIFEST")
            entry = matches[0]
            if sha(canonical({k:v for k,v in entry.items() if k != "admission_scope_sha256"})) != entry.get("admission_scope_sha256"):
                raise ValueError("P0_NORMAL_PROPOSAL_SOURCE_CHANGED")
            sources.append({"schema": "P0-NORMAL-PROPOSED-SOURCE-1.0", "reference": as_plain(ref),
                "available_authority": entry["available_authority"], "source_status": as_plain(entry["source_status"]),
                "admission_status": "OWNER_DECISION_PENDING", "provenance": as_plain(entry["provenance"])})
        wire = build_p0_content_request(value)
        raw = NormalP0GenerationAdapter.body(wire)
        identities = owner.grant_identities(value, raw)
        proof = preflight(raw, prospective_grant(owner.permission, identities, now),
            owner.tariff, owner.tokenizer(raw), now=now)
        # No preview acceptance token, grant publication, ledger.locked(), or secret.
        return {"state": "OWNER_NORMAL_ADOPTION_REQUIRED", "schema": "P0-NORMAL-PREPARATION-PREVIEW-1.0",
            "preparation_ref": data["preparation_ref"], "preparation_sha256": data["preparation_sha256"],
            "request_sha256": sha(raw), "request_bytes": len(raw), "request_body_utf8": raw.decode("utf-8"),
            "context_sha256": value["context_sha256"], "reference_set_sha256": sha(canonical(references)),
            "source_proposals": sources, "cost_bound_usd": proof["cost_bound_usd"], "preflight": proof,
            "profile_sha256": owner.permission["profile_sha256"],
            "proposed_permission_sha256": sha(canonical(owner.permission)),
            "tariff_sha256": owner.permission["tariff_sha256"],
            "tokenizer_manifest_sha256": owner.permission["tokenizer_manifest_sha256"],
            "request_parameters": {k: v for k,v in cast(dict[str, object], json.loads(raw)).items()
                if k not in {"instructions", "input", "text"}},
            "admission_status": "OWNER_DECISION_PENDING", "provider_attempts": 0,
            "authority": "NONE", "slot": "NONE", "effect_enabled": False}

    endpoint.consent_execute = preview
    endpoint.generation_bound = False
    endpoint.normal_mode = "PREPARE_ONLY"
