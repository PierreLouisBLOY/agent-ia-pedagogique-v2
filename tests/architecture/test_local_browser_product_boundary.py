from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "24b7a9850bc4644391dee2307c8a8a31036cd503"
SERVER_PATH = "backend/adapters/inbound/api/server.py"
ROUTES_PATH = "backend/adapters/inbound/api/routes.py"
_CONTRACT = "docs/development/phase_12_18_h2_local_read15/READ15_HTTP_LOCAL_V1.json"
_FORBIDDEN = ("aiohttp", "fastapi", "flask", "hypercorn", "starlette", "uvicorn")
_API_FORBIDDEN = (
    "anthropic", "backend.adapters.outbound", "backend.modules",
    "calibration_tooling", "openai", "sqlite3",
)
_EXPECTED_ROUTES = (
    (("GET",), "/api/v2/resources/{resource_ref}", None),
    (("GET", "HEAD"), "/", "index.html"),
    (("GET", "HEAD"), "/assets/app.js", "app.js"),
    (("GET", "HEAD"), "/assets/styles.css", "styles.css"),
)


def _qualified(node: ast.expr, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return _qualified(node.value, aliases) + "." + node.attr
    if isinstance(node, ast.Subscript):
        return "DYNAMIC_UNRESOLVED"
    return ""


def imported_names(source: str, path: str) -> set[str]:
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    names: set[str] = set()
    package = ".".join(Path(path).parts[:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                aliases[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                try:
                    module = importlib.util.resolve_name("." * node.level + module, package)
                except (ImportError, ValueError):
                    names.add("DYNAMIC_UNRESOLVED")
            names.add(module)
            for alias in node.names:
                full = module + "." + alias.name
                names.add(full)
                aliases[alias.asname or alias.name] = full
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                qualified = _qualified(node.value, aliases)
                if qualified:
                    aliases[target.id] = qualified
        if not isinstance(node, ast.Call):
            continue
        called = _qualified(node.func, aliases)
        if called in {"eval", "exec", "builtins.eval", "builtins.exec", "DYNAMIC_UNRESOLVED"}:
            names.add("DYNAMIC_UNRESOLVED")
        if called.endswith(("import_module", "__import__")):
            if node.args and isinstance(node.args[0], ast.Constant):
                module = node.args[0].value
                if isinstance(module, str) and not module.startswith("."):
                    names.add(module)
                else:
                    names.add("DYNAMIC_UNRESOLVED")
            else:
                names.add("DYNAMIC_UNRESOLVED")
    return names


def source_boundary_violations(source: str, path: str) -> list[str]:
    names = imported_names(source, path)
    violations = []
    for name in sorted(names):
        if name.startswith(_FORBIDDEN) or name == "DYNAMIC_UNRESOLVED":
            violations.append(name)
        if name.startswith("http.server") and path != SERVER_PATH:
            violations.append(name)
        if name.startswith("backend.adapters.inbound.api.server") and path != (
            "backend/infrastructure/composition/factories/local_browser.py"
        ):
            violations.append(name)
        if path.startswith("backend/adapters/inbound/api/") and name.startswith(_API_FORBIDDEN):
            violations.append(name)
        if "/domain/" in path or "/application/" in path and path.startswith("backend/modules/"):
            if name.startswith(("http", "urllib", "socket")):
                violations.append(name)
    if path.startswith("backend/adapters/inbound/api/") and re.search(
        r"\b(?:SELECT\s+.+\s+FROM|INSERT\s+INTO|CREATE\s+TABLE)\b", source
    ):
        violations.append("SQL_IN_HTTP")
    return violations


def server_import_violations(root: Path) -> list[str]:
    return [
        str(path.relative_to(root))
        for path in (root / "backend").rglob("*.py")
        if source_boundary_violations(
            path.read_text(encoding="utf-8"), path.relative_to(root).as_posix()
        )
    ]


def _literal(node: ast.expr, constants: dict[str, object]) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple):
        return tuple(_literal(item, constants) for item in node.elts)
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    raise ValueError("ROUTE_REGISTRY_MUST_BE_STATIC")


def route_contract_violations(root: Path) -> list[str]:
    constants: dict[str, object] = {}
    for node in ast.parse((root / ROUTES_PATH).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            if node.target.id in {"READ15_TEMPLATE", "_RESOURCE_PREFIX", "ROUTE_SPECS"}:
                constants[node.target.id] = _literal(node.value, constants)
    from backend.adapters.inbound.api.routes import ROUTE_SPECS
    contract = json.loads((root / _CONTRACT).read_text(encoding="utf-8"))
    documented = tuple(
        (tuple(row["methods"]), row["path"], row["asset"]) for row in contract["routes"]
    )
    violations = []
    if constants.get("ROUTE_SPECS") != _EXPECTED_ROUTES:
        violations.append("AST_REGISTRY_DRIFT")
    if ROUTE_SPECS != _EXPECTED_ROUTES or documented != _EXPECTED_ROUTES:
        violations.append("CONTRACT_REGISTRY_DRIFT")
    for path in (root / "backend/adapters/inbound/api").rglob("*.py"):
        if path.relative_to(root).as_posix() != ROUTES_PATH:
            if "/api/v2" in path.read_text(encoding="utf-8"):
                violations.append("ROUTE_DECLARED_OUTSIDE_REGISTRY")
    return violations


def frontend_violations(root: Path) -> list[str]:
    folder = root / "frontend"
    expected = {"index.html", "app.js", "styles.css"}
    actual = {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}
    violations = [] if actual == expected else ["ASSET_INVENTORY"]
    for path in folder.rglob("*"):
        if path.is_file():
            source = path.read_text(encoding="utf-8")
            if re.search(r"https?://|//[a-zA-Z]|@import|\bimport\s*\(|WebSocket|innerHTML|eval\(",
                         source):
                violations.append("UNSAFE_OR_EXTERNAL_ASSET")
    return violations


def observability_server_violations(source: str) -> list[str]:
    path = "backend/infrastructure/composition/bootstrap/observability.py"
    imports = imported_names(source, path)
    bad = [name for name in imports if name.startswith(
        ("backend.adapters.inbound.api", "http.server", "socket", *_FORBIDDEN)
    ) or name == "DYNAMIC_UNRESOLVED"]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = _qualified(node.func, {})
            if name.endswith((".bind", "HTTPServer", "LocalRead15Server")):
                bad.append("SERVER_CONSTRUCTION_IN_OBSERVABILITY")
    return bad


def inventory_violations(root: Path, changed: set[str] | None = None) -> list[str]:
    contract = json.loads((root / _CONTRACT).read_text(encoding="utf-8"))
    assert contract["baseline_commit"] == BASELINE
    if changed is None:
        changed = set()
        for arguments in (
            ["diff", "--name-only", BASELINE, "--"],
            ["ls-files", "--others", "--exclude-standard"],
        ):
            result = subprocess.run(
                ["git", *arguments], cwd=root, capture_output=True, text=True, check=True
            )
            changed.update(result.stdout.splitlines())
    protected = {item["path"]: item["sha256"] for item in contract["protected_documents"]}
    allowed = set(contract["approved_inventory"])
    violations = sorted(changed - allowed - set(protected))
    for name, digest in protected.items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            violations.append("PROTECTED_DOCUMENT_CHANGED:" + name)
    return violations


def test_server_framework_and_application_boundaries() -> None:
    assert server_import_violations(ROOT) == []


@pytest.mark.parametrize("source,path", [
    ("import http.server", "backend/modules/m/domain/x.py"),
    ("from http import server", "backend/modules/m/application/x.py"),
    ("import fastapi as f", SERVER_PATH),
    ("import http.server as h", "backend/adapters/inbound/api/extra.py"),
    ("from .server import LocalRead15Server", "backend/adapters/inbound/api/extra.py"),
    ("from ...outbound import persistence", "backend/adapters/inbound/api/extra.py"),
    ("import sqlite3", "backend/adapters/inbound/api/extra.py"),
    ("from ....modules import resource_library", "backend/adapters/inbound/api/extra.py"),
    ("import importlib as i\ni.import_module('http.server')", "backend/modules/m/domain/x.py"),
    ("from importlib import import_module as load\nload('sqlite3')",
     "backend/adapters/inbound/api/extra.py"),
    ("loader = __import__\nloader(name)", "backend/adapters/inbound/api/extra.py"),
    ("__import__('sqlite3')", "backend/adapters/inbound/api/extra.py"),
    ("eval(source)", "backend/adapters/inbound/api/extra.py"),
    ("connection.execute('SELECT * FROM resource')", "backend/adapters/inbound/api/extra.py"),
])
def test_ast_counterexamples_are_rejected(source: str, path: str) -> None:
    assert source_boundary_violations(source, path)


def test_only_exact_server_import_is_permitted() -> None:
    assert source_boundary_violations("from http.server import HTTPServer", SERVER_PATH) == []


def test_approved_registry_and_frontend() -> None:
    assert route_contract_violations(ROOT) == []
    assert frontend_violations(ROOT) == []


def test_a7_closed_registry_rejects_extra_routes_outside_or_inside_registry(
    tmp_path: Path,
) -> None:
    routes = tmp_path / ROUTES_PATH
    routes.parent.mkdir(parents=True)
    approved_source = (ROOT / ROUTES_PATH).read_text(encoding="utf-8")
    routes.write_text(approved_source, encoding="utf-8")
    contract = tmp_path / _CONTRACT
    contract.parent.mkdir(parents=True)
    contract.write_text((ROOT / _CONTRACT).read_text(encoding="utf-8"), encoding="utf-8")

    assert route_contract_violations(tmp_path) == []

    routes.write_text(
        approved_source.replace(
            "    ((\"GET\", \"HEAD\"), \"/assets/styles.css\", \"styles.css\"),\n)",
            "    ((\"GET\", \"HEAD\"), \"/assets/styles.css\", \"styles.css\"),\n"
            "    ((\"GET\",), \"/api/v2/extra\", None),\n)",
        ),
        encoding="utf-8",
    )
    assert "AST_REGISTRY_DRIFT" in route_contract_violations(tmp_path)

    routes.write_text(approved_source, encoding="utf-8")
    extra = routes.parent / "extra.py"
    extra.write_text('EXTRA_ROUTE = "/api/v2/extra"\n', encoding="utf-8")
    assert "ROUTE_DECLARED_OUTSIDE_REGISTRY" in route_contract_violations(tmp_path)


@pytest.mark.parametrize("source", [
    "from backend.adapters.inbound.api.server import LocalRead15Server",
    "host.bind(address)", "LocalRead15Server(service)",
    "import socket as network", "from http import server",
])
def test_observability_cannot_take_ownership_of_server(source: str) -> None:
    assert observability_server_violations(source)


def test_inventory_survives_staging_and_updated_head() -> None:
    assert inventory_violations(ROOT) == []
    for path in (
        "backend/adapters/inbound/api/extra.py", "frontend/extra.js",
        "backend/modules/resource_library/application/queries/get_resource.py",
        "requirements/lock/runtime-py312-win.txt",
    ):
        assert path in inventory_violations(ROOT, {path})


def test_existing_pure_contracts_and_original_guards_other_tests_preserved() -> None:
    expected = {
        "backend/adapters/inbound/api/local_browser.py":
            "cc7ee88ebbb41d17feb301c9707d1ab05efe3d1fa3118be8612c1b4c735d1148",
        "backend/infrastructure/config/schemas/http.py":
            "511336250f3a3274fe4f2f17f328771111250b0ec916a4e18723abc6b4ecf298",
    }
    for path, digest in expected.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    permitted = {
        "tests/architecture/test_local_browser_http_boundary_fitness.py": {
            "test_b04_adds_no_http_server_framework_or_route",
            "test_b04_adds_no_frontend_public_url_or_drive_runtime_dependency",
        },
        "tests/architecture/test_minimal_local_observability_fitness.py": {
            "test_http_observability_adds_no_server_framework_or_route",
        },
        "tests/architecture/test_security_recovery_observability_e2e_fitness.py": {
            "test_later_provider_work_preserves_phase_f_backend_owners",
        },
        "tests/architecture/test_resource_ref_contract_fitness.py": {
            "test_read15_keeps_one_field_and_deprecations_without_http_implementation",
        },
    }
    for path, changed_tests in permitted.items():
        old = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        old_functions = {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(old).body if isinstance(node, ast.FunctionDef)
            and node.name not in changed_tests
        }
        current = {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse((ROOT / path).read_text(encoding="utf-8")).body
            if isinstance(node, ast.FunctionDef) and node.name not in changed_tests
        }
        assert current == old_functions
