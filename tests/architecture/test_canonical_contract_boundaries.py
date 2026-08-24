from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED_KERNEL = ROOT / "backend" / "shared_kernel"
CORE_CONTRACTS = ROOT / "backend" / "core_contracts"
AGENT_RUNTIME = ROOT / "backend" / "agent_runtime"
AGENT_RUNTIME_CONTRACTS = AGENT_RUNTIME / "contracts"
MODULES = ROOT / "backend" / "modules"

FORBIDDEN_CORE_PREFIXES = (
    "backend.modules",
    "backend.adapters",
    "backend.infrastructure",
)
FORBIDDEN_SHARED_PREFIXES = (*FORBIDDEN_CORE_PREFIXES, "backend.core_contracts")
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "backend",
    "collections",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "types",
    "typing",
}


def _python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return modules


def test_core_contracts_depend_only_on_shared_kernel_and_stdlib() -> None:
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for path in _python_files(CORE_CONTRACTS)
        for module in _imported_modules(path)
        if module.startswith(FORBIDDEN_CORE_PREFIXES)
    ]

    assert violations == []


def test_shared_kernel_does_not_depend_on_outer_layers() -> None:
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for path in _python_files(SHARED_KERNEL)
        for module in _imported_modules(path)
        if module.startswith(FORBIDDEN_SHARED_PREFIXES)
    ]

    assert violations == []


def test_canonical_contract_implementation_has_no_third_party_imports() -> None:
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for root in (SHARED_KERNEL, CORE_CONTRACTS)
        for path in _python_files(root)
        for module in _imported_modules(path)
        if module.split(".", maxsplit=1)[0] not in ALLOWED_IMPORT_ROOTS
    ]

    assert violations == []


def test_agent_runtime_contracts_have_no_third_party_imports() -> None:
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for path in _python_files(AGENT_RUNTIME_CONTRACTS)
        for module in _imported_modules(path)
        if module.split(".", maxsplit=1)[0] not in ALLOWED_IMPORT_ROOTS
    ]

    assert violations == []


def test_agent_runtime_does_not_depend_on_modules_adapters_or_infrastructure() -> None:
    forbidden_prefixes = (
        "backend.modules",
        "backend.adapters",
        "backend.infrastructure",
    )
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for path in _python_files(AGENT_RUNTIME)
        for module in _imported_modules(path)
        if module.startswith(forbidden_prefixes)
    ]

    assert violations == []


def test_business_modules_do_not_depend_on_agent_runtime() -> None:
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for path in _python_files(MODULES)
        for module in _imported_modules(path)
        if module.startswith("backend.agent_runtime")
    ]

    assert violations == []


def test_use_case_context_has_one_canonical_definition() -> None:
    definitions = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "backend").rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ClassDef) and node.name == "UseCaseContext"
    ]

    assert definitions == [
        "backend/core_contracts/invocation/use_case_context.py"
    ]


def test_agent_runtime_contracts_have_one_canonical_definition_each() -> None:
    expected = {
        "AgentInvocation": ["backend/agent_runtime/contracts/invocation/agent_invocation.py"],
        "AgentResult": ["backend/agent_runtime/contracts/invocation/agent_result.py"],
        "DelegationEnvelope": ["backend/agent_runtime/contracts/planning/delegation.py"],
        "StepSpec": ["backend/agent_runtime/contracts/planning/step_spec.py"],
    }
    actual = {
        class_name: [
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "backend").rglob("*.py")
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        for class_name in expected
    }

    assert actual == expected


def test_delegation_request_has_no_parallel_class_definition() -> None:
    definitions = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "backend").rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ClassDef) and node.name == "DelegationRequest"
    ]

    assert definitions == []


def test_agent_runtime_does_not_define_evaluator_scheduler_or_registry_logic() -> None:
    forbidden_fragments = ("Evaluator", "Scheduler", "Registry")
    definitions = [
        f"{path.relative_to(ROOT).as_posix()}: {node.name}"
        for path in _python_files(AGENT_RUNTIME)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and any(fragment in node.name for fragment in forbidden_fragments)
    ]

    assert definitions == []
