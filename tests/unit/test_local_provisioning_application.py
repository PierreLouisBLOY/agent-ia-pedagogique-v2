from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from backend.modules.local_provisioning.application.contracts import (
    MigrationExpectation,
    OwnerApprovals,
    ProvisioningInspectionRequest,
    ProvisioningPlan,
    ProvisioningTargetInspectionRequest,
    ProvisioningTargetInspectionResult,
    RuntimeMigrationState,
    SeedCandidate,
    SeedExpectation,
    SeedInspection,
    SuppliedSeedFileInspectionRequest,
)
from backend.modules.local_provisioning.application.use_cases import (
    ApplyLocalProvisioning,
    InspectLocalProvisioning,
    InspectProvisioningTarget,
    InspectSuppliedSeedFile,
)

SEED_SHA = "9d64d15e9c246924edeff16e7bbb5fb7a53791fc2ddf217541824771b34053e1"
SEED_SIZE = 227_557_376
OLD_SEED_SHA = "38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134"
MIGRATIONS = (
    MigrationExpectation(
        "001", "5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102", Path("001.sql")
    ),
    MigrationExpectation(
        "002", "e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893", Path("002.sql")
    ),
)
APPROVALS = OwnerApprovals(
    True,
    True,
    True,
    True,
    True,
    True,
    True,
    "0abe109eab2f0f1c49c4ac484ffd596d63b5964c34a66e19a789f880145d2287",
)


class Gateway:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.candidate = SeedCandidate(root / "source.sqlite", SEED_SHA, SEED_SIZE)
        self.seed = SeedInspection(self.candidate, True, "ok", "ok", 0, 121, 23, 7, 11)
        self.calls: list[str] = []
        self.state_calls = 0
        self.config = None

    def discover_seed_candidates(self, roots, expectations):
        self.calls.append("discover")
        return (self.candidate,)

    def inspect_target(self, data_root, project_identity):
        self.calls.append("inspect_target")
        return ProvisioningTargetInspectionResult(False, False, (), (), ())

    def authenticate_seed(self, candidate, expectation):
        self.calls.append("authenticate")
        return replace(self.seed, candidate=candidate)

    def validate_migration_sources(self, migrations):
        self.calls.append("validate_migrations")
        return True

    def inspect_runtime(self, path, migrations):
        self.calls.append("inspect_runtime")
        self.state_calls += 1
        if self.state_calls == 1:
            return RuntimeMigrationState(False, None, None, (), None, None, None)
        if self.state_calls == 2:
            return RuntimeMigrationState(True, "a" * 64, SEED_SHA, (), "ok", "ok", 0)
        return RuntimeMigrationState(
            True,
            "a" * 64,
            SEED_SHA,
            (("001", MIGRATIONS[0].sha256), ("002", MIGRATIONS[1].sha256)),
            "ok",
            "ok",
            0,
        )

    def create_data_root(self, path):
        self.calls.append("create_root")
        return True

    def copy_reference_seed(self, source, target, expected_sha256):
        self.calls.append("copy_seed")
        return expected_sha256

    def create_runtime_from_reference(self, reference, runtime, expected_sha256):
        self.calls.append("copy_runtime")
        return expected_sha256

    def create_backup(self, runtime, backup, reference, migration_version):
        self.calls.append("backup")
        assert migration_version == "000"
        return "b" * 64

    def inspect_backup(self, backup, migrations, expected_migration_version):
        self.calls.append("inspect_backup")
        assert expected_migration_version == "000"
        return "c" * 64

    def apply_migrations(self, runtime, migrations):
        self.calls.append("migrate")
        return tuple(item.version for item in migrations)

    def create_library_root(self, path):
        self.calls.append("library")
        return True

    def read_user_config(self, names):
        self.calls.append("read_config")
        if self.config is None:
            return tuple((name, None) for name in names)
        return self.config

    def write_user_config(self, values):
        self.calls.append("write_config")
        self.config = values

    def startup_probe(self, plan):
        self.calls.append("startup")
        return True

    def snapshot_old_root(self, path):
        self.calls.append("snapshot_old_root")
        return "unchanged"


def test_inspection_authenticates_only_known_hash_candidates(tmp_path):
    gateway = Gateway(tmp_path)
    request = ProvisioningInspectionRequest(
        "agent-ia-pedagogique-v2",
        (tmp_path,),
        (SeedExpectation(SEED_SHA, SEED_SIZE),),
        tmp_path / "old",
        (),
    )

    result = InspectLocalProvisioning(gateway).execute(request)

    assert result.seed_candidates == (gateway.seed,)
    assert result.findings == ()
    assert gateway.calls == ["discover", "authenticate", "read_config"]


def test_inspection_rejects_mutating_request_before_gateway(tmp_path):
    gateway = Gateway(tmp_path)
    request = ProvisioningInspectionRequest(
        "project",
        (tmp_path,),
        (SeedExpectation(SEED_SHA, SEED_SIZE),),
        tmp_path / "old",
        (),
        read_only=False,
    )

    with pytest.raises(ValueError, match="READ_ONLY_INSPECTION_REQUIRED"):
        InspectLocalProvisioning(gateway).execute(request)
    assert gateway.calls == []


def test_target_inspection_is_read_only_and_rejects_unexpected_entries(tmp_path):
    gateway = Gateway(tmp_path)

    class TargetGateway(Gateway):
        def inspect_target(self, data_root, project_identity):
            self.calls.append("inspect_target")
            return ProvisioningTargetInspectionResult(
                True, True, (".r5-root.json", "unexpected.sqlite"), (), ()
            )

    gateway = TargetGateway(tmp_path)
    result = InspectProvisioningTarget(gateway).execute(
        ProvisioningTargetInspectionRequest(
            "agent-ia-pedagogique-v2", tmp_path / "new", tmp_path / "old"
        )
    )

    assert result.findings == ("EXISTING_DATA_ROOT_HAS_UNEXPECTED_ENTRIES",)
    assert result.unexpected_relative_paths == ("unexpected.sqlite",)
    assert gateway.calls == ["inspect_target"]


def test_target_inspection_rejects_mutating_request_before_gateway(tmp_path):
    gateway = Gateway(tmp_path)
    request = ProvisioningTargetInspectionRequest(
        "agent-ia-pedagogique-v2", tmp_path / "new", tmp_path / "old", read_only=False
    )

    with pytest.raises(ValueError, match="READ_ONLY_TARGET_INSPECTION_REQUIRED"):
        InspectProvisioningTarget(gateway).execute(request)
    assert gateway.calls == []


def test_real_benchmark_identity_pins_follow_cp645_without_importing_live_gates():
    from backend.adapters.outbound.persistence import migrations

    root = Path(__file__).resolve().parents[2]
    for name in (
        "test_retrieval_quality_real_gate.py",
        "test_semantic_retrieval_offline_r1_gate.py",
        "test_semantic_retrieval_live_gate.py",
    ):
        tree = ast.parse((root / "tests" / "non_functional" / name).read_text("utf-8"))
        pins = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"EXPECTED_SEED_SIZE", "EXPECTED_SEED_SHA256"}
        }
        assert pins == {
            "EXPECTED_SEED_SIZE": migrations.CANONICAL_SEED_SIZE,
            "EXPECTED_SEED_SHA256": migrations.CANONICAL_SEED_SHA256,
        }


def test_supplied_file_measurement_reports_exact_hash_without_authentication(tmp_path):
    candidate = SeedCandidate(tmp_path / "supplied.sqlite", "a" * 64, 123)

    class MeasurementGateway:
        calls = 0

        def measure_seed_file(self, path, allowed_root):
            self.calls += 1
            return candidate

    gateway = MeasurementGateway()
    request = SuppliedSeedFileInspectionRequest(
        "agent-ia-pedagogique-v2",
        tmp_path,
        candidate.path,
        SeedExpectation("a" * 64, 123),
    )

    result = InspectSuppliedSeedFile(gateway).execute(request)

    assert result.candidate == candidate
    assert result.matches_expected is True
    assert result.database_opened is False
    assert result.findings == ()
    assert gateway.calls == 1


def test_supplied_file_hash_mismatch_stays_read_only_and_is_reported(tmp_path):
    candidate = SeedCandidate(tmp_path / "supplied.sqlite", "b" * 64, 456)

    class MeasurementGateway:
        def measure_seed_file(self, path, allowed_root):
            return candidate

    request = SuppliedSeedFileInspectionRequest(
        "agent-ia-pedagogique-v2",
        tmp_path,
        candidate.path,
        SeedExpectation("a" * 64, 123),
    )

    result = InspectSuppliedSeedFile(MeasurementGateway()).execute(request)

    assert result.matches_expected is False
    assert result.findings == ("SUPPLIED_SEED_HASH_OR_SIZE_MISMATCH",)
    assert result.database_opened is False


def test_supplied_file_outside_owner_locator_is_rejected_before_measurement(tmp_path):
    class MeasurementGateway:
        def measure_seed_file(self, path, allowed_root):
            raise AssertionError("measurement must not run")

    request = SuppliedSeedFileInspectionRequest(
        "agent-ia-pedagogique-v2",
        tmp_path / "allowed",
        tmp_path / "outside" / "seed.sqlite",
        SeedExpectation("a" * 64, 123),
    )

    with pytest.raises(ValueError, match="SUPPLIED_SEED_OUTSIDE_OWNER_LOCATOR"):
        InspectSuppliedSeedFile(MeasurementGateway()).execute(request)


def _plan(tmp_path: Path, approvals: OwnerApprovals = APPROVALS) -> ProvisioningPlan:
    seed = SeedInspection(
        SeedCandidate(tmp_path / "source.sqlite", SEED_SHA, SEED_SIZE),
        True,
        "ok",
        "ok",
        0,
        121,
        23,
        7,
        11,
    )
    root = tmp_path / "new-v2-root"
    return ProvisioningPlan(
        "agent-ia-pedagogique-v2",
        seed,
        root,
        root / "reference" / "seed.sqlite",
        root / "runtime" / "runtime.sqlite",
        root / "backup" / "initial.sqlite",
        root / "library",
        MIGRATIONS,
        (tmp_path,),
        tmp_path / "old-v2-root",
        "HKCU\\Environment",
        (
            ("PROJET_V2_DATA_DIR", str(root)),
            ("PROJET_V2_CANONICAL_DB", str(root / "reference" / "seed.sqlite")),
            ("PROJET_V2_RUNTIME_DB", str(root / "runtime" / "runtime.sqlite")),
        ),
        "0123456789abcdef0123456789abcdef",
        approvals,
    )


def test_apply_refuses_missing_owner_approval_before_side_effect(tmp_path):
    gateway = Gateway(tmp_path)
    approvals = OwnerApprovals(
        True,
        True,
        True,
        True,
        True,
        True,
        False,
        "0abe109eab2f0f1c49c4ac484ffd596d63b5964c34a66e19a789f880145d2287",
    )

    with pytest.raises(ValueError, match="OWNER_APPROVALS_NOT_ALL_TRUE"):
        ApplyLocalProvisioning(gateway).execute(_plan(tmp_path, approvals))
    assert gateway.calls == []


def test_apply_orders_backup_before_migrations_and_probes_startup_last(tmp_path):
    gateway = Gateway(tmp_path)

    result = ApplyLocalProvisioning(gateway).execute(_plan(tmp_path))

    assert result.seed_sha256 == SEED_SHA
    assert result.migrations_applied == ("001", "002")
    assert gateway.calls.index("backup") < gateway.calls.index("migrate")
    assert (
        gateway.calls.index("migrate")
        < gateway.calls.index("library")
        < gateway.calls.index("write_config")
    )
    assert gateway.calls.index("startup") > gateway.calls.index("write_config")
    assert gateway.calls[-1] == "read_config"


def test_apply_replay_verifies_pre_migration_backup_instead_of_using_runtime_hash(tmp_path):
    gateway = Gateway(tmp_path)
    gateway.inspect_runtime = lambda path, migrations: RuntimeMigrationState(
        True,
        "a" * 64,
        SEED_SHA,
        tuple((item.version, item.sha256) for item in MIGRATIONS),
        "ok",
        "ok",
        0,
    )

    result = ApplyLocalProvisioning(gateway).execute(_plan(tmp_path))

    assert result.backup_sha256 == "c" * 64
    assert "inspect_backup" in gateway.calls
    assert "backup" not in gateway.calls


def test_apply_rejects_unapproved_migration_digest_before_side_effect(tmp_path):
    gateway = Gateway(tmp_path)
    plan = _plan(tmp_path)
    invalid = (MigrationExpectation("001", "0" * 64, Path("001.sql")), MIGRATIONS[1])

    with pytest.raises(ValueError, match="MIGRATION_HASH_MISMATCH"):
        ApplyLocalProvisioning(gateway).execute(replace(plan, migrations=invalid))
    assert gateway.calls == []


def test_inspection_flags_two_authenticated_seed_candidates(tmp_path):
    gateway = Gateway(tmp_path)
    second = SeedCandidate(tmp_path / "second.sqlite", SEED_SHA, SEED_SIZE)
    gateway.discover_seed_candidates = lambda roots, expectations: (gateway.candidate, second)
    request = ProvisioningInspectionRequest(
        "agent-ia-pedagogique-v2",
        (tmp_path,),
        (SeedExpectation(SEED_SHA, SEED_SIZE),),
        tmp_path / "old",
        (),
    )

    result = InspectLocalProvisioning(gateway).execute(request)

    assert len(result.seed_candidates) == 2
    assert result.findings == ("AUTHENTICATED_SEED_AMBIGUOUS",)


def test_apply_rejects_root_collision_with_old_root_before_side_effect(tmp_path):
    gateway = Gateway(tmp_path)
    plan = _plan(tmp_path)
    unsafe = replace(plan, data_root=plan.old_data_root / "new")

    with pytest.raises(ValueError, match="NEW_DATA_ROOT_MUST_BE_DISTINCT_FROM_OLD_ROOT"):
        ApplyLocalProvisioning(gateway).execute(unsafe)
    assert gateway.calls == []


def test_apply_stops_before_migration_when_backup_is_not_verified(tmp_path):
    gateway = Gateway(tmp_path)
    gateway.create_backup = lambda *args: "NOT_A_SHA256"

    with pytest.raises(ValueError, match="BACKUP_NOT_VERIFIED"):
        ApplyLocalProvisioning(gateway).execute(_plan(tmp_path))
    assert "migrate" not in gateway.calls


def test_startup_failure_restores_previous_user_configuration(tmp_path):
    gateway = Gateway(tmp_path)
    gateway.startup_probe = lambda plan: False

    with pytest.raises(ValueError, match="NORMAL_STARTUP_PROBE_FAILED_CONFIG_RESTORED"):
        ApplyLocalProvisioning(gateway).execute(_plan(tmp_path))
    assert gateway.calls[-1] == "write_config"


@pytest.mark.parametrize("name", ["PROJET_V2_CANONICAL_DB", "PROJET_V2_RUNTIME_DB"])
def test_configuration_database_must_match_plan_before_any_effect(tmp_path, name):
    plan = _plan(tmp_path)
    bad = replace(
        plan,
        config_values=tuple(
            (key, str(plan.old_data_root / "outside.sqlite") if key == name else value)
            for key, value in plan.config_values
        ),
    )
    gateway = Gateway(tmp_path)
    with pytest.raises(ValueError, match="CONFIG_DATABASE_BINDING_MISMATCH"):
        ApplyLocalProvisioning(gateway).execute(bad)
    assert gateway.calls == []


def test_configuration_duplicate_key_refused_before_any_effect(tmp_path):
    plan = _plan(tmp_path)
    bad = replace(plan, config_values=plan.config_values + (plan.config_values[-1],))
    gateway = Gateway(tmp_path)
    with pytest.raises(ValueError, match="CONFIG_TARGET_INVALID"):
        ApplyLocalProvisioning(gateway).execute(bad)
    assert gateway.calls == []


def test_configuration_exact_complete_binding_positive(tmp_path):
    plan = _plan(tmp_path)
    result = ApplyLocalProvisioning(Gateway(tmp_path)).execute(plan)
    assert result.startup_ready
    assert dict(result.config_after) == dict(plan.config_values)
