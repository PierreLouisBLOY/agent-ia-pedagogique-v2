from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "backend" / "infrastructure" / "filesystem" / "security.py"
ADAPTER = ROOT / "backend" / "adapters" / "outbound" / "filesystem" / "local.py"
SQLITE_TARGETS = (
    ROOT / "backend" / "adapters" / "outbound" / "persistence" / "migrations.py",
    ROOT / "backend" / "adapters" / "outbound" / "persistence" / "sqlite.py",
    ROOT / "backend" / "adapters" / "outbound" / "semantic" / "index.py",
    ROOT / "backend" / "infrastructure" / "config" / "schemas" / "sqlite.py",
    ROOT / "backend" / "infrastructure" / "composition" / "factories" / "sqlite.py",
)


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_concrete_filesystem_adapter_is_outside_agent_runtime() -> None:
    source = ADAPTER.read_text(encoding="utf-8")

    assert "class LocalSandboxFilesystemAdapter" in source
    assert "backend.agent_runtime.sandbox.model" in source
    assert not (ROOT / "backend" / "agent_runtime" / "sandbox" / "local.py").exists()


def test_uniform_security_helper_is_reused_by_all_mutable_sqlite_boundaries() -> None:
    sources = tuple(path.read_text(encoding="utf-8") for path in SQLITE_TARGETS)

    assert all("backend.infrastructure.filesystem" in source for source in sources[:4])
    assert "data_root=paths.data_directory" in sources[4]
    helper = HELPER.read_text(encoding="utf-8")
    for required in (
        "PATH_REDIRECTION_FORBIDDEN",
        "ensure_private_directory",
        "harden_private_file",
        "atomic_publish_fresh",
        "read_file_nofollow",
    ):
        assert required in helper


def test_domain_and_application_do_not_import_filesystem_adapter_or_sqlite_types() -> None:
    violations: list[str] = []
    for base in (ROOT / "backend" / "modules", ROOT / "backend" / "agent_runtime"):
        for path in base.rglob("*.py"):
            for imported in _imports(path):
                if imported.startswith("backend.adapters.outbound.filesystem") or imported.startswith(
                    "backend.infrastructure.filesystem"
                ):
                    violations.append(str(path.relative_to(ROOT)))

    assert violations == []


def test_boundary_adds_no_provider_network_or_business_dependency() -> None:
    imports = set(_imports(HELPER)) | set(_imports(ADAPTER))
    forbidden = ("openai", "anthropic", "requests", "httpx", "socket", "backend.modules")

    assert not any(module.startswith(forbidden) for module in imports)
