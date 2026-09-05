from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
LOCAL = BACKEND / "infrastructure" / "observability" / "local.py"
OPERATIONAL = BACKEND / "infrastructure" / "observability" / "operational.py"
BOOTSTRAP = (
    BACKEND / "infrastructure" / "composition" / "bootstrap" / "observability.py"
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_obs_a_constants_and_local_path_are_exact() -> None:
    source = LOCAL.read_text(encoding="utf-8")

    assert 'Path("logs") / "observability.ndjson"' in source
    assert "ROTATION_SIZE_BYTES: Final = 5 * 1_024 * 1_024" in source
    assert "MAX_LOG_FILE_COUNT: Final = 5" in source
    assert "RETENTION_DAYS: Final = 14" in source
    assert "MAX_SHUTDOWN_FLUSH_SECONDS: Final = 2" in source
    assert "assert_local_data_root" in source
    assert "ensure_private_directory" in source
    assert "harden_private_file" in source


def test_local_observability_has_no_network_provider_or_business_import() -> None:
    imports = _imports(LOCAL) | _imports(OPERATIONAL) | _imports(BOOTSTRAP)
    forbidden = (
        "anthropic",
        "backend.adapters",
        "backend.modules",
        "httpx",
        "openai",
        "requests",
        "socket",
        "urllib",
    )

    assert not any(module.startswith(forbidden) for module in imports)


def test_domain_and_application_do_not_import_concrete_observability() -> None:
    violations: list[str] = []
    roots = tuple(BACKEND.glob("modules/*/domain")) + tuple(
        BACKEND.glob("modules/*/application")
    )
    for root in roots:
        for path in root.rglob("*.py"):
            if any(
                module.startswith("backend.infrastructure.observability")
                for module in _imports(path)
            ):
                violations.append(str(path.relative_to(ROOT)))

    assert violations == []


def test_http_observability_adds_no_server_framework_or_route() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")
    imports = _imports(BOOTSTRAP)

    assert "http_request" in source
    assert all(
        not module.startswith(("fastapi", "flask", "starlette", "uvicorn"))
        for module in imports
    )
    from tests.architecture.test_local_browser_product_boundary import (
        observability_server_violations,
    )

    assert observability_server_violations(source) == []


def test_event_schema_is_an_explicit_allowlist_without_generic_export() -> None:
    source = OPERATIONAL.read_text(encoding="utf-8")

    for forbidden in (
        "asdict(",
        "__dict__",
        "default=str",
        "repr(",
        "str(error)",
        "traceback",
    ):
        assert forbidden not in source
    for required in (
        "APP_STARTUP",
        "APP_SHUTDOWN",
        "HTTP_REQUEST_COMPLETED",
        "HTTP_VALIDATION_REJECTED",
        "SQLITE_BOOTSTRAP_COMPLETED",
        "SQLITE_MIGRATION_COMPLETED",
        "SQLITE_BACKUP_COMPLETED",
        "SQLITE_RECOVERY_COMPLETED",
        "PROVIDER_CALL_STARTED",
        "PROVIDER_CALL_COMPLETED",
        "PROVIDER_CALL_FAILED",
        "SECURITY_PATH_REJECTED",
        "APP_UNHANDLED_EXCEPTION",
    ):
        assert required in source
