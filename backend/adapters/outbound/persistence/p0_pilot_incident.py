"""Append-only local disposition of the retained uncertain 406A command.

The marker pins known bytes and a prior stop observation. It never asserts a
provider outcome, releases a reservation, or authorizes another attempt alone.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    digest,
    money,
    sha,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import decode
from backend.infrastructure.filesystem import (
    atomic_publish_fresh,
    capture_secure_path,
    private_temporary_file,
    read_file_nofollow,
)

COMMAND = "406a9f51b4de4121ba91f9b410a9de4c"
PARENT = "176b136b4f80b11009d93713fa85e7805c851ad3c466b609a43e45c7fa84cf2b"
CANDIDATE = "58cf32a15f9b696f889855ac7831ade8d762439d6a49d2b144bc7ff14b90b044"
STOP_EVIDENCE = "c3a5882bc897b6971895b3c0f453565ef7c107091ac858369789c3633d56dd57"
STOP_OBSERVED_END = "2026-10-21T12:52:25+00:00"
OWNER_SCOPE = "LU-PRODUIT-01"
STATE = "LOCAL_PROCESS_STOPPED_OUTCOME_UNKNOWN_RESERVED_NO_REPLAY"
SCHEMA = "P1-PILOT-LOCAL-INCIDENT-DISPOSITION-1.0"
SOURCES = ("pending", "slot", "reserved", "dispatch")
FIELDS = {"schema", "state", "command_id", "parent_unknown_request_sha256",
    "candidate_request_sha256", "pending_sha256", "slot_sha256",
    "reserved_sha256", "dispatch_sha256", "reserved_usd",
    "stop_evidence_sha256", "stop_observed_end_utc", "owner_scope"}


class LockedLedger(Protocol):
    def _require_lock(self) -> None: ...


class P0PilotIncidentDisposition:
    """Use the existing confirmation and receipt roots; infer no outcome."""

    def __init__(self, *, confirmation_root: Path, receipt_root: Path,
                 documents_root: Path, sources: Mapping[str, str],
                 expected_sha256: str | None = None) -> None:
        if (set(sources) != set(self.source_names)
            or any(not digest(value) for value in sources.values())
            or expected_sha256 is not None and not digest(expected_sha256)):
            raise ValueError("P1_PILOT_INCIDENT_SOURCES_REQUIRED")
        self.roots = {"pending": confirmation_root, "slot": receipt_root,
            "reserved": receipt_root, "dispatch": receipt_root,
            "prior_permission": documents_root}
        self.identities = {name: capture_secure_path(root, allowed_root=root)
            for name, root in self.roots.items()}
        if any(not identity.is_directory for identity in self.identities.values()):
            raise ValueError("P1_PILOT_INCIDENT_ROOT_REQUIRED")
        self.confirmation_root = confirmation_root
        self.sources = dict(sources)
        self.expected_sha256 = expected_sha256

    @property
    def source_names(self) -> tuple[str, ...]:
        return SOURCES

    @property
    def command(self) -> str:
        return COMMAND

    @property
    def observed_end(self) -> str:
        return STOP_OBSERVED_END

    @property
    def base_slots_count(self) -> int:
        return 4

    @property
    def expected_events(self) -> frozenset[str]:
        return frozenset({"RESERVED", "DISPATCH"})

    def retained(self) -> tuple[P0PilotIncidentDisposition, ...]:
        return (self,)

    @property
    def path(self) -> Path:
        return self.confirmation_root / f"p0-incident.{self.command}.json"

    def _source(self, name: str, path: Path, *, expected: str) -> dict[str, object]:
        root = self.roots[name]
        if not self.identities[name].same_identity(capture_secure_path(
                root, allowed_root=root)):
            raise ValueError("P1_PILOT_INCIDENT_ROOT_CHANGED")
        raw = read_file_nofollow(path, allowed_root=root, maximum_bytes=131_072)
        if sha(raw) != expected:
            raise ValueError("P1_PILOT_INCIDENT_SOURCE_CHANGED")
        return decode(raw)

    def _pending(self) -> dict[str, object]:
        # An exact command can have only one old recipe. Never choose the first
        # match or infer a command identity from the body hash.
        matches = [path for path in self.confirmation_root.glob(
            f"p0-confirmation.*.{self.command}.PENDING.json") if re.fullmatch(
                rf"p0-confirmation\.[0-9a-f]{{64}}\.{self.command}\.PENDING\.json", path.name)]
        if len(matches) != 1:
            raise ValueError("P1_PILOT_INCIDENT_PENDING_UNIQUE_REQUIRED")
        pending = self._source("pending", matches[0], expected=self.sources["pending"])
        if (pending.get("schema") != "P1-PILOT-CONFIRMATION-PENDING-1.0"
            or pending.get("command_id") != self.command
            or not digest(pending.get("recipe_sha256"))
            or not digest(pending.get("normal_preview_sha256"))
            or not digest(pending.get("permission_sha256"))):
            raise ValueError("P1_PILOT_INCIDENT_LINEAGE_CHANGED")
        return pending

    def _prior_permission(self, pending: Mapping[str, object]) -> dict[str, object]:
        prior_path = self.roots["prior_permission"] / f"p0-derived.{self.command}.permission.json"
        return self._source("prior_permission", prior_path,
            expected=str(pending["permission_sha256"]))

    def slot_path(self) -> Path:
        pending = self._pending()
        prior = self._prior_permission(pending)
        namespace = prior.get("permission_namespace_sha256")
        if not digest(namespace):
            raise ValueError("P1_PILOT_INCIDENT_LINEAGE_CHANGED")
        return self.roots["slot"] / (
            f"{namespace}.P1.{pending['normal_preview_sha256']}.json")

    def sources_checked(self) -> dict[str, dict[str, object]]:
        pending = self._pending()
        prior = self._prior_permission(pending)
        recipe = str(pending["recipe_sha256"])
        revoked = self.confirmation_root / f"p0-confirmation.{recipe}.REVOKED.json"
        if capture_secure_path(revoked, allowed_root=self.confirmation_root).exists:
            raise ValueError("P1_PILOT_INCIDENT_PRIOR_REVOKED")
        slot = self._source("slot", self.slot_path(), expected=self.sources["slot"])
        namespace = slot.get("namespace_sha256")
        if not digest(namespace):
            raise ValueError("P1_PILOT_INCIDENT_LINEAGE_CHANGED")
        reserved = self._source("reserved", self.roots["reserved"] /
            f"{namespace}.RESERVED.json", expected=self.sources["reserved"])
        dispatch = self._source("dispatch", self.roots["dispatch"] /
            f"{namespace}.DISPATCH.json", expected=self.sources["dispatch"])
        capture_preflight = dispatch.get("preflight")
        if (pending["permission_sha256"] != sha(canonical(prior))
            or slot.get("command_id") != self.command
            or slot.get("preview_sha256") != pending["normal_preview_sha256"]
            or slot.get("permission_sha256") != pending["permission_sha256"]
            or slot.get("request_sha256") != CANDIDATE
            or money(slot.get("reserved_usd")) != money("0.1237945")
            or any(event.get("namespace_sha256") != namespace
                or event.get("grant_sha256") != slot.get("grant_sha256")
                or event.get("preflight_sha256") != slot.get("preflight_sha256")
                for event in (reserved, dispatch))
            or money(reserved.get("reserved_usd")) != money(slot["reserved_usd"])
            or not isinstance(capture_preflight, dict)
            or money(capture_preflight.get("cost_bound_usd")) != money(slot["reserved_usd"])
            or reserved.get("schema") != "P0-NORMAL-TECHNICAL-RECEIPT-1.0"
            or reserved.get("state") != "RESERVED"
            or dispatch.get("schema") != "P0-NORMAL-DISPATCH-CAPTURE-1.0"
            or dispatch.get("request_sha256") != CANDIDATE
            or not isinstance(dispatch.get("body"), str)
            or sha(str(dispatch["body"]).encode()) != CANDIDATE):
            raise ValueError("P1_PILOT_INCIDENT_LINEAGE_CHANGED")
        return {"pending": pending, "slot": slot, "reserved": reserved,
            "dispatch": dispatch, "prior_permission": prior}

    def _validate(self, record: Mapping[str, object]) -> None:
        if (set(record) != FIELDS or record.get("schema") != SCHEMA
            or record.get("state") != STATE or record.get("command_id") != self.command
            or record.get("parent_unknown_request_sha256") != PARENT
            or record.get("candidate_request_sha256") != CANDIDATE
            or any(record.get(f"{name}_sha256") != self.sources[name]
                for name in SOURCES)
            or money(record.get("reserved_usd")) != money("0.1237945")
            or record.get("stop_evidence_sha256") != STOP_EVIDENCE
            or record.get("stop_observed_end_utc") != STOP_OBSERVED_END
            or record.get("owner_scope") != OWNER_SCOPE):
            raise ValueError("P1_PILOT_INCIDENT_DISPOSITION_CHANGED")

    def proposed(self) -> dict[str, object]:
        """Stable, reviewable bytes; no write, authority or terminal claim."""
        record: dict[str, object] = {"schema": SCHEMA, "state": STATE,
            "command_id": self.command, "parent_unknown_request_sha256": PARENT,
            "candidate_request_sha256": CANDIDATE,
            **{f"{name}_sha256": self.sources[name] for name in SOURCES},
            "reserved_usd": "0.1237945",
            "stop_evidence_sha256": STOP_EVIDENCE,
            "stop_observed_end_utc": STOP_OBSERVED_END,
            "owner_scope": OWNER_SCOPE}
        self._validate(record)
        return record

    def assert_reviewed(self) -> None:
        """Check adopted bytes and retained lineage without requiring a write."""
        self.sources_checked()
        if (self.expected_sha256 is None
            or sha(canonical(self.proposed())) != self.expected_sha256):
            raise ValueError("P1_PILOT_INCIDENT_DISPOSITION_CHANGED")
        if capture_secure_path(self.path, allowed_root=self.confirmation_root).exists:
            self.read()

    def read(self) -> dict[str, object]:
        self.sources_checked()
        raw = read_file_nofollow(self.path, allowed_root=self.confirmation_root,
            maximum_bytes=8192)
        if self.expected_sha256 is not None and sha(raw) != self.expected_sha256:
            raise ValueError("P1_PILOT_INCIDENT_DISPOSITION_CHANGED")
        record = decode(raw)
        self._validate(record)
        return record

    def publish(self, *, ledger: LockedLedger, now: datetime, operator: str) -> str:
        """Future explicit Application action only; never called by startup."""
        ledger._require_lock()
        self.sources_checked()
        if (operator != OWNER_SCOPE or now.utcoffset() != timedelta(0)
            or now < datetime.fromisoformat(self.observed_end)):
            raise ValueError("P1_PILOT_INCIDENT_DISPOSITION_REQUIRED")
        record = self.proposed()
        raw = canonical(record)
        if self.expected_sha256 is None or sha(raw) != self.expected_sha256:
            raise ValueError("P1_PILOT_INCIDENT_DISPOSITION_CHANGED")
        if capture_secure_path(self.path, allowed_root=self.confirmation_root).exists:
            raise ValueError("P1_PILOT_INCIDENT_ALREADY_DISPOSED")
        temporary = private_temporary_file(self.confirmation_root,
            allowed_root=self.confirmation_root, prefix="p0-incident-", suffix=".pending")
        with temporary.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_publish_fresh(temporary, self.path, allowed_root=self.confirmation_root)
        if self.read() != record:
            raise ValueError("P1_PILOT_INCIDENT_COMMIT_UNKNOWN")
        return sha(raw)
