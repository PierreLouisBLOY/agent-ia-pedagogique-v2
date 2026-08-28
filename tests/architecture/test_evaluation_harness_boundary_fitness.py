from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
HARNESS = ROOT / "evaluation_harness"
QUALITY_EVALUATION = BACKEND / "modules" / "quality_evaluation"
SCORING = HARNESS / "scoring"
SCORING_CONTRACTS = HARNESS / "contracts" / "scoring.py"
RUNNER = HARNESS / "runner"


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


def _assertion_spec_classes() -> tuple[ast.ClassDef, ...]:
    return tuple(
        node
        for path in _python_files(HARNESS)
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name.endswith("AssertionSpec")
    )


def _scoring_contract_classes() -> tuple[ast.ClassDef, ...]:
    protected = {
        "EvaluationRubric",
        "EvaluationScoringCriterionSpec",
        "RubricScoreResult",
        "ScoreResult",
        "ScorerOutcome",
    }
    return tuple(
        node
        for node in ast.walk(_tree(SCORING_CONTRACTS))
        if isinstance(node, ast.ClassDef) and node.name in protected
    )


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


def test_harness_contains_no_duplicate_runner_reporting_or_provider_semantics() -> None:
    forbidden_classes = {
        "ConcurrentEvaluationRunner",
        "EvaluationScorer",
        "EvaluationReporter",
        "JsonEvaluationReporter",
        "JsonEvaluationSerializer",
        "JudgeModel",
        "MarkdownEvaluationReporter",
        "ProviderScorer",
        "PytestRunner",
        "TestCollector",
        "WeightedScore",
    }
    assert _defined_classes(HARNESS).isdisjoint(forbidden_classes)


def test_assertion_specs_expose_only_bounded_data_fields() -> None:
    forbidden_field_names = {
        "actual",
        "expected",
        "import_path",
        "metadata",
        "payload",
        "predicate",
        "python_expression",
    }
    forbidden_annotation_names = {"Any", "Callable", "Mapping"}
    for class_node in _assertion_spec_classes():
        fields = tuple(
            node
            for node in class_node.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
        )
        assert {node.target.id for node in fields}.isdisjoint(forbidden_field_names)
        assert all(
            not forbidden_annotation_names.intersection(
                child.id
                for child in ast.walk(node.annotation)
                if isinstance(child, ast.Name)
            )
            for node in fields
        )


def test_scoring_contracts_have_no_float_callable_mapping_or_arbitrary_config() -> None:
    forbidden_field_names = {
        "actual",
        "config",
        "expected",
        "import_path",
        "metadata",
        "model_name",
        "payload",
        "prompt",
        "provider_params",
        "threshold",
        "verdict",
    }
    forbidden_annotation_names = {"Any", "Callable", "Mapping", "float"}
    for class_node in _scoring_contract_classes():
        fields = tuple(
            node
            for node in class_node.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
        )
        assert {node.target.id for node in fields}.isdisjoint(forbidden_field_names)
        assert all(
            not forbidden_annotation_names.intersection(
                child.id
                for child in ast.walk(node.annotation)
                if isinstance(child, ast.Name)
            )
            for node in fields
        )


def test_scoring_never_imports_or_mutates_evaluation_verdict() -> None:
    paths = (*_python_files(SCORING), SCORING_CONTRACTS)
    assert all(
        "EvaluationVerdict"
        not in {
            node.id
            for node in ast.walk(_tree(path))
            if isinstance(node, ast.Name)
        }
        for path in paths
    )


def test_no_binary_or_speculative_ordinal_score_contract_exists() -> None:
    assert _defined_classes(HARNESS).isdisjoint(
        {"BinaryScore", "OrdinalScale", "OrdinalScore"}
    )


def test_runner_has_no_retry_replay_concurrency_or_unbounded_loop() -> None:
    forbidden_names = {
        "RecoveryCoordinator",
        "ReplayGuard",
        "RetryPolicy",
        "Thread",
        "Process",
    }
    for path in _python_files(RUNNER):
        tree = _tree(path)
        names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }
        assert names.isdisjoint(forbidden_names)
        assert not any(
            isinstance(node, (ast.AsyncFor, ast.AsyncFunctionDef, ast.While))
            for node in ast.walk(tree)
        )


def test_runner_contains_no_reporter_serializer_provider_or_model_token() -> None:
    forbidden_fragments = {
        "anthropic",
        "junit",
        "markdown",
        "model_name",
        "openai",
        "provider",
        "reporter",
        "serializer",
        "token_price",
    }
    for path in _python_files(RUNNER):
        source = path.read_text(encoding="utf-8").lower()
        assert all(fragment not in source for fragment in forbidden_fragments)


def test_harness_has_no_dynamic_loading_or_arbitrary_code_execution() -> None:
    forbidden_names = {"eval", "exec", "__import__"}
    forbidden_attributes = {"import_module"}
    for path in _python_files(HARNESS):
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            assert not (
                isinstance(node.func, ast.Name) and node.func.id in forbidden_names
            )
            assert not (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden_attributes
            )


def test_harness_has_no_global_mutable_registry() -> None:
    mutable_factories = {"dict", "list", "set", "defaultdict"}
    for path in _python_files(HARNESS):
        for node in _tree(path).body:
            assigned_names: set[str] = set()
            if isinstance(node, ast.Assign):
                assigned_names.update(
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name)
                )
            elif isinstance(node, ast.AnnAssign) and isinstance(
                node.target, ast.Name
            ):
                assigned_names.add(node.target.id)
            if assigned_names == {"__all__"}:
                continue
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
            assert not isinstance(value, (ast.Dict, ast.List, ast.Set))
            assert not (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in mutable_factories
            )


def test_harness_contract_names_are_unique_outside_tests() -> None:
    protected = {
        "EvaluationCase",
        "EvaluationSuite",
        "EvaluationVerdict",
        "CaseExecutionResult",
        "CaseEvaluationResult",
        "AssertionResult",
        "ScoreResult",
        "RubricScoreResult",
        "RepetitionEvaluationResult",
        "EvaluationRunner",
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
