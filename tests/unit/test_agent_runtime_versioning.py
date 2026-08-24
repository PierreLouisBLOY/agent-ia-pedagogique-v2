from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    AgentResult,
    AgentResultStatus,
    ContractMeta,
    ContractSchemaVersion,
    CorrectionRequest,
    CorrectionResult,
    DelegationEnvelope,
    DelegationResult,
    EffectState,
    ErrorCategory,
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    ExecutorKind,
    ExecutorRef,
    InvocationStatus,
    PermissionScope,
    RecommendedAction,
    StepKind,
    StepSpec,
)
from backend.agent_runtime.versioning import (
    BASELINE_MIGRATION_CATALOG,
    BASELINE_POLICY,
    ContractChangeKind,
    ContractFamily,
    ContractMigrationUnavailable,
    DuplicateContractMigration,
    MigrationCatalog,
    NestedContractVersionContextRequired,
    SupplementalContractKind,
    SupportedVersionRange,
    UnsupportedContractVersion,
    VersionBump,
    VersionedContractKey,
    contract_schema_version,
    ensure_contract_version_supported,
    ensure_nested_contract_version_supported,
    is_valid_version_transition,
    required_bump,
)
from backend.core_contracts.capability import CapabilityId
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.identifiers import TypedEntityId
from backend.shared_kernel.references import ObjectVersionRef, TypedEntityRef, VersionRef
from backend.shared_kernel.time import Instant

NOW = Instant(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))


def _meta[TStatus](
    status: TStatus,
    version: ContractSchemaVersion = AGENT_CONTRACT_SCHEMA_V1_0,
) -> ContractMeta[TStatus]:
    return ContractMeta(
        schema_version=version,
        run_id="run-1",
        step_id="step-1",
        parent_step_id=None,
        correlation_id=CorrelationId("corr-1"),
        created_at=NOW,
        actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
        status=status,
    )


def _agent_result(
    version: ContractSchemaVersion = AGENT_CONTRACT_SCHEMA_V1_0,
) -> AgentResult[object]:
    return AgentResult(
        meta=_meta(AgentResultStatus.SUCCEEDED, version),
        invocation_id="invocation-1",
        payload={"result": "candidate"},
    )


def _correction_result(
    version: ContractSchemaVersion = AGENT_CONTRACT_SCHEMA_V1_0,
) -> CorrectionResult:
    production = TypedEntityRef(TypedEntityId("production", "production-1"))
    parent = ObjectVersionRef(production, VersionRef("v1"))
    request = CorrectionRequest(
        meta=_meta(InvocationStatus.PLANNED, version),
        target_production_ref=parent,
        review_ref="review-1",
        finding_ids=("finding-1",),
    )
    return CorrectionResult(
        meta=_meta(AgentResultStatus.SUCCEEDED, version),
        request=request,
        new_production_ref=ObjectVersionRef(production, VersionRef("v2")),
        parent_production_ref=parent,
        addressed_findings=request.finding_ids,
        unresolved_findings=(),
        change_summary="Corrected the reviewed finding.",
        lineage={},
    )


def _delegation() -> DelegationEnvelope:
    step = StepSpec(
        step_id="step-1",
        kind=StepKind.AGENT,
        capability_id=CapabilityId("course.generate"),
        executor=ExecutorRef(ExecutorKind.AG_02),
        objective="Generate a candidate",
        output_contract={"type": "candidate"},
    )
    return DelegationEnvelope(
        delegation_id="delegation-1",
        source_step=step,
        target_agent=AgentId.AG_02,
        context_slice={},
        evidence_refs=(),
        constraints={},
        permission_scope=PermissionScope(
            principal=ActorRef(ActorKind.AGENT, AgentId.AG_02.value)
        ),
    )


def _error() -> ErrorEnvelope:
    return ErrorEnvelope(
        error_code="VERSION_CONTEXT",
        category=ErrorCategory.VALIDATION,
        source=ErrorSource.APPLICATION,
        retryable=False,
        severity=ErrorSeverity.ERROR,
        message="Parent context is required",
        step_id="step-1",
        attempt=1,
        effect_state=EffectState.NONE,
        recommended_action=RecommendedAction.STOP,
    )


@pytest.mark.parametrize("rendered", ["1.0", "1.12"])
def test_contract_schema_version_parses_and_renders_canonical_values(rendered: str) -> None:
    version = ContractSchemaVersion.parse(rendered)

    assert str(version) == rendered


@pytest.mark.parametrize(
    "rendered",
    ["0.1", "01.0", "1.00", "1", "1.0.0", "v1.0", "1.-1", " 1.0", "1.0 "],
)
def test_contract_schema_version_rejects_non_canonical_values(rendered: str) -> None:
    with pytest.raises(ValueError):
        ContractSchemaVersion.parse(rendered)


@pytest.mark.parametrize("values", [(True, 0), (1, False)])
def test_contract_schema_version_rejects_boolean_components(values: tuple[object, object]) -> None:
    with pytest.raises(TypeError):
        ContractSchemaVersion(*values)  # type: ignore[arg-type]


@pytest.mark.parametrize("values", [(0, 0), (1, -1)])
def test_contract_schema_version_rejects_out_of_range_components(
    values: tuple[int, int],
) -> None:
    with pytest.raises(ValueError):
        ContractSchemaVersion(*values)


def test_contract_meta_requires_contract_schema_version() -> None:
    with pytest.raises(TypeError):
        ContractMeta(
            schema_version="1.0",  # type: ignore[arg-type]
            run_id="run-1",
            step_id="step-1",
            parent_step_id=None,
            correlation_id=CorrelationId("corr-1"),
            created_at=NOW,
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_02.value),
            status=AgentResultStatus.SUCCEEDED,
        )


def test_supported_version_range_includes_its_boundaries() -> None:
    supported = SupportedVersionRange(major=1, min_minor=2, max_minor=4)

    assert supported.supports(ContractSchemaVersion(1, 2))
    assert supported.supports(ContractSchemaVersion(1, 4))
    assert not supported.supports(ContractSchemaVersion(1, 1))
    assert not supported.supports(ContractSchemaVersion(1, 5))
    assert not supported.supports(ContractSchemaVersion(2, 2))


@pytest.mark.parametrize("field", ["major", "min_minor", "max_minor"])
def test_supported_version_range_rejects_boolean_components(field: str) -> None:
    values: dict[str, object] = {"major": 1, "min_minor": 0, "max_minor": 1}
    values[field] = True
    with pytest.raises(TypeError):
        SupportedVersionRange(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "values",
    [
        {"major": 0, "min_minor": 0, "max_minor": 1},
        {"major": 1, "min_minor": -1, "max_minor": 1},
        {"major": 1, "min_minor": 2, "max_minor": 1},
    ],
)
def test_supported_version_range_rejects_invalid_bounds(values: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        SupportedVersionRange(**values)


def test_baseline_supports_exactly_version_1_0_for_every_family() -> None:
    for family in ContractFamily:
        assert BASELINE_POLICY.is_supported(family, AGENT_CONTRACT_SCHEMA_V1_0)
        assert BASELINE_POLICY.supported_ranges(family) == (
            SupportedVersionRange(major=1, min_minor=0, max_minor=0),
        )


@pytest.mark.parametrize("version", [ContractSchemaVersion(1, 1), ContractSchemaVersion(2, 0), ContractSchemaVersion(9, 9)])
def test_baseline_rejects_unsupported_versions_cleanly(version: ContractSchemaVersion) -> None:
    with pytest.raises(UnsupportedContractVersion) as raised:
        BASELINE_POLICY.ensure_supported(ContractFamily.C01, version)

    assert raised.value.key is ContractFamily.C01
    assert raised.value.version == version
    assert str(raised.value) == f"unsupported version {version} for C-01"


def test_contract_version_extraction_supports_direct_and_composed_metadata() -> None:
    result = _agent_result()
    delegation_result = DelegationResult(
        delegation_id="delegation-1",
        source_agent=AgentId.AG_02,
        agent_result=result,
    )

    assert contract_schema_version(ContractFamily.C02, result) == AGENT_CONTRACT_SCHEMA_V1_0
    assert (
        contract_schema_version(ContractFamily.C04, delegation_result)
        == AGENT_CONTRACT_SCHEMA_V1_0
    )
    ensure_contract_version_supported(ContractFamily.C02, result)
    ensure_contract_version_supported(ContractFamily.C04, delegation_result)


@pytest.mark.parametrize(
    ("family", "contract"),
    [(ContractFamily.C03, _delegation()), (ContractFamily.C19, _error())],
)
def test_nested_contract_version_extraction_requires_parent_context(
    family: ContractFamily,
    contract: object,
) -> None:
    with pytest.raises(NestedContractVersionContextRequired) as raised:
        contract_schema_version(family, contract)

    assert raised.value.key is family


@pytest.mark.parametrize("family", [ContractFamily.C03, ContractFamily.C19])
def test_nested_contract_parent_version_is_checked_explicitly(family: ContractFamily) -> None:
    ensure_nested_contract_version_supported(family, AGENT_CONTRACT_SCHEMA_V1_0)
    with pytest.raises(UnsupportedContractVersion):
        ensure_nested_contract_version_supported(family, ContractSchemaVersion(2, 0))


def test_baseline_supports_correction_result_version_1_0() -> None:
    key = SupplementalContractKind.CORRECTION_RESULT

    assert BASELINE_POLICY.is_supported(key, AGENT_CONTRACT_SCHEMA_V1_0)
    ensure_contract_version_supported(key, _correction_result())


def test_contract_version_extraction_supports_correction_result() -> None:
    assert (
        contract_schema_version(
            SupplementalContractKind.CORRECTION_RESULT,
            _correction_result(),
        )
        == AGENT_CONTRACT_SCHEMA_V1_0
    )


@pytest.mark.parametrize(
    "version",
    [ContractSchemaVersion(1, 1), ContractSchemaVersion(2, 0)],
)
def test_correction_result_rejects_unsupported_versions(
    version: ContractSchemaVersion,
) -> None:
    key = SupplementalContractKind.CORRECTION_RESULT

    with pytest.raises(UnsupportedContractVersion) as raised:
        ensure_contract_version_supported(key, _correction_result(version))

    assert raised.value.key is key
    assert raised.value.version == version


def test_correction_result_versioning_rejects_wrong_contract_type() -> None:
    with pytest.raises(TypeError):
        contract_schema_version(
            SupplementalContractKind.CORRECTION_RESULT,
            _agent_result(),
        )


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (ContractChangeKind.ADDITIVE, VersionBump.MINOR),
        (ContractChangeKind.REMOVAL, VersionBump.MAJOR),
        (ContractChangeKind.RENAME, VersionBump.MAJOR),
        (ContractChangeKind.SEMANTIC_CHANGE, VersionBump.MAJOR),
    ],
)
def test_required_bump_maps_change_kinds(
    kind: ContractChangeKind,
    expected: VersionBump,
) -> None:
    assert required_bump(kind) is expected


@pytest.mark.parametrize(
    ("old", "new", "kind", "expected"),
    [
        (ContractSchemaVersion(1, 0), ContractSchemaVersion(1, 1), ContractChangeKind.ADDITIVE, True),
        (ContractSchemaVersion(1, 1), ContractSchemaVersion(1, 1), ContractChangeKind.ADDITIVE, False),
        (ContractSchemaVersion(1, 0), ContractSchemaVersion(1, 1), ContractChangeKind.REMOVAL, False),
        (ContractSchemaVersion(1, 8), ContractSchemaVersion(2, 0), ContractChangeKind.REMOVAL, True),
        (ContractSchemaVersion(1, 8), ContractSchemaVersion(3, 0), ContractChangeKind.RENAME, True),
        (ContractSchemaVersion(1, 8), ContractSchemaVersion(2, 0), ContractChangeKind.SEMANTIC_CHANGE, True),
    ],
)
def test_version_transition_rules(
    old: ContractSchemaVersion,
    new: ContractSchemaVersion,
    kind: ContractChangeKind,
    expected: bool,
) -> None:
    assert is_valid_version_transition(old, new, kind) is expected


@dataclass(frozen=True, slots=True)
class _FakeAdditiveMigration:
    key: VersionedContractKey = ContractFamily.C01
    from_version: ContractSchemaVersion = ContractSchemaVersion(1, 0)
    to_version: ContractSchemaVersion = ContractSchemaVersion(1, 1)

    def migrate(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        return {**payload, "migrated_for": self.key.value}


def test_explicit_fake_migration_is_applied_and_frozen() -> None:
    catalog = MigrationCatalog((_FakeAdditiveMigration(),))

    migrated = catalog.migrate(
        ContractFamily.C01,
        ContractSchemaVersion(1, 0),
        ContractSchemaVersion(1, 1),
        {"nested": {"value": 1}},
    )

    assert migrated["migrated_for"] == "C-01"
    nested = migrated["nested"]
    assert isinstance(nested, Mapping)
    with pytest.raises(TypeError):
        nested["value"] = 2  # type: ignore[index]


def test_absent_migration_is_rejected_and_baseline_catalog_is_empty() -> None:
    assert BASELINE_MIGRATION_CATALOG.registered_edges == ()
    with pytest.raises(ContractMigrationUnavailable):
        BASELINE_MIGRATION_CATALOG.migrate(
            ContractFamily.C01,
            ContractSchemaVersion(1, 0),
            ContractSchemaVersion(1, 1),
            {},
        )


def test_duplicate_migration_edge_is_rejected() -> None:
    migration = _FakeAdditiveMigration()

    with pytest.raises(DuplicateContractMigration):
        MigrationCatalog((migration, migration))


def test_explicit_correction_result_migration_is_supported() -> None:
    key = SupplementalContractKind.CORRECTION_RESULT
    catalog = MigrationCatalog((_FakeAdditiveMigration(key=key),))

    migrated = catalog.migrate(
        key,
        ContractSchemaVersion(1, 0),
        ContractSchemaVersion(1, 1),
        {"change_summary": "Corrected"},
    )

    assert migrated["migrated_for"] == "CorrectionResult"


def test_correction_result_migration_edge_does_not_collide_with_c11() -> None:
    migrations = (
        _FakeAdditiveMigration(key=ContractFamily.C11),
        _FakeAdditiveMigration(key=SupplementalContractKind.CORRECTION_RESULT),
    )
    catalog = MigrationCatalog(migrations)

    assert len(catalog.registered_edges) == 2
