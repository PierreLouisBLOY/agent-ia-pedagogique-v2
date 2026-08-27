from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend" / "agent_runtime"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        name
        for node in ast.walk(tree)
        for name in (
            ([node.module] if isinstance(node, ast.ImportFrom) else [])
            if not isinstance(node, ast.Import)
            else [alias.name for alias in node.names]
        )
        if name
    }


def test_global_security_composition_has_no_io_or_authority_owner() -> None:
    path = BACKEND / "security" / "runtime_composition.py"
    source = path.read_text(encoding="utf-8")
    imports = _imports(path)

    assert "SecurityRuntimeGuard" in source
    assert "RuntimeSecurityDisposition" in source
    assert all(
        fragment not in module
        for module in imports
        for fragment in (
            "backend.adapters",
            "backend.infrastructure",
            "logging",
            "pathlib",
            "requests",
            "sqlalchemy",
            "subprocess",
        )
    )
    assert all(
        token not in source
        for token in ("PolicyDisposition", "GateEngine", "ToolCallPolicy", "execute(")
    )


def test_recovery_revalidates_security_without_storing_assessments() -> None:
    replay = (BACKEND / "recovery" / "replay.py").read_text(encoding="utf-8")
    coordinator = (BACKEND / "recovery" / "coordinator.py").read_text(
        encoding="utf-8"
    )
    snapshot = (BACKEND / "recovery" / "snapshot.py").read_text(encoding="utf-8")

    assert "SecurityRevalidationStatus" in replay
    assert "canonical_authority.security_assessment" in coordinator
    assert "RuntimeSecurityAssessment" not in snapshot
    assert "SecurityEvent" not in snapshot
