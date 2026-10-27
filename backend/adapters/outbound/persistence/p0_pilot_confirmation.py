"""Append-only pilot confirmation receipts under the original ledger LOCK.

The store never creates a slot or calls a provider. A PENDING is an exclusion
record, not an authorization by itself. Every reader checks the pinned root.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    digest,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import (
    decode,
    pinned_receipt_root,
)
from backend.infrastructure.filesystem import (
    atomic_publish_fresh,
    capture_secure_path,
    private_temporary_file,
    read_file_nofollow,
)

_PENDING = {"schema", "recipe_sha256", "command_id", "stable_preview_sha256",
    "normal_preview_sha256", "issued_at_utc", "expires_at_utc",
    "permission_sha256", "decision_sha256", "envelope_sha256",
    "authority_sha256", "effect_sha256", "transfer_accepted",
    "cost_bound_accepted", "double_execution_cost_risk_accepted"}
_EXPIRED = {"schema", "recipe_sha256", "command_id", "pending_sha256",
    "expired_at_utc", "state"}
_REVOKED = {"schema", "recipe_sha256", "revoked_at_utc", "operator"}


class PilotLedger(Protocol):
    def _require_lock(self) -> None: ...
    def slots(self) -> list[dict[str, object]]: ...


class P0PilotConfirmationStore:
    """A technical store distinct from the historical receipt root."""

    def __init__(self, root: Path, *, recipe_sha256: str,
                 baseline_slots: int = 3, right_id: str | None = None) -> None:
        if not digest(recipe_sha256):
            raise ValueError("P1_PILOT_RECIPE_IDENTITY_REQUIRED")
        from backend.adapters.outbound.persistence.p0_pilot_retained_child import RIGHT_ID
        if (baseline_slots not in {3, 4, 5}
            or (baseline_slots == 5) != (right_id == RIGHT_ID)
            or right_id is not None and right_id != RIGHT_ID):
            raise ValueError("P1_PILOT_CONFIRMATION_BASELINE_REQUIRED")
        self.right_id = right_id
        self.pending_fields = _PENDING | ({"right_id"} if right_id is not None else set())
        self.pending_schema = ("P1-PILOT-CONFIRMATION-PENDING-1.1" if right_id is not None
            else "P1-PILOT-CONFIRMATION-PENDING-1.0")
        identity = capture_secure_path(root, allowed_root=root)
        if not identity.is_directory:
            raise ValueError("P1_PILOT_CONFIRMATION_ROOT_REQUIRED")
        self.root, self.recipe_sha256, self._identity = root, recipe_sha256, identity
        self.baseline_slots = baseline_slots

    def _root(self) -> None:
        if not self._identity.same_identity(capture_secure_path(
                self.root, allowed_root=self.root)):
            raise ValueError("P1_PILOT_CONFIRMATION_ROOT_CHANGED")

    def _name(self, command: str, kind: str) -> Path:
        if (not re.fullmatch(r"[0-9a-f]{32}", command)
            or kind not in {"PENDING", "EXPIRED_NO_SLOT"}):
            raise ValueError("P1_PILOT_CONFIRMATION_NAME_REJECTED")
        return self.root / f"p0-confirmation.{self.recipe_sha256}.{command}.{kind}.json"

    def _revoked(self) -> Path:
        return self.root / f"p0-confirmation.{self.right_id or self.recipe_sha256}.REVOKED.json"

    def _read(self, path: Path) -> dict[str, object] | None:
        self._root()
        with pinned_receipt_root(self.root):
            before = capture_secure_path(path, allowed_root=self.root)
            if not before.exists:
                return None
            raw = read_file_nofollow(path, allowed_root=self.root, maximum_bytes=8192)
            if not before.same_state(capture_secure_path(path, allowed_root=self.root)):
                raise ValueError("P1_PILOT_CONFIRMATION_CHANGED")
            result = decode(raw)
        self._root()
        return result

    def _publish(self, path: Path, record: Mapping[str, object]) -> str:
        raw = canonical(dict(record))
        if len(raw) > 8192:
            raise ValueError("P1_PILOT_CONFIRMATION_OVERSIZED")
        self._root()
        with pinned_receipt_root(self.root):
            self._root()
            if capture_secure_path(path, allowed_root=self.root).exists:
                raise ValueError("P1_PILOT_CONFIRMATION_ALREADY_EXISTS")
            temporary = private_temporary_file(self.root, allowed_root=self.root,
                prefix="p0-confirmation-", suffix=".pending")
            with temporary.open("wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            atomic_publish_fresh(temporary, path, allowed_root=self.root)
            if self._read(path) != dict(record):
                raise ValueError("P1_PILOT_CONFIRMATION_COMMIT_UNKNOWN")
        return sha(raw)

    def _pending_records(self) -> list[dict[str, object]]:
        self._root()
        if self.right_id is not None:
            return self._right_pending_records()
        prefix = f"p0-confirmation.{self.recipe_sha256}."
        records: list[dict[str, object]] = []
        for path in self.root.iterdir():
            if not path.name.startswith(prefix) or not path.name.endswith(".json"):
                continue
            if path == self._revoked():
                continue
            match = re.fullmatch(re.escape(prefix)
                + r"([0-9a-f]{32})\.(PENDING|EXPIRED_NO_SLOT)\.json", path.name)
            if match is None:
                raise ValueError("P1_PILOT_CONFIRMATION_UNEXPECTED_FILE")
            record = self._read(path)
            if record is None:
                raise ValueError("P1_PILOT_CONFIRMATION_CHANGED")
            kind = match.group(2)
            expected = _PENDING if kind == "PENDING" else _EXPIRED
            if (set(record) != expected
                or record.get("recipe_sha256") != self.recipe_sha256
                or record.get("command_id") != match.group(1)
                or record.get("schema") !=
                    ("P1-PILOT-CONFIRMATION-PENDING-1.0" if kind == "PENDING"
                     else "P1-PILOT-CONFIRMATION-EXPIRED-NO-SLOT-1.0")):
                raise ValueError("P1_PILOT_CONFIRMATION_CHANGED")
            records.append(record)
        self._root()
        return records

    def _right_pending_records(self) -> list[dict[str, object]]:
        # The fixed right is consumed across recipes/packages, under the same
        # original LOCK. A restart only reads; it never resumes dispatch.
        records = []
        for path in self.root.glob("p0-confirmation.*.PENDING.json"):
            record = self._read(path)
            if record is None:
                raise ValueError("P1_PILOT_CONFIRMATION_CHANGED")
            if (record.get("schema") == "P1-PILOT-CONFIRMATION-PENDING-1.0"
                and set(record) == _PENDING):
                continue
            match = re.fullmatch(r"p0-confirmation\.([0-9a-f]{64})\.([0-9a-f]{32})\.PENDING\.json", path.name)
            if (match is None or set(record) != self.pending_fields
                or record.get("schema") != self.pending_schema
                or record.get("right_id") != self.right_id
                or record.get("recipe_sha256") != match.group(1)
                or record.get("command_id") != match.group(2)):
                raise ValueError("P1_PILOT_CONFIRMATION_CHANGED")
            if record.get("recipe_sha256") != self.recipe_sha256:
                raise ValueError("P1_PILOT_RECOVERY_RIGHT_ALREADY_CONSUMED")
            records.append(record)
        if len(records) > 1:
            raise ValueError("P1_PILOT_MULTIPLE_CONFIRMATIONS_STOP")
        self._root()
        return records

    def _check_revoked(self) -> None:
        revoked = self._read(self._revoked())
        if revoked is None:
            return
        if (set(revoked) != _REVOKED | ({"right_id"} if self.right_id is not None else set())
            or revoked.get("schema") != "P1-PILOT-REVOKED-1.0"
            or (revoked.get("right_id") != self.right_id if self.right_id is not None
                else revoked.get("recipe_sha256") != self.recipe_sha256)):
            raise ValueError("P1_PILOT_REVOCATION_CHANGED")
        raise ValueError("P1_PILOT_REVOKED")

    def retained_pending(self) -> dict[str, object] | None:
        """Read the one retained confirmation for local recovery, never for dispatch."""
        records = self._pending_records()
        pendings = {str(row["command_id"]): row for row in records if row[
            "schema"] == self.pending_schema}
        terminals = {str(row["command_id"]): row for row in records if row[
            "schema"] == "P1-PILOT-CONFIRMATION-EXPIRED-NO-SLOT-1.0"}
        if (len(pendings) != sum(row["schema"] ==
                self.pending_schema for row in records)
            or len(terminals) != sum(row["schema"] ==
                "P1-PILOT-CONFIRMATION-EXPIRED-NO-SLOT-1.0" for row in records)
            or any(command not in pendings
                or row.get("pending_sha256") != sha(canonical(pendings[command]))
                or row.get("state") != "EXPIRED_NO_SLOT"
                for command, row in terminals.items())):
            raise ValueError("P1_PILOT_CONFIRMATION_ORPHAN_TERMINAL")
        active = [row for command, row in pendings.items() if command not in terminals]
        if self.baseline_slots >= 4 and terminals:
            raise ValueError("P1_PILOT_RECOVERY_RIGHT_ALREADY_CONSUMED")
        if len(active) > 1:
            raise ValueError("P1_PILOT_MULTIPLE_CONFIRMATIONS_STOP")
        return active[0] if active else None

    def begin(self, *, ledger: PilotLedger, record: Mapping[str, object],
              now: datetime) -> str:
        """Caller holds the original LOCK; publication precedes any slot."""
        ledger._require_lock()
        self._check_revoked()
        if (set(record) != self.pending_fields
            or record.get("schema") != self.pending_schema
            or record.get("recipe_sha256") != self.recipe_sha256
            or any(record.get(key) is not True for key in (
                "transfer_accepted", "cost_bound_accepted",
                "double_execution_cost_risk_accepted"))
            or not isinstance(record.get("command_id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", cast(str, record["command_id"]))
            or any(not digest(record.get(key)) for key in _PENDING
                if key.endswith("_sha256"))
            or self.right_id is not None and record.get("right_id") != self.right_id
            or utc(cast(str, record["issued_at_utc"])) != now
            or utc(cast(str, record["expires_at_utc"])) - now
                != timedelta(minutes=60)):
            raise ValueError("P1_PILOT_CONFIRMATION_RECORD_REJECTED")
        slots = ledger.slots()
        if len(slots) != self.baseline_slots:
            raise ValueError("P1_PILOT_OPERATION_ALREADY_RESERVED")
        records = self._pending_records()
        pendings = {str(row["command_id"]): row for row in records
            if row["schema"] == self.pending_schema}
        expired = {str(row["command_id"]): row for row in records
            if row["schema"] == "P1-PILOT-CONFIRMATION-EXPIRED-NO-SLOT-1.0"}
        if len(pendings) != sum(row["schema"] ==
                self.pending_schema for row in records):
            raise ValueError("P1_PILOT_CONFIRMATION_DUPLICATE")
        # The punctual post-406A exception is spent when PENDING is published.
        # Expiration without a slot cannot open another command in this recipe.
        if self.baseline_slots >= 4 and records:
            raise ValueError("P1_PILOT_RECOVERY_RIGHT_ALREADY_CONSUMED")
        for command, prior in pendings.items():
            terminal = expired.get(command)
            if terminal is None:
                if now < utc(cast(str, prior["expires_at_utc"])):
                    raise ValueError("P1_PILOT_PENDING_EXISTS")
                self._publish(self._name(command, "EXPIRED_NO_SLOT"), {
                    "schema": "P1-PILOT-CONFIRMATION-EXPIRED-NO-SLOT-1.0",
                    "recipe_sha256": self.recipe_sha256, "command_id": command,
                    "pending_sha256": sha(canonical(prior)),
                    "expired_at_utc": now.isoformat(), "state": "EXPIRED_NO_SLOT"})
            elif (terminal.get("pending_sha256") != sha(canonical(prior))
                  or terminal.get("state") != "EXPIRED_NO_SLOT"):
                raise ValueError("P1_PILOT_CONFIRMATION_CHANGED")
        if set(expired) - set(pendings):
            raise ValueError("P1_PILOT_CONFIRMATION_ORPHAN_TERMINAL")
        return self._publish(self._name(cast(str, record["command_id"]), "PENDING"), record)

    def require_current(self, *, ledger: PilotLedger, command_id: str,
                        pending_sha256: str, now: datetime) -> None:
        """Called under the same LOCK before reservation and ATTEMPTED."""
        ledger._require_lock()
        self._check_revoked()
        record = self._read(self._name(command_id, "PENDING"))
        if (record is None or set(record) != self.pending_fields
            or record.get("schema") != self.pending_schema
            or record.get("recipe_sha256") != self.recipe_sha256
            or sha(canonical(record)) != pending_sha256
            or self._read(self._name(command_id, "EXPIRED_NO_SLOT")) is not None
            or not utc(cast(str, record["issued_at_utc"])) <= now
                < utc(cast(str, record["expires_at_utc"]))):
            raise ValueError("P1_PILOT_CONFIRMATION_NOT_CURRENT")
        if self.right_id is not None and self._pending_records() != [record]:
            raise ValueError("P1_PILOT_RECOVERY_RIGHT_ALREADY_CONSUMED")
        slots = ledger.slots()
        if len(slots) not in {self.baseline_slots, self.baseline_slots + 1}:
            raise ValueError("P1_PILOT_OPERATION_ALREADY_RESERVED")

    def revoke(self, *, ledger: PilotLedger, now: datetime, operator: str) -> str:
        """Closed local command; never removes a pending record or child."""
        ledger._require_lock()
        if not operator or len(operator) > 128:
            raise ValueError("P1_PILOT_REVOKER_REQUIRED")
        self._check_revoked()
        return self._publish(self._revoked(), {"schema": "P1-PILOT-REVOKED-1.0",
            "recipe_sha256": self.recipe_sha256,
            "revoked_at_utc": now.isoformat(), "operator": operator,
            **({"right_id": self.right_id} if self.right_id is not None else {})})

    def require_not_revoked(self, *, ledger: PilotLedger) -> None:
        """Fail before the incident disposition is published by a final command."""
        ledger._require_lock()
        self._check_revoked()
