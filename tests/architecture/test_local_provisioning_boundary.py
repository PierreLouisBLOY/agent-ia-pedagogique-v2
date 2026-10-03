from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPLICATION = ROOT / "backend" / "modules" / "local_provisioning"
INBOUND = ROOT / "backend" / "adapters" / "inbound" / "cli" / "local_provisioning.py"
COMPOSITION = (
    ROOT / "backend" / "infrastructure" / "composition" / "factories" / "local_provisioning.py"
)
OUTBOUND = ROOT / "backend" / "adapters" / "outbound" / "system" / "local_provisioning.py"


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_application_layer_uses_ports_and_has_no_infrastructure_sqlite_or_provider_imports() -> (
    None
):
    violations: list[str] = []
    for path in APPLICATION.rglob("*.py"):
        for imported in _imports(path):
            if (
                imported.startswith("backend.infrastructure")
                or imported.startswith("backend.adapters")
                or imported == "sqlite3"
                or imported.startswith(("openai", "anthropic", "requests", "httpx", "socket"))
            ):
                violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_trusted_local_inbound_depends_on_application_and_not_sqlite_adapter() -> None:
    modules = _imports(INBOUND)
    assert "backend.adapters.outbound.system.local_provisioning" not in modules
    assert "backend.adapters.outbound.persistence.migrations" not in modules
    assert "backend.modules.local_provisioning.application.contracts" in modules


def test_composition_is_only_wiring_point_and_adapter_reuses_existing_sqlite_lifecycle() -> None:
    composition_imports = _imports(COMPOSITION)
    assert "backend.adapters.outbound.system.local_provisioning" in composition_imports
    source = OUTBOUND.read_text(encoding="utf-8")
    assert "create_runtime_backup" in source
    assert "apply_registered_migrations" in source
    assert "backend.infrastructure.composition" not in _imports(OUTBOUND)
    assert "sqlite3" not in _imports(OUTBOUND)


def test_no_http_or_agent_tool_provisioning_surface_was_added() -> None:
    route_dir = ROOT / "backend" / "adapters" / "inbound" / "api"
    tools_dir = ROOT / "backend" / "adapters" / "inbound" / "agent_tools"
    assert not any("provision" in path.name.casefold() for path in route_dir.glob("*.py"))
    assert not any("provision" in path.name.casefold() for path in tools_dir.glob("*.py"))
