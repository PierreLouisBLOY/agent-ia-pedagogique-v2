from __future__ import annotations

import importlib
import subprocess
import tomllib
from pathlib import Path

from tests.support.repository_hygiene import forbidden_source_paths, repository_paths

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

MODULE_NAMES = (
    "knowledge_reference",
    "documents_provenance",
    "resource_library",
    "pedagogical_design",
    "transformation_assembly",
    "analysis_simulation",
    "pedagogical_context",
    "work_orchestration",
    "validation_control",
    "quality_evaluation",
    "lifecycle_promotion",
    "materialization_export",
    "audit_traceability",
)

MODULE_TEMPLATE_DIRS = (
    "domain/aggregates",
    "domain/entities",
    "domain/value_objects",
    "domain/policies",
    "domain/services",
    "domain/errors",
    "domain/events",
    "contracts/refs",
    "contracts/snapshots",
    "contracts/dto",
    "contracts/events",
    "ports/inbound",
    "ports/outbound",
    "application/commands",
    "application/queries",
    "application/orchestration",
    "application/services",
    "application/dto/input",
    "application/dto/output",
    "application/mappers",
)

STRUCTURAL_DIRS = (
    "backend/shared_kernel/identifiers",
    "backend/shared_kernel/references",
    "backend/shared_kernel/correlation",
    "backend/shared_kernel/errors",
    "backend/shared_kernel/result",
    "backend/shared_kernel/time",
    "backend/core_contracts/invocation",
    "backend/core_contracts/outcome",
    "backend/core_contracts/capability",
    "backend/agent_runtime/contracts/common",
    "backend/agent_runtime/contracts/policy",
    "backend/agent_runtime/contracts/planning",
    "backend/agent_runtime/contracts/invocation",
    "backend/agent_runtime/contracts/errors",
    "backend/adapters/inbound/api",
    "backend/adapters/inbound/local_ui",
    "backend/adapters/inbound/cli",
    "backend/adapters/inbound/agent_tools",
    "backend/adapters/inbound/batch",
    "backend/adapters/outbound/persistence",
    "backend/adapters/outbound/transaction",
    "backend/adapters/outbound/search",
    "backend/adapters/outbound/read_models",
    "backend/adapters/outbound/document_content",
    "backend/adapters/outbound/generation",
    "backend/adapters/outbound/semantic",
    "backend/adapters/outbound/materialization",
    "backend/adapters/outbound/artifacts",
    "backend/adapters/outbound/delivery",
    "backend/adapters/outbound/deferred",
    "backend/adapters/outbound/events",
    "backend/adapters/outbound/system",
    "backend/infrastructure/config/schemas",
    "backend/infrastructure/config/loaders",
    "backend/infrastructure/config/effective_config",
    "backend/infrastructure/config/secrets",
    "backend/infrastructure/composition/bindings",
    "backend/infrastructure/composition/factories",
    "backend/infrastructure/composition/bootstrap",
    "backend/infrastructure/composition/readiness",
    "backend/infrastructure/observability",
    "tests/architecture",
    "tests/unit/domain",
    "tests/unit/application",
    "tests/contracts/inbound",
    "tests/contracts/outbound",
    "tests/adapters/inbound",
    "tests/adapters/outbound",
    "tests/integration/db",
    "tests/integration/transactions",
    "tests/integration/modules",
    "tests/integration/async_postcommit",
    "tests/e2e/core",
    "tests/providers",
    "tests/non_functional",
    "tests/support/fixtures",
    "tests/support/doubles",
    "tests/support/testkits",
    "architecture/adr",
)


def test_phase_6_15_structural_zones_exist() -> None:
    missing = [relative for relative in STRUCTURAL_DIRS if not (ROOT / relative).is_dir()]
    assert missing == []


def test_all_canonical_modules_and_templates_exist() -> None:
    modules_root = BACKEND / "modules"
    actual_modules = {
        path.name
        for path in modules_root.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert actual_modules == set(MODULE_NAMES)

    missing = [
        f"{module}/{relative}"
        for module in MODULE_NAMES
        for relative in MODULE_TEMPLATE_DIRS
        if not (modules_root / module / relative).is_dir()
    ]
    assert missing == []


def test_forbidden_global_backend_locations_are_absent() -> None:
    forbidden = ("domain", "repositories", "services")
    present = [name for name in forbidden if (BACKEND / name).exists()]
    assert present == []


def test_modules_do_not_contain_adapters_or_infrastructure() -> None:
    forbidden = [
        path.relative_to(ROOT).as_posix()
        for module in MODULE_NAMES
        for name in ("adapters", "infrastructure")
        if (path := BACKEND / "modules" / module / name).exists()
    ]
    assert forbidden == []


def test_source_tree_contains_no_runtime_database() -> None:
    assert forbidden_source_paths(repository_paths(ROOT)) == ()


def test_structural_packages_are_importable() -> None:
    packages = [
        "backend",
        "backend.shared_kernel",
        "backend.core_contracts",
        "backend.agent_runtime",
        "backend.agent_runtime.contracts",
        "backend.modules",
        "backend.adapters",
        "backend.adapters.inbound",
        "backend.adapters.outbound",
        "backend.infrastructure",
        *[f"backend.modules.{module}" for module in MODULE_NAMES],
    ]

    for package in packages:
        assert importlib.import_module(package).__name__ == package


def test_canonical_artifacts_package_is_not_ignored_by_git() -> None:
    package = "backend/adapters/outbound/artifacts/__init__.py"
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", package],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, result.stdout + result.stderr


def test_no_production_dependency_is_declared() -> None:
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert project["requires-python"] == ">=3.12,<3.13"
    assert project["dependencies"] == ["openai>=3.5,<4"]
