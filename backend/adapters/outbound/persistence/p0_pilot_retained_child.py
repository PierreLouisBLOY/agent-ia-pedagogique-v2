"""Exact, non-recursive disposition of the observed 2f1e child; no replay."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, money, sha, utc
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import NORMAL_EVENTS
from backend.adapters.outbound.persistence import p0_pilot_incident as parent_module
from backend.adapters.outbound.persistence.p0_pilot_incident import P0PilotIncidentDisposition
from backend.infrastructure.filesystem import capture_secure_path

CHILD_COMMAND = "2f1ef780598e469fafc94f9f4ba142c6"
CHILD_RECIPE = "e71e3026c12e3c7713fa8462005933c6b069257f777d4e523965c58e899357fe"
CHILD_SOURCES = {
    "pending": "3ba78c34e1340f9ff57ffc8f64ea0f8d3de6f6387c61ef3950b3c39c124000f9",
    "slot": "c9d2bc8ed4f2814162d85b5c032e3522c3315a7685114d371b450b0ca50fabae"}
PARENT_DISPOSITION = "18c24732af9179bc9cf6b4404d64a43271e3d7325a23d5a0d995968cfa6bb02b"
OBSERVATION = "a483fa5478c98f6a869d0161922ce166ddea17851fedc4f6e34b1ac224f48c30"
OBSERVED_END = "2026-10-22T22:51:28.560664+00:00"
OPERATION = "ONE_ADDITIONAL_MANUAL_CREATE_AFTER_2F1E"
# This identity is a bounded right inside the SAME campaign, never a receipt
# namespace. Neither package, recipe, clock nor command of the future call enters it.
RIGHT_ID = sha(canonical({"operation": OPERATION, "retained_command_id": CHILD_COMMAND}))


def proposed_retained_child() -> dict[str, object]:
    """Stable bytes from the dated Application observation; no filesystem access."""
    return {"schema": "P1-PILOT-RETAINED-CHILD-DISPOSITION-1.0",
        "state": "RETAINED_PENDING_SLOT_OUTCOME_UNKNOWN_RESERVED_NO_REPLAY",
        "command_id": CHILD_COMMAND, "recipe_sha256": CHILD_RECIPE,
        "parent_unknown_request_sha256": parent_module.PARENT,
        "parent_406a_command_id": parent_module.COMMAND,
        "parent_406a_disposition_sha256": PARENT_DISPOSITION,
        "candidate_request_sha256": parent_module.CANDIDATE,
        "pending_sha256": CHILD_SOURCES["pending"], "slot_sha256": CHILD_SOURCES["slot"],
        "reserved_usd": "0.1237945", "observed_receipt_states": [],
        "observation_sha256": OBSERVATION, "observed_end_utc": OBSERVED_END,
        "owner_scope": parent_module.OWNER_SCOPE}


class P0PilotRetainedChildDisposition(P0PilotIncidentDisposition):
    """Recognize ONLY the pinned child, while retaining the old 406A marker."""

    def __init__(self, *, parent: P0PilotIncidentDisposition,
                 sources: Mapping[str, str], expected_sha256: str | None = None) -> None:
        if (dict(sources) != CHILD_SOURCES or parent.expected_sha256 != PARENT_DISPOSITION
            or parent.command != parent_module.COMMAND):
            raise ValueError("P1_PILOT_RETAINED_CHILD_BINDING")
        # Base source reader is reused; no new root or namespace is selected.
        super().__init__(confirmation_root=parent.confirmation_root,
            receipt_root=parent.roots["slot"], documents_root=parent.roots["prior_permission"],
            sources=sources,
            expected_sha256=expected_sha256)
        self.sources = dict(sources)
        self.parent = parent

    @property
    def source_names(self) -> tuple[str, ...]:
        return ("pending", "slot")

    @property
    def command(self) -> str:
        return CHILD_COMMAND

    @property
    def observed_end(self) -> str:
        return OBSERVED_END

    @property
    def base_slots_count(self) -> int:
        return 5

    @property
    def expected_events(self) -> frozenset[str]:
        return frozenset()

    def retained(self) -> tuple[P0PilotIncidentDisposition, ...]:
        return (self.parent, self)

    def proposed(self) -> dict[str, object]:
        return proposed_retained_child()

    def _validate(self, record: Mapping[str, object]) -> None:
        if canonical(record) != canonical(self.proposed()):
            raise ValueError("P1_PILOT_RETAINED_CHILD_DISPOSITION_CHANGED")

    def sources_checked(self) -> dict[str, dict[str, object]]:
        self.parent.read()
        pending = self._pending()
        if (pending.get("recipe_sha256") != CHILD_RECIPE
            or any(pending.get(key) is not True for key in (
                "transfer_accepted", "cost_bound_accepted", "double_execution_cost_risk_accepted"))
            or utc(pending.get("expires_at_utc")) > utc(OBSERVED_END)):
            raise ValueError("P1_PILOT_RETAINED_CHILD_PENDING_CHANGED")
        for kind in ("REVOKED", f"{CHILD_COMMAND}.EXPIRED_NO_SLOT"):
            path = self.confirmation_root / f"p0-confirmation.{CHILD_RECIPE}.{kind}.json"
            if capture_secure_path(path, allowed_root=self.confirmation_root).exists:
                raise ValueError("P1_PILOT_RETAINED_CHILD_TRANSITION_CHANGED")
        docs = {key: self._source("prior_permission", self.roots["prior_permission"] /
            f"p0-derived.{CHILD_COMMAND}.{key}.json", expected=str(pending.get(f"{key}_sha256")))
            for key in ("permission", "decision", "envelope", "authority", "effect")}
        slot = self._source("slot", self.slot_path(), expected=self.sources["slot"])
        namespace = slot.get("namespace_sha256")
        grant = slot.get("grant")
        if (slot.get("command_id") != CHILD_COMMAND
            or slot.get("preview_sha256") != pending.get("normal_preview_sha256")
            or slot.get("permission_sha256") != pending.get("permission_sha256")
            or slot.get("request_sha256") != parent_module.CANDIDATE
            or money(slot.get("reserved_usd")) != money("0.1237945")
            or not isinstance(grant, Mapping)
            or slot.get("grant_sha256") != sha(canonical(grant))
            or grant.get("request_sha256") != parent_module.CANDIDATE
            or grant.get("expires_at_utc") != pending.get("expires_at_utc")
            or docs["authority"].get("permission_sha256") != pending.get("permission_sha256")
            or docs["authority"].get("parent_unknown_request_sha256") != parent_module.PARENT):
            raise ValueError("P1_PILOT_RETAINED_CHILD_LINEAGE_CHANGED")
        from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
        receipt = P0NormalReceipt(self.roots["slot"], str(namespace))
        if any(receipt.exists(state) for state in NORMAL_EVENTS):
            raise ValueError("P1_PILOT_RETAINED_CHILD_RECEIPTS_CHANGED")
        return {"pending": pending, "slot": slot, "prior_permission": docs["permission"]}


def compose_incident(value: Mapping[str, object], *, confirmation_root: Path,
                     receipt_root: Path, documents_root: Path,
                     retained_child: bool = False) -> P0PilotIncidentDisposition:
    """Shared normal/effect startup factory, with closed exact descriptors."""
    from typing import cast

    expected_fields = {"disposition", "sources"} | ({"retained_child"} if retained_child else set())
    if (set(value) != expected_fields or not isinstance(value.get("disposition"), Mapping)
        or not isinstance(value.get("sources"), Mapping)):
        raise ValueError("P1_PILOT_INCIDENT_PROFILE_CHANGED")
    desc = cast(Mapping[str, object], value["disposition"])
    if set(desc) != {"path", "sha256"}:
        raise ValueError("P1_PILOT_INCIDENT_PROFILE_CHANGED")
    parent = P0PilotIncidentDisposition(confirmation_root=confirmation_root,
        receipt_root=receipt_root, documents_root=documents_root,
        sources=cast(Mapping[str, str], value["sources"]), expected_sha256=str(desc["sha256"]))
    if str(parent.path) != desc["path"]:
        raise ValueError("P1_PILOT_INCIDENT_PROFILE_CHANGED")
    parent.assert_reviewed()
    if not retained_child:
        return parent
    child = value["retained_child"]
    if (not isinstance(child, Mapping) or set(child) != {"disposition", "sources"}
        or not isinstance(child["disposition"], Mapping) or not isinstance(child["sources"], Mapping)):
        raise ValueError("P1_PILOT_RETAINED_CHILD_PROFILE_CHANGED")
    child_desc = child["disposition"]
    if set(child_desc) != {"path", "sha256"}:
        raise ValueError("P1_PILOT_RETAINED_CHILD_PROFILE_CHANGED")
    result = P0PilotRetainedChildDisposition(parent=parent,
        sources=cast(Mapping[str, str], child["sources"]), expected_sha256=str(child_desc["sha256"]))
    if str(result.path) != child_desc["path"]:
        raise ValueError("P1_PILOT_RETAINED_CHILD_PROFILE_CHANGED")
    result.assert_reviewed()
    return result
