from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from backend.agent_runtime.contracts import AgentId
from backend.agent_runtime.policy import BASELINE_AGENT_RUNTIME_POLICY
from backend.agent_runtime.registry import BASELINE_AGENT_REGISTRY, AgentRole

ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME = ROOT / "backend" / "agent_runtime"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def definitions(name: str) -> tuple[Path, ...]:
    found: list[Path] = []
    for path in AGENT_RUNTIME.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
            for node in ast.walk(tree)
        ):
            found.append(path)
    return tuple(found)


def test_ag01_remains_unique_orchestrator_and_specialist_roles_are_unchanged() -> None:
    orchestrators = tuple(
        item.agent_id for item in BASELINE_AGENT_REGISTRY.all() if item.is_orchestrator
    )
    assert orchestrators == (AgentId.AG_01,)
    assert BASELINE_AGENT_REGISTRY.get(AgentId.AG_02).role is AgentRole.EVIDENCE_RETRIEVAL
    assert (
        BASELINE_AGENT_REGISTRY.get(AgentId.AG_03).role
        is AgentRole.GENERATOR_TRANSFORMER
    )
    assert BASELINE_AGENT_REGISTRY.get(AgentId.AG_04).role is AgentRole.REVIEWER_CRITIC


def test_e_reuses_unique_scope_content_label_policy_and_structural_classifier() -> None:
    handoff = AGENT_RUNTIME / "security" / "multi_agent.py"
    imported = imports(handoff)
    assert "backend.agent_runtime.policy" in imported
    assert "backend.agent_runtime.security.tool_application" in imported
    assert definitions("PermissionScopeEvaluator") == (
        AGENT_RUNTIME / "policy" / "permission_evaluator.py",
    )
    assert definitions("InstructionDataBoundaryPolicy") == (
        AGENT_RUNTIME / "security" / "content_isolation.py",
    )
    assert definitions("ContentTrustLabel") == (
        AGENT_RUNTIME / "contracts" / "security" / "trust.py",
    )
    assert definitions("DelegationEnvelope") == (
        AGENT_RUNTIME / "contracts" / "planning" / "delegation.py",
    )


def test_delegation_depth_is_not_increased_and_specialist_redelegation_is_closed() -> None:
    assert BASELINE_AGENT_RUNTIME_POLICY.max_delegation_depth == 2
    source = (AGENT_RUNTIME / "contracts" / "planning" / "delegation.py").read_text(
        encoding="utf-8"
    )
    assert "delegation_depth: int = 1" in source
    assert "permission_scope.delegable" in source


def test_e_does_not_import_tool_application_gate_recovery_runtime_or_observability_owners() -> None:
    e_files = (
        AGENT_RUNTIME / "security" / "multi_agent.py",
        AGENT_RUNTIME / "contracts" / "security" / "agent_handoff.py",
        AGENT_RUNTIME / "contracts" / "planning" / "delegation.py",
        AGENT_RUNTIME / "contracts" / "delegation" / "delegation_result.py",
        AGENT_RUNTIME / "contracts" / "invocation" / "agent_result.py",
    )
    imported = {module for path in e_files for module in imports(path)}
    forbidden = (
        "backend.agent_runtime.application_routing",
        "backend.agent_runtime.gates",
        "backend.agent_runtime.recovery",
        "backend.agent_runtime.runtime",
        "backend.agent_runtime.tools.router",
        "backend.infrastructure.observability",
    )
    assert all(not module.startswith(prefix) for module in imported for prefix in forbidden)


def test_e_adds_no_secret_scanner_event_sink_or_runtime_dependency() -> None:
    assert definitions("SecretScanner") == ()
    assert definitions("SecurityEventSink") == ()
    with (ROOT / "pyproject.toml").open("rb") as stream:
        assert tomllib.load(stream)["project"]["dependencies"] == ["openai>=3.5,<4"]
