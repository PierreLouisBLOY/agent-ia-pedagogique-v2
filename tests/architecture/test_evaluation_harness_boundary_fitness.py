from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
HARNESS = ROOT / "evaluation_harness"
QUALITY_EVALUATION = BACKEND / "modules" / "quality_evaluation"


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


def _defined_classes(root: Path) -> set[str]:
    return {
        node.name
        for path in _python_files(root)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef)
    }


def _annotated_fields(root: Path) -> set[str]:
    return {
        node.target.id
        for path in _python_files(root)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }


def test_production_backend_never_imports_the_offline_evaluation_harness() -> None:
    for path in _python_files(BACKEND):
        assert all(
            not module.startswith("evaluation_harness") for module in _imports(path)
        )


def test_harness_depends_only_on_stdlib_internal_contracts_and_shared_value_safety() -> None:
    imports = {
        module for path in _python_files(HARNESS) for module in _imports(path)
    }
    backend_imports = {module for module in imports if module.startswith("backend")}
    assert backend_imports == {"backend.shared_kernel._value_safety"}
    assert all(not module.startswith("tests") for module in imports)
    assert "pytest" not in imports


def test_harness_has_no_infrastructure_io_provider_or_runtime_dependency() -> None:
    forbidden_roots = {
        "anthropic",
        "asyncio",
        "boto3",
        "google",
        "httpx",
        "openai",
        "os",
        "pathlib",
        "random",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "threading",
        "time",
        "urllib",
        "uuid",
    }
    imports = {
        module for path in _python_files(HARNESS) for module in _imports(path)
    }
    roots = {module.split(".")[0] for module in imports}
    assert roots.isdisjoint(forbidden_roots)
    assert all("backend.infrastructure" not in module for module in imports)
    assert all("backend.agent_runtime" not in module for module in imports)


def test_quality_evaluation_domain_scaffold_is_not_a_harness_dependency() -> None:
    imports = {
        module for path in _python_files(HARNESS) for module in _imports(path)
    }
    assert all("quality_evaluation" not in module for module in imports)
    assert QUALITY_EVALUATION.is_dir()


def test_contract_fields_expose_no_authority_or_arbitrary_data_channel() -> None:
    forbidden_fields = {
        "allow",
        "approve",
        "authority",
        "capability_owner",
        "config",
        "evidence_content",
        "exception",
        "gate_approval",
        "metadata",
        "output",
        "payload",
        "permission",
        "prompt",
        "reasoning",
        "recovery_authority",
        "security_authority",
    }
    assert _annotated_fields(HARNESS).isdisjoint(forbidden_fields)


def test_b_contains_no_runner_scoring_reporting_or_assertion_semantics() -> None:
    forbidden_classes = {
        "AssertionEvaluator",
        "EvaluationRunner",
        "EvaluationScorer",
        "JsonEvaluationReporter",
        "MarkdownEvaluationReporter",
        "Rubric",
        "ScoreResult",
        "WeightedScore",
    }
    assert _defined_classes(HARNESS).isdisjoint(forbidden_classes)
    for path in _python_files(HARNESS):
        assert not any(
            isinstance(node, (ast.AsyncFor, ast.AsyncFunctionDef, ast.While))
            for node in ast.walk(_tree(path))
        )


def test_harness_contract_names_are_unique_outside_tests() -> None:
    protected = {
        "EvaluationCase",
        "EvaluationSuite",
        "EvaluationVerdict",
        "CaseExecutionResult",
        "CaseEvaluationResult",
        "SuiteEvaluationResult",
    }
    definitions = {
        name: tuple(
            path
            for root in (BACKEND, HARNESS)
            for path in _python_files(root)
            if any(
                isinstance(node, ast.ClassDef) and node.name == name
                for node in ast.walk(_tree(path))
            )
        )
        for name in protected
    }
    assert all(
        len(paths) == 1 and HARNESS in paths[0].parents
        for paths in definitions.values()
    )


def test_project_runtime_dependencies_remain_empty() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["dependencies"] == []
