from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "architecture/adr/ADR-P12-068-active-calibration-tooling-boundary.md"
FREEZE = (
    ROOT
    / "docs/development/"
    "phase_12_17_04e_b01_design_approval_hash_freeze/"
    "03_HISTORICAL_HASH_FREEZE.json"
)
BASELINE_COMMIT = "6d0d66380757d7502fd967cd0246c5b6ff91d5f8"
ADR_SHA256 = "4cac693a66d09bf5708b050eceeb82f9e249dbd1f32537d6b312cba8c4a6ffbd"
FREEZE_SHA256 = "b3083ee1cc8bfdde863ba812eb10fa97d10a69863a49af8527ada8e9b818878b"
ORDERED_SET_SHA256 = (
    "ee220e8deaee46b3e5c0f43932238600b4a54ab941ceb80f1b175995b2565ab5"
)
FORBIDDEN_HISTORICAL_IMPORTS = (
    "tests.calibration.pedagogical",
    "tests.providers.anthropic",
)
ACTIVE_ROOTS = (
    ROOT / "backend",
    ROOT / "evaluation_harness",
    ROOT / "calibration_tooling",
)
REQUIRED_ENTRY_FIELDS = {
    "historical_id",
    "path",
    "sha256_current",
    "historical_reference_sha256",
    "historical_manifest_refs",
    "classification",
    "immutable",
    "allowed_operation",
    "known_preexisting_drift",
    "drift_origin",
    "baseline_commit",
    "freeze_timestamp",
    "status",
}


def _freeze() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FREEZE.read_text(encoding="utf-8")))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_historical_freeze_is_bound_to_the_accepted_adr() -> None:
    payload = _freeze()
    assert payload["schema_version"] == (
        "12.17.4e-b01-historical-hash-freeze-v1"
    )
    assert payload["baseline_commit"] == BASELINE_COMMIT
    assert payload["entry_count"] == 40
    assert payload["preexisting_drift_count"] == 7
    assert hashlib.sha256(FREEZE.read_bytes()).hexdigest() == FREEZE_SHA256
    assert hashlib.sha256(ADR.read_bytes()).hexdigest() == ADR_SHA256
    assert payload["adr"] == {
        "id": "ADR-P12-068",
        "path": (
            "architecture/adr/"
            "ADR-P12-068-active-calibration-tooling-boundary.md"
        ),
        "status": "ACCEPTED",
        "sha256": ADR_SHA256,
    }


def test_all_40_historical_files_are_byte_exact_and_read_only() -> None:
    entries = _freeze()["entries"]
    assert isinstance(entries, list)
    assert len(entries) == 40
    assert {entry["historical_id"] for entry in entries} == {
        f"HIST-{index:03d}" for index in range(1, 41)
    }
    assert len({entry["path"] for entry in entries}) == 40

    serialized = ""
    for entry in entries:
        assert REQUIRED_ENTRY_FIELDS <= entry.keys()
        assert entry["immutable"] is True
        assert entry["allowed_operation"] == "READ_ONLY"
        assert entry["baseline_commit"] == BASELINE_COMMIT
        path = ROOT / entry["path"]
        assert path.is_file()
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        assert current == entry["sha256_current"]
        serialized += f"{entry['path']}\t{current}\n"
        for reference in entry["historical_manifest_refs"]:
            assert (ROOT / reference).is_file()

    assert hashlib.sha256(serialized.encode()).hexdigest() == ORDERED_SET_SHA256


def test_only_the_seven_12_17_2a_drifts_are_recorded() -> None:
    entries = _freeze()["entries"]
    assert isinstance(entries, list)
    drifted = [entry for entry in entries if entry["known_preexisting_drift"]]
    stable = [entry for entry in entries if not entry["known_preexisting_drift"]]
    assert len(drifted) == 7
    assert len(stable) == 33
    for entry in drifted:
        assert entry["drift_origin"] == "12.17.2A typing remediation"
        assert entry["retroactive_repair"] == "FORBIDDEN"
        assert entry["historical_reference_sha256"] != entry["sha256_current"]
        assert entry["status"] == (
            "FROZEN_CURRENT_BASELINE_WITH_PREEXISTING_DRIFT"
        )
    for entry in stable:
        assert entry["drift_origin"] is None
        assert entry["retroactive_repair"] == "NOT_APPLICABLE"
        assert entry["historical_reference_sha256"] == entry["sha256_current"]
        assert entry["status"] == "FROZEN_CURRENT_BASELINE"


def test_active_graph_never_imports_historical_calibration_evidence() -> None:
    python_files = (
        path
        for root in ACTIVE_ROOTS
        if root.is_dir()
        for path in root.rglob("*.py")
    )
    for path in python_files:
        assert all(
            not module.startswith(FORBIDDEN_HISTORICAL_IMPORTS)
            for module in _imports(path)
        ), path.relative_to(ROOT)


def test_adr_records_the_active_historical_separation() -> None:
    source = ADR.read_text(encoding="utf-8")
    normalized = " ".join(source.split())
    assert "Accepté pour la Phase 12.17.4E-B01" in normalized
    assert "ACTIVE_RUNTIME != HISTORICAL_CALIBRATION_EVIDENCE" in normalized
    assert "RETROACTIVE_REPAIR = FORBIDDEN" in normalized
    assert "ne modifie aucun runtime" in normalized
    assert "n'ouvre pas SQLite" in normalized
    assert "n'appelle aucun provider" in normalized
