from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict, cast

B01_FREEZE = Path(
    "docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/"
    "03_HISTORICAL_HASH_FREEZE.json"
)
APPROVED_BASELINE_COMMIT = "6d0d66380757d7502fd967cd0246c5b6ff91d5f8"


class _FreezeEntry(TypedDict):
    path: str
    sha256_current: str
    historical_reference_sha256: str
    immutable: bool
    known_preexisting_drift: bool
    drift_origin: str | None
    retroactive_repair: str


class _FreezeDocument(TypedDict):
    schema_version: str
    entries: list[_FreezeEntry]


def assert_current_historical_hashes(root: Path, paths: Iterable[str]) -> None:
    """Assert current evidence against B01, with its approved Git baseline fallback."""

    freeze = _load_b01_freeze(root)
    for relative_path in paths:
        entry = freeze.get(relative_path)
        if entry is None:
            expected = _git_baseline_sha256(root, relative_path)
        else:
            assert entry["immutable"] is True
            expected = entry["sha256_current"]
            if entry["known_preexisting_drift"]:
                assert len(entry["historical_reference_sha256"]) == 64
                assert entry["drift_origin"]
                assert entry["retroactive_repair"] == "FORBIDDEN"
        actual = hashlib.sha256((root / relative_path).read_bytes()).hexdigest()
        assert actual == expected, relative_path


def _load_b01_freeze(root: Path) -> dict[str, _FreezeEntry]:
    freeze_path = root / B01_FREEZE
    if not freeze_path.is_file():
        return {}
    document = cast(
        _FreezeDocument,
        json.loads(freeze_path.read_text(encoding="utf-8")),
    )
    assert document["schema_version"] == "12.17.4e-b01-historical-hash-freeze-v1"
    assert len(document["entries"]) == 40
    return {entry["path"]: entry for entry in document["entries"]}


def _git_baseline_sha256(root: Path, relative_path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{APPROVED_BASELINE_COMMIT}:{relative_path}"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return hashlib.sha256(result.stdout).hexdigest()
