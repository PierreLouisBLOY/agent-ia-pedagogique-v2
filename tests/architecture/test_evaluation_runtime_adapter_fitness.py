from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
HARNESS = ROOT / "evaluation_harness"
ADAPTER = ROOT / "tests" / "support" / "evaluation_runtime_adapters.py"
E2E_CORE = ROOT / "tests" / "e2e" / "core"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_runtime_adapter_is_test_only_and_imports_both_existing_sides() -> None:
    assert ADAPTER.is_file()
    imports = _imports(ADAPTER)
    assert any(item.startswith("backend.agent_runtime") for item in imports)
    assert "evaluation_harness" in imports
    assert not any(
        path.name.startswith("evaluation_runtime_")
        for root in (BACKEND, HARNESS)
        for path in root.rglob("*.py")
    )


def test_production_and_harness_dependency_directions_remain_unchanged() -> None:
    backend_imports = {
        module
        for path in BACKEND.rglob("*.py")
        for module in _imports(path)
    }
    harness_imports = {
        module
        for path in HARNESS.rglob("*.py")
        for module in _imports(path)
    }
    assert not any(item.startswith("evaluation_harness") for item in backend_imports)
    assert not any(
        item.startswith(("backend.agent_runtime", "backend.infrastructure"))
        for item in harness_imports
    )


def test_runtime_adapter_has_no_external_provider_or_network_dependency() -> None:
    forbidden_roots = {
        "anthropic",
        "boto3",
        "google",
        "httpx",
        "openai",
        "requests",
        "socket",
        "urllib",
    }
    roots = {module.split(".")[0] for module in _imports(ADAPTER)}
    assert roots.isdisjoint(forbidden_roots)


def test_runtime_adapter_has_no_dynamic_dispatch_or_mutable_global_registry() -> None:
    tree = _tree(ADAPTER)
    forbidden_calls = {"eval", "exec", "__import__"}
    assert not any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id in forbidden_calls
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
        )
        for node in ast.walk(tree)
    )
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            assert not isinstance(value, (ast.Dict, ast.List, ast.Set))


def test_projection_contract_fields_are_closed_facts_only() -> None:
    forbidden = {
        "content",
        "document_text",
        "exception",
        "message",
        "metadata",
        "output",
        "payload",
        "prompt",
        "provider_response",
        "raw",
        "reasoning",
        "secret",
    }
    protected = {
        "ClosedTechnicalFacts",
        "ClosedFactSnapshotProjector",
    }
    for node in ast.walk(_tree(ADAPTER)):
        if not isinstance(node, ast.ClassDef) or node.name not in protected:
            continue
        names = {
            child.target.id
            for child in ast.walk(node)
            if isinstance(child, ast.AnnAssign)
            and isinstance(child.target, ast.Name)
        }
        assert names.isdisjoint(forbidden)


def test_pedagogical_e2e_core_contains_declarations_and_c1_binding() -> None:
    names = {path.name for path in E2E_CORE.iterdir() if path.is_file()}
    assert {"adapters.py", "catalog.py", "expectations.py", "fixtures.py"} <= names
    assert ".gitkeep" not in names
