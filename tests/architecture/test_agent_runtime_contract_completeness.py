from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "backend" / "agent_runtime" / "contracts"

CONTRACT_MATRIX = {
    "C-01": {"AgentInvocation": "invocation/agent_invocation.py"},
    "C-02": {"AgentResult": "invocation/agent_result.py"},
    "C-03": {"DelegationEnvelope": "planning/delegation.py"},
    "C-04": {"DelegationResult": "delegation/delegation_result.py"},
    "C-05": {"EvidenceRequest": "evidence/evidence_request.py"},
    "C-06": {
        "EvidenceSet": "evidence/evidence_set.py",
        "EvidenceItem": "evidence/evidence_item.py",
    },
    "C-07": {"ProductionRequest": "production/production_request.py"},
    "C-08": {"ProductionCandidate": "production/production_candidate.py"},
    "C-09": {"ReviewRequest": "review/review_request.py"},
    "C-10": {
        "ReviewResult": "review/review_result.py",
        "Finding": "review/finding.py",
    },
    "C-11": {"CorrectionRequest": "review/correction_request.py"},
    "C-12": {"UseCaseRequest": "application/use_case_request.py"},
    "C-13": {"UseCaseResult": "application/use_case_result.py"},
    "C-14": {"ToolCallRequest": "tools/tool_call_request.py"},
    "C-15": {"ToolCallResult": "tools/tool_call_result.py"},
    "C-16": {"GateRequest": "gates/gate_request.py"},
    "C-17": {"GateDecision": "gates/gate_decision.py"},
    "C-18": {"WorkflowEvent": "events/workflow_event.py"},
    "C-19": {"ErrorEnvelope": "errors/error_envelope.py"},
}

VOCABULARY_MATRIX = {
    "AgentResultStatus": "invocation/agent_result.py",
    "FindingSeverity": "review/vocabulary.py",
    "GateDecisionValue": "gates/gate_decision.py",
    "GateStatus": "gates/gate_request.py",
    "InvocationStatus": "invocation/agent_invocation.py",
    "OverallAssessment": "review/vocabulary.py",
    "ProductionValidationState": "production/production_candidate.py",
    "ReviewDimension": "review/vocabulary.py",
    "ReviewStatus": "review/review_result.py",
    "WorkflowEventType": "events/workflow_event.py",
    "WorkflowStatus": "events/workflow_event.py",
}

METADATA_CLASSIFICATION = {
    "C-01": "DIRECT_META",
    "C-02": "DIRECT_META",
    "C-03": "NESTED_VALUE",
    "C-04": "COMPOSED_META",
    "C-05": "DIRECT_META",
    "C-06": "DIRECT_META",
    "C-07": "DIRECT_META",
    "C-08": "DIRECT_META",
    "C-09": "DIRECT_META",
    "C-10": "DIRECT_META",
    "C-11": "DIRECT_META",
    "C-12": "DIRECT_META",
    "C-13": "DIRECT_META",
    "C-14": "DIRECT_META",
    "C-15": "DIRECT_META",
    "C-16": "DIRECT_META",
    "C-17": "DIRECT_META",
    "C-18": "DIRECT_META",
    "C-19": "NESTED_VALUE",
}


def _python_files() -> list[Path]:
    return sorted(CONTRACTS.rglob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _class_definitions(class_name: str) -> list[tuple[str, ast.ClassDef]]:
    return [
        (path.relative_to(CONTRACTS).as_posix(), node)
        for path in _python_files()
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]


def _enum_values(class_node: ast.ClassDef) -> set[str]:
    return {
        node.value.value
        for node in class_node.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def test_c01_c19_matrix_is_complete_unique_and_canonically_placed() -> None:
    assert set(CONTRACT_MATRIX) == {f"C-{index:02d}" for index in range(1, 20)}
    for family in CONTRACT_MATRIX.values():
        for class_name, expected_path in family.items():
            definitions = _class_definitions(class_name)
            assert [path for path, _ in definitions] == [expected_path]

    assert _class_definitions("DelegationRequest") == []


def test_principal_runtime_vocabularies_have_one_definition() -> None:
    for class_name, expected_path in VOCABULARY_MATRIX.items():
        definitions = _class_definitions(class_name)
        assert [path for path, _ in definitions] == [expected_path]


def test_correction_result_has_one_complementary_definition() -> None:
    definitions = _class_definitions("CorrectionResult")
    assert [path for path, _ in definitions] == ["review/correction_result.py"]


def test_agent_runtime_contract_imports_stay_provider_neutral() -> None:
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.providers",
    )
    violations: list[str] = []
    for path in _python_files():
        for node in ast.walk(_tree(path)):
            module_names: list[str] = []
            if isinstance(node, ast.Import):
                module_names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                module_names = [node.module]
            violations.extend(
                f"{path.relative_to(CONTRACTS).as_posix()}: {module}"
                for module in module_names
                if module.startswith(forbidden_prefixes)
                or ".provider" in module.casefold()
            )

    assert violations == []


def test_metadata_classification_covers_every_canonical_family() -> None:
    assert set(METADATA_CLASSIFICATION) == set(CONTRACT_MATRIX)
    assert set(METADATA_CLASSIFICATION.values()) == {
        "DIRECT_META",
        "COMPOSED_META",
        "NESTED_VALUE",
    }

    direct_classes = {
        next(iter(CONTRACT_MATRIX[family]))
        for family, classification in METADATA_CLASSIFICATION.items()
        if classification == "DIRECT_META"
    }
    for class_name in direct_classes:
        _, class_node = _class_definitions(class_name)[0]
        fields = {
            node.target.id
            for node in class_node.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        assert "meta" in fields

    assert "agent_result" in {
        node.target.id
        for node in _class_definitions("DelegationResult")[0][1].body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }


def test_status_vocabulary_cannot_grant_agentic_validation_or_promotion() -> None:
    forbidden_promotion_values = {"promoted", "superseded", "validated"}
    enum_violations: list[str] = []
    for class_name in VOCABULARY_MATRIX:
        path, class_node = _class_definitions(class_name)[0]
        values = _enum_values(class_node)
        forbidden = values.intersection(forbidden_promotion_values)
        if forbidden:
            enum_violations.append(f"{path}: {class_name}: {sorted(forbidden)}")
    assert enum_violations == []

    production_enum = _class_definitions("ProductionValidationState")[0][1]
    assert _enum_values(production_enum) == {"candidate"}

    review_result = _class_definitions("ReviewResult")[0][1]
    review_fields = {
        node.target.id
        for node in review_result.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert review_fields.isdisjoint({"promoted", "validated"})


def test_gate_decision_ast_keeps_ag01_authorship_guard() -> None:
    _, gate_decision = _class_definitions("GateDecision")[0]
    post_init = next(
        node
        for node in gate_decision.body
        if isinstance(node, ast.FunctionDef) and node.name == "__post_init__"
    )
    attributes = {
        node.attr for node in ast.walk(post_init) if isinstance(node, ast.Attribute)
    }
    assert "AG_01" in attributes
    assert any(isinstance(node, ast.Raise) for node in ast.walk(post_init))


def test_status_and_versioning_documents_cover_the_canonical_matrix() -> None:
    status_doc = (
        ROOT / "docs" / "development" / "AGENT_RUNTIME_STATUS_MAPPING.md"
    ).read_text(encoding="utf-8")
    versioning_doc = (
        ROOT / "docs" / "development" / "AGENT_RUNTIME_VERSIONING_INVENTORY.md"
    ).read_text(encoding="utf-8")

    for status in (
        "waiting_gate",
        "replanning",
        "candidate",
        "completed",
        "incomplete",
        "expired",
        "OutcomeStatus",
    ):
        assert f"`{status}`" in status_doc
    for family in CONTRACT_MATRIX:
        assert f"| {family} |" in versioning_doc
