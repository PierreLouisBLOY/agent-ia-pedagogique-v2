"""One immutable private OFF pilot preview, separate from R4 records and P1 receipts."""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from backend.infrastructure.filesystem import (
    atomic_publish_fresh,
    capture_secure_path,
    private_temporary_file,
    read_file_nofollow,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    fingerprint,
    object_data,
)

_NAME = "P1_PILOT_CANDIDATE_OFF.json"
_MAX_BYTES = 512_000


class P0PilotCandidateOffStore:
    """The existing private pilot store is the only root; no catalog or ledger write."""

    def __init__(self, root: Path) -> None:
        self.root = root
        identity = capture_secure_path(root, allowed_root=root)
        if not identity.is_directory:
            raise ValueError("P0_PILOT_STORE_REQUIRED")
        self._identity = (identity.device, identity.inode)

    def _check_root(self) -> None:
        current = capture_secure_path(self.root, allowed_root=self.root)
        if not current.is_directory or (current.device, current.inode) != self._identity:
            raise ValueError("P0_PILOT_STORE_CHANGED")

    def read(self) -> dict[str, object] | None:
        self._check_root()
        path = self.root / _NAME
        if not capture_secure_path(path, allowed_root=self.root).exists:
            return None
        raw = read_file_nofollow(path, allowed_root=self.root, maximum_bytes=_MAX_BYTES)
        envelope = object_data(json.loads(raw), {"record", "sha256"})
        record = object_data(envelope["record"], {"schema", "demand", "request", "preparation_ref",
            "preparation_sha256", "preview"})
        if (envelope["sha256"] != fingerprint(record)
            or record["schema"] != "P1-PILOT-CANDIDATE-OFF-1.0"
            or not isinstance(record["demand"], str)
            or not 1 <= len(record["demand"]) <= 2048
            or not isinstance(record["preparation_ref"], str)
            or not record["preparation_ref"].startswith("prep:")
            or fingerprint(record["request"]) != record["preparation_sha256"]):
            raise ValueError("P0_PILOT_CANDIDATE_INTEGRITY")
        preview = object_data(record["preview"])
        if (preview.get("preparation_ref") != record["preparation_ref"]
            or preview.get("preparation_sha256") != record["preparation_sha256"]
            or preview.get("effect_permitted") is not False
            or preview.get("provider_calls") != 0
            or preview.get("new_slots") != 0):
            raise ValueError("P0_PILOT_CANDIDATE_INTEGRITY")
        self._check_root()
        return cast(dict[str, object], as_plain(record))

    def publish(self, record: Mapping[str, object]) -> dict[str, object]:
        self._check_root()
        plain = object_data(as_plain(record))
        raw = encoded({"record": plain, "sha256": fingerprint(plain)})
        if len(raw) > _MAX_BYTES:
            raise ValueError("P0_PILOT_CANDIDATE_TOO_LARGE")
        existing = self.read()
        if existing is not None:
            if fingerprint(existing) != fingerprint(plain):
                raise ValueError("P0_PILOT_CANDIDATE_CONFLICT")
            return existing
        temporary = private_temporary_file(self.root, allowed_root=self.root,
            prefix="p0-pilot-", suffix=".pending")
        with temporary.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_publish_fresh(temporary, self.root / _NAME, allowed_root=self.root)
        loaded = self.read()
        if loaded is None or fingerprint(loaded) != fingerprint(plain):
            raise ValueError("P0_PILOT_CANDIDATE_COMMIT_UNKNOWN")
        return loaded
