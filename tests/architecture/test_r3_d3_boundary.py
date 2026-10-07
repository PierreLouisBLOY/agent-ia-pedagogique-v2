"""Architecture and exact public contracts, independently from behavioral tests."""

import ast
import json
import subprocess
from pathlib import Path

import pytest

from tests.support.r3_d3_scope_guard import BASELINE, PATHS, assert_scope, digest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.usefixtures("historical_guard_sources")
def test_exact_scope_and_protected_contracts() -> None:
    assert_scope(ROOT)
    inventory = json.loads(
        (ROOT / "docs/development/phase_12_18_h2_r3_d3/IMPLEMENTATION_SCOPE.json").read_text(
            "utf-8"
        )
    )
    assert set(inventory["paths"]) == set(PATHS) and len(PATHS) == 46
    for path in inventory["protected"]:
        raw = subprocess.run(
            ["git", "show", f"{BASELINE}:{path}"], cwd=ROOT, check=True, capture_output=True
        ).stdout
        from tests.support.r4_scope_guard import baseline_view as r4_view
        assert digest(raw) == digest(r4_view(ROOT, path)), path


def test_restoration_dto_pure_and_default_factories_not_live_wired() -> None:
    tree = ast.parse(
        (ROOT / "backend/modules/work_orchestration/contracts/dto/r3_restoration.py").read_bytes()
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not any(
                s in (node.module or "") for s in ("adapters", "infrastructure", "sqlite", "openai")
            )
        if isinstance(node, ast.Import):
            assert all(
                n.name not in {"os", "pathlib", "socket", "sqlite3", "subprocess"}
                for n in node.names
            )
    for name in ("conversation", "r3_review_modify"):
        raw = (ROOT / f"backend/infrastructure/composition/factories/{name}.py").read_text("utf-8")
        assert "build_harden_adapter" not in raw and "build_restored_r3" not in raw
    binding = (ROOT / "backend/infrastructure/composition/bindings/r3_agents.py").read_text("utf-8")
    assert 'CapabilityId("CAP-G02")' in binding
    projection = (
        ROOT / "backend/infrastructure/composition/bindings/r3_harden_projection.py"
    ).read_text("utf-8")
    assert '"base_bundle"' not in projection
