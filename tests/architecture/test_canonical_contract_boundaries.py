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
    "re",
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
        "CorrectionRequest": [
            "backend/agent_runtime/contracts/review/correction_request.py"
        ],
        "DelegationEnvelope": ["backend/agent_runtime/contracts/planning/delegation.py"],
        "DelegationResult": [
            "backend/agent_runtime/contracts/delegation/delegation_result.py"
        ],
        "EvidenceItem": ["backend/agent_runtime/contracts/evidence/evidence_item.py"],
        "EvidenceRequest": [
            "backend/agent_runtime/contracts/evidence/evidence_request.py"
        ],
        "EvidenceSet": ["backend/agent_runtime/contracts/evidence/evidence_set.py"],
        "Finding": ["backend/agent_runtime/contracts/review/finding.py"],
        "GateDecision": ["backend/agent_runtime/contracts/gates/gate_decision.py"],
        "GateRequest": ["backend/agent_runtime/contracts/gates/gate_request.py"],
        "ProductionCandidate": [
            "backend/agent_runtime/contracts/production/production_candidate.py"
        ],
        "ProductionRequest": [
            "backend/agent_runtime/contracts/production/production_request.py"
        ],
        "ReviewRequest": ["backend/agent_runtime/contracts/review/review_request.py"],
        "ReviewResult": ["backend/agent_runtime/contracts/review/review_result.py"],
        "StepSpec": ["backend/agent_runtime/contracts/planning/step_spec.py"],
        "ToolCallRequest": [
            "backend/agent_runtime/contracts/tools/tool_call_request.py"
        ],
        "ToolCallResult": ["backend/agent_runtime/contracts/tools/tool_call_result.py"],
        "UseCaseRequest": [
            "backend/agent_runtime/contracts/application/use_case_request.py"
        ],
        "UseCaseResult": [
            "backend/agent_runtime/contracts/application/use_case_result.py"
        ],
        "WorkflowEvent": ["backend/agent_runtime/contracts/events/workflow_event.py"],
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


def test_agent_runtime_does_not_define_adapter_or_concrete_binding_logic() -> None:
    forbidden_fragments = (
        "Handler",
        "Provider",
        "Repository",
    )
    definitions = [
        f"{path.relative_to(ROOT).as_posix()}: {node.name}"
        for path in _python_files(AGENT_RUNTIME)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and any(fragment in node.name for fragment in forbidden_fragments)
    ]

    assert definitions == []


def test_invocation_and_errors_do_not_import_private_planning_symbols() -> None:
    checked_roots = (
        ROOT / "backend" / "agent_runtime" / "contracts" / "invocation",
        ROOT / "backend" / "agent_runtime" / "contracts" / "errors",
    )
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {alias.name}"
        for root in checked_roots
        for path in _python_files(root)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("backend.agent_runtime.contracts.planning")
        for alias in node.names
        if alias.name.startswith("_")
    ]

    assert violations == []


def test_specialized_application_and_tool_contracts_have_no_active_dependencies() -> None:
    checked_roots = (
        AGENT_RUNTIME_CONTRACTS / "application",
        AGENT_RUNTIME_CONTRACTS / "tools",
        AGENT_RUNTIME_CONTRACTS / "gates",
    )
    forbidden_fragments = (
        ".handlers",
        ".repositories",
        ".repository",
        ".orm",
        ".sql",
        ".providers",
        ".adapters",
        ".infrastructure",
        ".modules",
    )
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for root in checked_roots
        for path in _python_files(root)
        for module in _imported_modules(path)
        if any(fragment in module.casefold() for fragment in forbidden_fragments)
    ]

    assert violations == []


def test_contract_ref_has_one_agent_runtime_definition() -> None:
    definitions = [
        path.relative_to(ROOT).as_posix()
        for path in _python_files(AGENT_RUNTIME_CONTRACTS)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.TypeAlias)
        and isinstance(node.name, ast.Name)
        and node.name.id == "ContractRef"
    ]

    assert definitions == ["backend/agent_runtime/contracts/common/references.py"]
