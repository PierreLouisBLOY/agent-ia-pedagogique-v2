"""Pure, closed derivation of one pilot authority at final confirmation.

The caller owns persistence and the original LOCK. This module has no I/O,
provider, credential, ledger, or business filesystem access.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    sha,
    utc,
)

RECIPE_FIELDS = {"schema", "operation", "template_projection_sha256", "normal_profile_sha256",
    "request_sha256", "preparation_sha256", "context_sha256", "reference_set_sha256",
    "parent_unknown_request_sha256", "tariff_sha256", "tokenizer_manifest_sha256",
    "financial_admission_sha256",
    "source_admission_manifest_sha256", "institutional_catalog_sha256",
    "approved_cost_bound_usd", "duration_seconds", "max_calls", "retry", "fallback"}
RECOVERY_FIELDS = RECIPE_FIELDS | {"incident_disposition_sha256", "incident_command_id"}
RECOVERY_OPERATION = "ONE_ADDITIONAL_MANUAL_CREATE_AFTER_406A"
RETAINED_OPERATION = "ONE_ADDITIONAL_MANUAL_CREATE_AFTER_2F1E"
RETAINED_FIELDS = RECOVERY_FIELDS | {"prior_incident_disposition_sha256", "right_id"}
DOCUMENTS = ("permission", "decision", "envelope", "authority", "effect")


def projection(templates: Mapping[str, Mapping[str, object]]) -> dict[str, dict[str, object]]:
    """Exactly the fields approved before any clock value exists."""
    if set(templates) != set(DOCUMENTS):
        raise ValueError("P1_PILOT_ON_DEMAND_TEMPLATE_FIELDS")
    values = {key: deepcopy(dict(templates[key])) for key in DOCUMENTS}
    for field in ("owner_decision_sha256", "issued_at_utc", "expires_at_utc"):
        values["permission"].pop(field, None)
    values["decision"].pop("permission_policy_sha256", None)
    for field in ("decision", "permission"):
        values["envelope"].pop(field, None)
    for field in ("permission_sha256", "issued_at_utc", "expires_at_utc"):
        values["authority"].pop(field, None)
    for field in ("normal_profile", "authority"):
        values["effect"].pop(field, None)
    return values


def validate_recipe(recipe: Mapping[str, object], templates: Mapping[str, Mapping[str, object]],
                    normal_profile: Mapping[str, object]) -> None:
    retained = recipe.get("operation") == RETAINED_OPERATION
    recovery = retained or recipe.get("operation") == RECOVERY_OPERATION
    closed(recipe, RETAINED_FIELDS if retained else RECOVERY_FIELDS if recovery else RECIPE_FIELDS,
        "P1_PILOT_ON_DEMAND_RECIPE_FIELDS")
    if (recipe["schema"] != ("P1-PILOT-CONFIRMATION-RECIPE-1.1" if retained else "P1-PILOT-CONFIRMATION-RECIPE-1.0")
        or recipe["operation"] not in {
            "ONE_MANUAL_CREATE_REATTEMPT_OF_UNKNOWN", RECOVERY_OPERATION, RETAINED_OPERATION}
        or type(recipe["duration_seconds"]) is not int or recipe["duration_seconds"] != 3600
        or type(recipe["max_calls"]) is not int or recipe["max_calls"] != 1
        or type(recipe["retry"]) is not int or recipe["retry"] != 0
        or recipe["fallback"] != "NONE"
        or recipe["approved_cost_bound_usd"] != "0.1237945"
        or any(not digest(recipe[field]) for field in RECIPE_FIELDS if field.endswith("_sha256"))
        or recipe["normal_profile_sha256"] != sha(canonical(normal_profile))
        or recipe["template_projection_sha256"] != sha(canonical(projection(templates)))
        or any(recipe[field] != templates["effect"].get(field) for field in (
            "request_sha256", "preparation_sha256", "context_sha256",
            "reference_set_sha256", "parent_unknown_request_sha256"))
        or recipe["approved_cost_bound_usd"] != templates["effect"].get("approved_cost_bound_usd")
        or any(recipe[field] != templates["permission"].get(field) for field in (
            "tariff_sha256", "tokenizer_manifest_sha256", "source_admission_manifest_sha256",
            "institutional_catalog_sha256"))):
        raise ValueError("P1_PILOT_ON_DEMAND_RECIPE_CHANGED")
    if retained:
        from backend.adapters.outbound.persistence.p0_pilot_retained_child import (
            CHILD_COMMAND,
            RIGHT_ID,
        )
        incident = templates["effect"].get("incident")
        child = incident.get("retained_child") if isinstance(incident, Mapping) else None
        if (recipe["right_id"] != RIGHT_ID or recipe["incident_command_id"] != CHILD_COMMAND
            or not isinstance(incident, Mapping) or not isinstance(child, Mapping)
            or not isinstance(incident.get("disposition"), Mapping)
            or not isinstance(child.get("disposition"), Mapping)
            or not digest(recipe["prior_incident_disposition_sha256"])
            or not digest(recipe["incident_disposition_sha256"])
            or incident["disposition"].get("sha256") != recipe["prior_incident_disposition_sha256"]
            or child["disposition"].get("sha256") != recipe["incident_disposition_sha256"]
            or templates["effect"].get("schema") != "P1-PILOT-RETAINED-CHILD-EFFECT-STARTUP-1.0"):
            raise ValueError("P1_PILOT_RETAINED_CHILD_RECIPE_CHANGED")
    elif recovery:
        incident = templates["effect"].get("incident")
        if (recipe["incident_command_id"] != "406a9f51b4de4121ba91f9b410a9de4c"
            or not digest(recipe["incident_disposition_sha256"])
            or not isinstance(incident, Mapping)
            or not isinstance(incident.get("disposition"), Mapping)
            or incident["disposition"].get("sha256") !=
                recipe["incident_disposition_sha256"]):
            raise ValueError("P1_PILOT_INCIDENT_RECIPE_CHANGED")
    elif "incident" in templates["effect"]:
        raise ValueError("P1_PILOT_INCIDENT_RECIPE_CHANGED")
    if (templates["authority"].get("operation") not in
        ({recipe["operation"]} if recovery else {None, recipe["operation"]})):
        raise ValueError("P1_PILOT_ON_DEMAND_OPERATION_CHANGED")


def derive(recipe: Mapping[str, object], templates: Mapping[str, Mapping[str, object]],
           normal_profile: Mapping[str, object], *, at: datetime, paths: Mapping[str, Path]
           ) -> dict[str, dict[str, object]]:
    """Derive canonical temporal documents once; never read the clock internally."""
    validate_recipe(recipe, templates, normal_profile)
    if (at.tzinfo is None or at.utcoffset() != timedelta(0)
        or set(paths) != set(DOCUMENTS)
        or len({str(path) for path in paths.values()}) != len(DOCUMENTS)
        or any(not path.is_absolute() or path.suffix != ".json" for path in paths.values())):
        raise ValueError("P1_PILOT_ON_DEMAND_DERIVATION_REQUIRED")
    start = at.astimezone(UTC).isoformat()
    end = (at + timedelta(seconds=cast(int, recipe["duration_seconds"]))).astimezone(UTC).isoformat()
    docs = {key: deepcopy(dict(templates[key])) for key in DOCUMENTS}
    permission = docs["permission"]
    permission.pop("owner_decision_sha256", None)
    permission["issued_at_utc"], permission["expires_at_utc"] = start, end
    permission["profile_sha256"] = sha(canonical(normal_profile))
    decision = docs["decision"]
    decision["profile_sha256"] = permission["profile_sha256"]
    decision["permission_policy_sha256"] = sha(canonical(permission))
    permission["owner_decision_sha256"] = sha(canonical(decision))
    def descriptor(name: str) -> dict[str, str]:
        return {"path": str(paths[name]), "sha256": sha(canonical(docs[name]))}
    envelope = docs["envelope"]
    embedded_profile = envelope.get("profile")
    if (not isinstance(embedded_profile, Mapping)
        or canonical(embedded_profile) != canonical(normal_profile)):
        raise ValueError("P1_PILOT_ON_DEMAND_PROFILE_EMBEDDING_CHANGED")
    # P0NormalProductComposition reads the complete profile inline from the
    # envelope. A descriptor here can pass synthetic derivation yet refuse
    # the actual normal startup after the final confirmation.
    envelope["profile"] = deepcopy(dict(normal_profile))
    envelope["decision"] = descriptor("decision")
    envelope["permission"] = descriptor("permission")
    authority = docs["authority"]
    authority["operation"] = recipe["operation"]
    authority["permission_sha256"] = sha(canonical(permission))
    authority["issued_at_utc"], authority["expires_at_utc"] = start, end
    effect = docs["effect"]
    effect["normal_profile"] = descriptor("envelope")
    effect["authority"] = descriptor("authority")
    if (utc(cast(str, authority["expires_at_utc"])) - utc(cast(str, authority["issued_at_utc"]))
        != timedelta(minutes=60)):
        raise ValueError("P1_PILOT_ON_DEMAND_DURATION_CHANGED")
    return docs
