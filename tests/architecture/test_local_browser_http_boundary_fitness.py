from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
API = BACKEND / "adapters" / "inbound" / "api"
CONFIG = BACKEND / "infrastructure" / "config" / "schemas" / "http.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_b04_adds_no_http_server_framework_or_route() -> None:
    from tests.architecture.test_local_browser_product_boundary import (
        route_contract_violations,
        server_import_violations,
    )

    assert server_import_violations(ROOT) == []
    assert {
        path.relative_to(ROOT).as_posix() for path in API.rglob("*.py")
        if path.name in {"server.py", "routes.py"}
    } == {"backend/adapters/inbound/api/server.py", "backend/adapters/inbound/api/routes.py"}
    assert route_contract_violations(ROOT) == []


def test_b04_contract_has_no_provider_database_repository_or_business_dependency() -> None:
    imports = set()
    for path in API.rglob("*.py"):
        imports.update(_imports(path))
    forbidden = (
        "anthropic",
        "backend.adapters.outbound",
        "backend.modules",
        "calibration_tooling",
        "openai",
        "sqlite3",
    )

    assert not any(module.startswith(forbidden) for module in imports)


def test_loopback_and_fail_closed_defaults_are_encoded() -> None:
    source = CONFIG.read_text(encoding="utf-8")

    assert 'DEFAULT_HTTP_BIND_HOST: Final = "127.0.0.1"' in source
    assert 'LOCAL_HTTP_BIND_HOSTS: Final = ("127.0.0.1", "::1")' in source
    assert "port: int" in source
    assert "debug: bool = False" in source
    assert "reload: bool = False" in source
    assert "docs_enabled: bool = False" in source
    assert "stateful_sessions: bool = False" in source
    assert "cors_allow_credentials: bool = False" in source


def test_non_loopback_and_permissive_literals_are_rejection_only() -> None:
    source = CONFIG.read_text(encoding="utf-8")
    api_source = "\n".join(
        path.read_text(encoding="utf-8") for path in API.rglob("*.py")
    )

    assert "0.0.0.0" not in source
    assert 'bind_host: str = "::"' not in source
    assert 'cors_allowed_origins: tuple[str, ...] = ("*",)' not in source
    assert "allow_credentials: bool = True" not in source
    assert "traceback" not in api_source


def test_b04_reuses_b03_observability_contract_without_second_id_generator() -> None:
    source = (API / "local_browser.py").read_text(encoding="utf-8")

    assert "correlation_id(" in source
    assert "http_request(" in source
    assert "security_rejected(" in source
    assert "uuid" not in source.casefold()
    assert "random" not in source.casefold()


def test_b04_adds_no_frontend_public_url_or_drive_runtime_dependency() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for root in (API, CONFIG.parent)
        for path in root.rglob("*.py")
    )

    from tests.architecture.test_local_browser_product_boundary import frontend_violations

    assert frontend_violations(ROOT) == []
    assert "google drive" not in source.casefold()
    assert "0.0.0.0" not in source
    assert "192.168." not in source
