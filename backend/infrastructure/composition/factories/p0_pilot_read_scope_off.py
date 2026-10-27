"""Pinned, revocable read authority for the exact local pilot; no effect port."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from backend.adapters.outbound.generation.openai.p0_normal_policy import closed, digest, sha
from backend.infrastructure.composition.factories.p0_normal_profile import read_descriptor
from backend.infrastructure.composition.factories.p0_normal_profile_contract import descriptor
from backend.infrastructure.filesystem import capture_secure_path, read_file_nofollow

FIELDS = {"schema", "operation", "mode", "duration", "owner_evidence",
    "historical_plan", "historical_adoption", "historical_owner_sha256",
    "pilot_body_scope_sha256", "pilot_runtime_sha256", "effect_authorized",
    "ledger_writes_allowed", "provider_calls_allowed", "preparation_sha256",
    "request_sha256", "request_bytes"}
OWNER_FIELDS = {"schema", "decision", "pilot", "scope"}
POLICY_DECISION = "READ_PREPARE_OFF_UNTIL_CLOSURE_OR_REVOCATION_20261019"
MARKER = "P1_PILOT_READ_CLOSED_OR_REVOKED"


class P0PilotReadScopeOff:
    """Recheck authority and stop marker on every Application inspection."""

    def __init__(self, *, path: Path, expected_sha256: str,
        pilot_body_scope_sha256: str, pilot_runtime_sha256: str) -> None:
        self.path = path
        self.expected_sha256 = expected_sha256
        self.pilot_body_scope_sha256 = pilot_body_scope_sha256
        self.pilot_runtime_sha256 = pilot_runtime_sha256
        self.parent_pin = capture_secure_path(path.parent, allowed_root=path.parent)
        self.validate()

    def validate(self) -> None:
        if os.path.lexists(self.path.parent / MARKER):
            raise ValueError("P1_PILOT_READ_CLOSED_OR_REVOKED")
        current_parent = capture_secure_path(self.path.parent, allowed_root=self.path.parent)
        if (current_parent.device, current_parent.inode) != (self.parent_pin.device,
                self.parent_pin.inode):
            raise ValueError("P1_PILOT_READ_SCOPE_PARENT_CHANGED")
        raw = read_file_nofollow(self.path, allowed_root=self.path.parent, maximum_bytes=4096)
        if not digest(self.expected_sha256) or sha(raw) != self.expected_sha256:
            raise ValueError("P1_PILOT_READ_SCOPE_CHANGED")
        value = read_descriptor({"path": str(self.path), "sha256": self.expected_sha256})
        if not isinstance(value, Mapping):
            raise ValueError("P1_PILOT_READ_SCOPE_INVALID")
        closed(value, FIELDS, "P1_PILOT_READ_SCOPE_FIELDS")
        owner_desc = descriptor(value["owner_evidence"])
        owner = read_descriptor(owner_desc)
        plan_desc = descriptor(value["historical_plan"])
        adoption_desc = descriptor(value["historical_adoption"])
        if not isinstance(owner, Mapping):
            raise ValueError("P1_PILOT_READ_OWNER_REQUIRED")
        closed(owner, OWNER_FIELDS, "P1_PILOT_READ_OWNER_FIELDS")
        if (value["schema"] != "P1-PILOT-READ-SCOPE-OFF-1.0"
            or value["operation"] != "READ_PREPARE_PILOT_AFTER_P1_EXPIRY"
            or value["mode"] != "OFF" or value["duration"] != "UNTIL_CLOSURE_OR_REVOCATION"
            or value["effect_authorized"] is not False
            or value["ledger_writes_allowed"] is not False
            or type(value["provider_calls_allowed"]) is not int or value["provider_calls_allowed"] != 0
            or not digest(value["historical_owner_sha256"])
            or not digest(value["preparation_sha256"])
            or not digest(value["request_sha256"])
            or type(value["request_bytes"]) is not int or not 0 < value["request_bytes"] <= 512_000
            or value["pilot_body_scope_sha256"] != self.pilot_body_scope_sha256
            or value["pilot_runtime_sha256"] != self.pilot_runtime_sha256
            or owner["schema"] != "P1-PILOT-READ-OWNER-DECISION-1.0"
            or owner["decision"] != POLICY_DECISION
            or owner["pilot"] != "LU-PRODUIT-01"
            or owner["scope"] != "EXACT_LOCAL_HISTORY_AND_PREPARATION_OFF"):
            raise ValueError("P1_PILOT_READ_SCOPE_INVALID")
        self.plan_path = Path(str(plan_desc["path"]))
        self.adoption_path = Path(str(adoption_desc["path"]))
        self.expected = (str(plan_desc["sha256"]), str(adoption_desc["sha256"]),
            str(value["historical_owner_sha256"]), self.pilot_body_scope_sha256,
            self.pilot_runtime_sha256)
        self.preparation_sha256 = str(value["preparation_sha256"])
        self.request_sha256 = str(value["request_sha256"])
        self.request_bytes = int(value["request_bytes"])
