from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLING = ROOT / "calibration_tooling"
ADAPTER = TOOLING / "adapters/anthropic"
HISTORICAL = (
    ROOT / "tests/providers/anthropic/transport.py",
    ROOT / "tests/providers/anthropic/scorer.py",
)
HISTORICAL_SHA256 = {
    "transport.py": "15ecf4b27ac8840dc503201864614a304917d3d43132b159da6a520044787b5b",
    "scorer.py": "3be22f3a4ee19a3e2095f52f459b30d0b204a7e37437b2e5b33ab0ee03a76119",
}


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_active_anthropic_adapter_has_the_approved_six_file_surface() -> None:
    assert {path.name for path in ADAPTER.glob("*.py")} == {
        "__init__.py",
        "contracts.py",
        "mapping.py",
        "parser.py",
        "scorer.py",
        "transport.py",
    }


def test_active_adapter_imports_no_test_history_or_provider_sdk() -> None:
    imports = {module for path in _python_files(ADAPTER) for module in _imports(path)}
    forbidden = {
        "anthropic",
        "httpx",
        "openai",
        "requests",
        "socket",
        "sqlite3",
        "urllib",
    }
    assert all(not module.startswith("tests") for module in imports)
    assert {module.split(".")[0] for module in imports}.isdisjoint(forbidden)


def test_contracts_and_application_remain_provider_neutral() -> None:
    roots = (TOOLING / "contracts", TOOLING / "application")
    imports = {
        module
        for root in roots
        for path in _python_files(root)
        for module in _imports(path)
    }
    assert all("anthropic" not in module.lower() for module in imports)


def test_adapter_has_no_retry_loop_environment_or_persistence_access() -> None:
    execution_files = (ADAPTER / "scorer.py", ADAPTER / "transport.py")
    trees = [
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in execution_files
    ]
    assert not any(isinstance(node, (ast.For, ast.While)) for tree in trees for node in ast.walk(tree))
    imports = {module for path in _python_files(ADAPTER) for module in _imports(path)}
    assert {module.split(".")[0] for module in imports}.isdisjoint(
        {"os", "pathlib", "sqlite3"}
    )
    for path in _python_files(ADAPTER):
        if path.name != "transport.py":
            assert "reveal_for_transport" not in path.read_text(encoding="utf-8")


def test_active_scorer_structurally_implements_the_b02_provider_port() -> None:
    scorer_source = (ADAPTER / "scorer.py").read_text(encoding="utf-8")
    tree = ast.parse(scorer_source)
    methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "invoke" in methods
    assert "score" not in methods


def test_two_historical_anthropic_implementations_remain_byte_exact() -> None:
    import hashlib

    assert len(HISTORICAL) == 2
    for path in HISTORICAL:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == HISTORICAL_SHA256[path.name]
