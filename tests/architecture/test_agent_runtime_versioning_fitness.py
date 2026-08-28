from __future__ import annotations

import ast
from pathlib import Path
from typing import get_type_hints

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ContractMeta,
    ContractSchemaVersion,
    DelegationEnvelope,
    ErrorEnvelope,
)
from backend.agent_runtime.versioning import (
    BASELINE_POLICY,
    CONTRACT_VERSION_DESCRIPTORS,
    ContractFamily,
    MetadataMode,
    SupplementalContractKind,
    SupportedVersionRange,
)

ROOT = Path(__file__).resolve().parents[2]
VERSIONING = ROOT / "backend" / "agent_runtime" / "versioning"

EXPECTED_METADATA_MODES = {
    **{family: MetadataMode.DIRECT_META for family in ContractFamily},
    ContractFamily.C03: MetadataMode.NESTED_VALUE,
    ContractFamily.C04: MetadataMode.COMPOSED_META,
    ContractFamily.C19: MetadataMode.NESTED_VALUE,
}

EXPECTED_CONTRACT_TYPES = {
    ContractFamily.C01: "AgentInvocation",
    ContractFamily.C02: "AgentResult",
    ContractFamily.C03: "DelegationEnvelope",
    ContractFamily.C04: "DelegationResult",
    ContractFamily.C05: "EvidenceRequest",
    ContractFamily.C06: "EvidenceSet",
    ContractFamily.C07: "ProductionRequest",
    ContractFamily.C08: "ProductionCandidate",
    ContractFamily.C09: "ReviewRequest",
    ContractFamily.C10: "ReviewResult",
    ContractFamily.C11: "CorrectionRequest",
    ContractFamily.C12: "UseCaseRequest",
    ContractFamily.C13: "UseCaseResult",
    ContractFamily.C14: "ToolCallRequest",
    ContractFamily.C15: "ToolCallResult",
    ContractFamily.C16: "GateRequest",
    ContractFamily.C17: "GateDecision",
    ContractFamily.C18: "WorkflowEvent",
    ContractFamily.C19: "ErrorEnvelope",
}


def _python_files(path: Path) -> list[Path]:
    return sorted(path.rglob("*.py"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_contract_meta_schema_version_has_canonical_type() -> None:
    assert get_type_hints(ContractMeta)["schema_version"] is ContractSchemaVersion


def test_legacy_phase_labels_are_absent_from_schema_versions() -> None:
    forbidden_assignment = "schema_version=" + '"12.3-C'
    violations = [
        path.relative_to(ROOT).as_posix()
        for root in (ROOT / "backend", ROOT / "tests")
        for path in _python_files(root)
        if forbidden_assignment in path.read_text(encoding="utf-8")
    ]

    assert violations == []


def test_contract_family_and_descriptor_matrix_are_exact() -> None:
    expected_families = {f"C-{index:02d}" for index in range(1, 20)}
    family_descriptors = {
        key: descriptor
        for key, descriptor in CONTRACT_VERSION_DESCRIPTORS.items()
        if isinstance(key, ContractFamily)
    }

    assert {family.value for family in ContractFamily} == expected_families
    assert len(ContractFamily) == 19
    assert set(family_descriptors) == set(ContractFamily)
    assert len(family_descriptors) == 19
    assert {
        family: descriptor.contract_type.__name__
        for family, descriptor in family_descriptors.items()
    } == EXPECTED_CONTRACT_TYPES
    assert "C-20" not in {family.value for family in ContractFamily}


def test_supplemental_contract_kind_and_descriptor_are_exact() -> None:
    key = SupplementalContractKind.CORRECTION_RESULT

    assert list(SupplementalContractKind) == [key]
    assert len(CONTRACT_VERSION_DESCRIPTORS) == 20
    assert len(set(CONTRACT_VERSION_DESCRIPTORS)) == 20
    assert all(
        descriptor.key is descriptor_key
        for descriptor_key, descriptor in CONTRACT_VERSION_DESCRIPTORS.items()
    )
    assert CONTRACT_VERSION_DESCRIPTORS[key].contract_type.__name__ == "CorrectionResult"
    assert CONTRACT_VERSION_DESCRIPTORS[key].metadata_mode is MetadataMode.DIRECT_META


def test_descriptor_metadata_modes_match_c3_inventory() -> None:
    assert {
        family: descriptor.metadata_mode
        for family, descriptor in CONTRACT_VERSION_DESCRIPTORS.items()
        if isinstance(family, ContractFamily)
    } == EXPECTED_METADATA_MODES


def test_every_descriptor_uses_baseline_version_1_0() -> None:
    assert str(AGENT_CONTRACT_SCHEMA_V1_0) == "1.0"
    assert {
        descriptor.current_version for descriptor in CONTRACT_VERSION_DESCRIPTORS.values()
    } == {AGENT_CONTRACT_SCHEMA_V1_0}
    assert all(descriptor.version_path for descriptor in CONTRACT_VERSION_DESCRIPTORS.values())


def test_baseline_policy_covers_exactly_all_versioned_contract_keys() -> None:
    expected_range = (SupportedVersionRange(major=1, min_minor=0, max_minor=0),)

    assert set(BASELINE_POLICY.ranges_by_key) == set(CONTRACT_VERSION_DESCRIPTORS)
    assert len(BASELINE_POLICY.ranges_by_key) == 20
    assert all(
        BASELINE_POLICY.supported_ranges(key) == expected_range
        for key in CONTRACT_VERSION_DESCRIPTORS
    )


def test_versioning_imports_respect_runtime_boundaries() -> None:
    forbidden_prefixes = (
        "backend.adapters",
        "backend.infrastructure",
        "backend.modules",
        "backend.providers",
    )
    violations = [
        f"{path.relative_to(ROOT).as_posix()}: {module}"
        for path in _python_files(VERSIONING)
        for module in _imports(path)
        if module.startswith(forbidden_prefixes)
        or ".provider" in module.casefold()
        or module.casefold().startswith(("pydantic", "sqlalchemy"))
    ]

    assert violations == []


def test_nested_contracts_do_not_duplicate_contract_meta() -> None:
    assert "meta" not in get_type_hints(DelegationEnvelope)
    assert "meta" not in get_type_hints(ErrorEnvelope)


def test_runtime_dependencies_allow_only_the_calibrated_openai_sdk() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'dependencies = ["openai>=3.5,<4"]' in pyproject
