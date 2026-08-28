from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
AGENT_RUNTIME = BACKEND / "agent_runtime"


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _definitions(name: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_files(BACKEND)
        if any(
            isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name
            for node in ast.walk(_tree(path))
        )
    )


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_safe_mapping_and_sensitive_value_policy_have_unique_owners() -> None:
    assert _definitions("freeze_safe_mapping") == (BACKEND / "shared_kernel" / "_safe_data.py",)
    assert _definitions("SensitiveValuePolicy") == (
        AGENT_RUNTIME / "security" / "sensitive_values.py",
    )
    assert _definitions("StructuredDataLimits") == (
        BACKEND / "shared_kernel" / "_value_safety.py",
    )


def test_f_reuses_c_d_e_boundaries_without_changing_their_owners() -> None:
    helper = AGENT_RUNTIME / "security" / "tool_application.py"
    imports = _imports(helper)
    assert "backend.agent_runtime.security.content_isolation" in imports
    assert "backend.agent_runtime.security.structural_keys" in imports
    assert "backend.agent_runtime.security.sensitive_values" in imports
    assert len(_definitions("InstructionDataBoundaryPolicy")) == 1
    assert len(_definitions("structural_key_locations")) == 1
    assert len(_definitions("AgentHandoffSecurityPolicy")) == 1


def test_f_adds_no_secret_store_provider_network_observability_or_recovery_owner() -> None:
    f_files = (
        BACKEND / "shared_kernel" / "_value_safety.py",
        AGENT_RUNTIME / "security" / "sensitive_values.py",
    )
    imports = {module for path in f_files for module in _imports(path)}
    forbidden_imports = {
        "boto3",
        "httpx",
        "logging",
        "openai",
        "requests",
        "socket",
        "subprocess",
    }
    assert imports.isdisjoint(forbidden_imports)
    for forbidden_name in (
        "KMS",
        "SecretManager",
        "SecretStore",
        "SecurityEventSink",
        "Vault",
    ):
        assert _definitions(forbidden_name) == ()
    recovery_imports = {
        module
        for path in _python_files(AGENT_RUNTIME / "recovery")
        for module in _imports(path)
    }
    assert all("sensitive_values" not in module for module in recovery_imports)


def test_security_events_and_error_envelopes_use_agent_safe_value_boundaries() -> None:
    event_source = (
        AGENT_RUNTIME / "contracts" / "security" / "security_event.py"
    ).read_text(encoding="utf-8")
    error_source = (
        AGENT_RUNTIME / "contracts" / "errors" / "error_envelope.py"
    ).read_text(encoding="utf-8")
    assert "freeze_agent_safe_mapping" in event_source
    assert "SECURITY_EVENT_DATA_LIMITS" in event_source
    assert "require_agent_safe_text" in error_source
    assert "ERROR_SAFE_DATA_LIMITS" in error_source


def test_project_keeps_zero_runtime_dependencies() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        assert tomllib.load(stream)["project"]["dependencies"] == ["openai>=3.5,<4"]
