from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLING = ROOT / "calibration_tooling"
RUNTIME = TOOLING / "runtime"
OBSERVABILITY = TOOLING / "observability"


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _constructor_sites(constructor: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(TOOLING)
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == constructor
            for node in ast.walk(_tree(path))
        )
    )


def test_b04_has_exact_runtime_and_observability_surface() -> None:
    assert {path.name for path in RUNTIME.glob("*.py")} == {
        "__init__.py",
        "authorization.py",
        "budget.py",
        "cli.py",
        "composition.py",
        "configuration.py",
        "ledger.py",
        "runner.py",
    }
    assert {path.name for path in OBSERVABILITY.glob("*.py")} == {
        "__init__.py",
        "events.py",
        "redaction.py",
    }


def test_composition_is_the_only_active_provider_assembly_site() -> None:
    composition = TOOLING / "runtime/composition.py"
    assert _constructor_sites("AnthropicMessagesTransport") == (composition,)
    assert _constructor_sites("AnthropicCalibrationScorer") == (composition,)
    assert _constructor_sites("CanonicalCalibrationRunner") == (composition,)


def test_runtime_reads_no_ambient_environment_filesystem_or_provider_sdk() -> None:
    imports = {
        module
        for root in (RUNTIME, OBSERVABILITY)
        for path in _python_files(root)
        for module in _imports(path)
    }
    forbidden = {
        "anthropic",
        "argparse",
        "httpx",
        "openai",
        "os",
        "pathlib",
        "requests",
        "socket",
        "sqlite3",
        "sys",
        "urllib",
    }
    assert {module.split(".")[0] for module in imports}.isdisjoint(forbidden)
    assert all(not module.startswith("tests") for module in imports)


def test_live_is_disabled_by_default_and_cli_is_dependency_injected() -> None:
    configuration = (RUNTIME / "configuration.py").read_text(encoding="utf-8")
    cli = (RUNTIME / "cli.py").read_text(encoding="utf-8")
    assert "LIVE_PROVIDER_DEFAULT_ENABLED: Final = False" in configuration
    assert "ACTIVE_CLI_TARGET: Final" in cli
    assert "sys.argv" not in cli
    assert "os.environ" not in cli
    assert "getenv(" not in cli
    assert "Path(" not in cli


def test_safe_telemetry_schema_has_no_content_or_secret_fields() -> None:
    event_names = {
        node.target.id
        for node in ast.walk(_tree(OBSERVABILITY / "events.py"))
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }
    assert {
        "payload",
        "projection",
        "prompt",
        "response",
        "secret",
        "thinking",
    }.isdisjoint(event_names)
    redaction = (OBSERVABILITY / "redaction.py").read_text(encoding="utf-8")
    assert "SafeTelemetryValue = str | int | None" in redaction
