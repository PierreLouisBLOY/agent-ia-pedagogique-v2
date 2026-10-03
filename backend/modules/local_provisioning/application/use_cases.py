from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.modules.local_provisioning.application.contracts import (
    ProvisioningApplyResult,
    ProvisioningInspectionRequest,
    ProvisioningInspectionResult,
    ProvisioningPlan,
    ProvisioningTargetInspectionRequest,
    ProvisioningTargetInspectionResult,
    SeedExpectation,
    SeedInspection,
    SuppliedSeedFileInspectionRequest,
    SuppliedSeedFileInspectionResult,
)
from backend.modules.local_provisioning.ports.outbound import (
    LocalProvisioningGateway,
    ProvisioningTargetInspectionGateway,
    SuppliedSeedFileGateway,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MIGRATIONS = {
    "001": "5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102",
    "002": "e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893",
}
_OWNER_CONFIG = (
    "PROJET_V2_DATA_DIR",
    "PROJET_V2_CANONICAL_DB",
    "PROJET_V2_RUNTIME_DB",
)
_KNOWN_TARGET_PATHS = frozenset(
    {
        ".r5-root.json",
        "reference",
        "reference/base_pedagogique_v2.sqlite",
        "runtime",
        "runtime/base_pedagogique_v2.runtime.sqlite",
        "runtime/base_pedagogique_v2.runtime.sqlite.r5-provenance.json",
        "runtime/base_pedagogique_v2.runtime.sqlite-shm",
        "runtime/base_pedagogique_v2.runtime.sqlite-wal",
        "backup",
        "backup/pre-migration.sqlite",
        "backup/pre-migration.sqlite-shm",
        "backup/pre-migration.sqlite-wal",
        "backup/pre-migration.sqlite.manifest.json",
        "library",
        "library/saved-productions",
        "library/saved-productions/R4_STORE",
        "library/saved-productions/catalog.json",
        "library/saved-productions/writer.lock",
        "library/saved-productions/logs",
        "library/saved-productions/logs/observability.ndjson",
        "logs",
        "logs/observability.ndjson",
    }
)


def _inside(path: Path, root: Path) -> bool:
    resolved_path, resolved_root = path.resolve(), root.resolve()
    return resolved_path == resolved_root or resolved_path.is_relative_to(resolved_root)


@dataclass(frozen=True, slots=True)
class InspectLocalProvisioning:
    gateway: LocalProvisioningGateway

    def __post_init__(self) -> None:
        if not isinstance(self.gateway, LocalProvisioningGateway):
            raise TypeError("gateway must implement LocalProvisioningGateway")

    def execute(self, request: ProvisioningInspectionRequest) -> ProvisioningInspectionResult:
        if type(request) is not ProvisioningInspectionRequest or not request.read_only:
            raise ValueError("READ_ONLY_INSPECTION_REQUIRED")
        if not request.project_identity.strip() or not request.allowed_roots:
            raise ValueError("PROJECT_AND_BOUNDED_ROOTS_REQUIRED")
        if not request.seed_expectations or any(
            not _SHA256.fullmatch(item.sha256) or item.size_bytes <= 0
            for item in request.seed_expectations
        ):
            raise ValueError("SEED_EXPECTATIONS_INVALID")
        if any(not path.is_absolute() for path in request.allowed_roots):
            raise ValueError("ABSOLUTE_SEARCH_ROOTS_REQUIRED")
        candidates = self.gateway.discover_seed_candidates(
            request.allowed_roots, request.seed_expectations
        )
        expected_by_digest = {item.sha256: item for item in request.seed_expectations}
        authenticated: list[SeedInspection] = []
        for candidate in candidates:
            expected = expected_by_digest.get(candidate.sha256)
            if expected is None or expected.size_bytes != candidate.size_bytes:
                continue
            result = self.gateway.authenticate_seed(candidate, expected)
            if result.authenticated:
                authenticated.append(result)
        findings: list[str] = []
        if not authenticated:
            findings.append("AUTHENTICATED_SEED_NOT_FOUND")
        elif len(authenticated) > 1:
            findings.append("AUTHENTICATED_SEED_AMBIGUOUS")
        config = self.gateway.read_user_config(_OWNER_CONFIG)
        return ProvisioningInspectionResult(
            seed_candidates=tuple(authenticated),
            current_config=config,
            current_runtime_claim="NOT_INSPECTED_BY_THIS_USE_CASE",
            migration_state_claim="NOT_INSPECTED_BY_THIS_USE_CASE",
            library_root_claim="NOT_CONFIGURED_OR_NOT_INSPECTED",
            findings=tuple(findings),
        )


@dataclass(frozen=True, slots=True)
class InspectSuppliedSeedFile:
    gateway: SuppliedSeedFileGateway

    def __post_init__(self) -> None:
        if not isinstance(self.gateway, SuppliedSeedFileGateway):
            raise TypeError("gateway must implement SuppliedSeedFileGateway")

    def execute(
        self, request: SuppliedSeedFileInspectionRequest
    ) -> SuppliedSeedFileInspectionResult:
        if type(request) is not SuppliedSeedFileInspectionRequest or not request.read_only:
            raise ValueError("READ_ONLY_SUPPLIED_SEED_INSPECTION_REQUIRED")
        if not request.project_identity.strip():
            raise ValueError("PROJECT_IDENTITY_REQUIRED")
        if not request.allowed_root.is_absolute() or not request.candidate_path.is_absolute():
            raise ValueError("ABSOLUTE_SUPPLIED_SEED_PATHS_REQUIRED")
        if not _inside(request.candidate_path, request.allowed_root):
            raise ValueError("SUPPLIED_SEED_OUTSIDE_OWNER_LOCATOR")
        expected = request.expected_seed
        if not _SHA256.fullmatch(expected.sha256) or expected.size_bytes <= 0:
            raise ValueError("SUPPLIED_SEED_EXPECTATION_INVALID")
        candidate = self.gateway.measure_seed_file(request.candidate_path, request.allowed_root)
        if candidate is None:
            return SuppliedSeedFileInspectionResult(
                None, False, ("SUPPLIED_SEED_FILE_NOT_FOUND_OR_NOT_ADMISSIBLE",)
            )
        matches = (
            candidate.sha256 == expected.sha256 and candidate.size_bytes == expected.size_bytes
        )
        return SuppliedSeedFileInspectionResult(
            candidate,
            matches,
            () if matches else ("SUPPLIED_SEED_HASH_OR_SIZE_MISMATCH",),
        )


@dataclass(frozen=True, slots=True)
class InspectProvisioningTarget:
    gateway: ProvisioningTargetInspectionGateway

    def __post_init__(self) -> None:
        if not isinstance(self.gateway, ProvisioningTargetInspectionGateway):
            raise TypeError("gateway must implement ProvisioningTargetInspectionGateway")

    def execute(
        self, request: ProvisioningTargetInspectionRequest
    ) -> ProvisioningTargetInspectionResult:
        if (
            type(request) is not ProvisioningTargetInspectionRequest
            or not request.read_only
        ):
            raise ValueError("READ_ONLY_TARGET_INSPECTION_REQUIRED")
        if not request.project_identity.strip():
            raise ValueError("PROJECT_IDENTITY_REQUIRED")
        if not request.data_root.is_absolute() or not request.old_data_root.is_absolute():
            raise ValueError("ABSOLUTE_DATA_ROOTS_REQUIRED")
        root, old_root = request.data_root.resolve(), request.old_data_root.resolve()
        if not root.is_absolute() or _inside(root, old_root) or _inside(old_root, root):
            raise ValueError("NEW_DATA_ROOT_MUST_BE_DISTINCT_FROM_OLD_ROOT")
        observed = self.gateway.inspect_target(root, request.project_identity)
        recoverable = tuple(
            path
            for path in observed.observed_relative_paths
            if path.startswith("reference/.seed-copy-") and path.endswith(".tmp")
        )
        backup_sidecars = tuple(
            path
            for path in observed.observed_relative_paths
            if path.startswith("backup/.projet-v2-backup-")
            and path.endswith((".tmp-shm", ".tmp-wal"))
        )
        known_runtime_sidecars = frozenset(recoverable + backup_sidecars)
        unexpected = tuple(
            path
            for path in observed.observed_relative_paths
            if path not in _KNOWN_TARGET_PATHS and path not in known_runtime_sidecars
        )
        findings = list(observed.findings)
        if observed.data_root_exists and not observed.root_marker_valid:
            findings.append("EXISTING_DATA_ROOT_UNVERIFIED")
        if unexpected:
            findings.append("EXISTING_DATA_ROOT_HAS_UNEXPECTED_ENTRIES")
        return ProvisioningTargetInspectionResult(
            observed.data_root_exists,
            observed.root_marker_valid,
            observed.observed_relative_paths,
            unexpected,
            tuple(findings),
            tuple(sorted(known_runtime_sidecars)),
        )


@dataclass(frozen=True, slots=True)
class ApplyLocalProvisioning:
    gateway: LocalProvisioningGateway

    def __post_init__(self) -> None:
        if not isinstance(self.gateway, LocalProvisioningGateway):
            raise TypeError("gateway must implement LocalProvisioningGateway")

    def execute(self, plan: ProvisioningPlan) -> ProvisioningApplyResult:
        if type(plan) is not ProvisioningPlan:
            raise TypeError("plan must be a ProvisioningPlan")
        if not plan.approvals.all_approved:
            raise ValueError("OWNER_APPROVALS_NOT_ALL_TRUE")
        if not plan.idempotency_key or len(plan.idempotency_key) < 16:
            raise ValueError("IDEMPOTENCY_KEY_REQUIRED")
        if not plan.seed.authenticated or not _SHA256.fullmatch(plan.seed.candidate.sha256):
            raise ValueError("AUTHENTICATED_SEED_REQUIRED")
        if not plan.allowed_seed_roots or not any(
            _inside(plan.seed.candidate.path, allowed_root)
            for allowed_root in plan.allowed_seed_roots
        ):
            raise ValueError("SEED_SOURCE_OUTSIDE_APPROVED_SEARCH_ROOTS")
        if any(
            m.version not in _MIGRATIONS or m.sha256 != _MIGRATIONS[m.version]
            for m in plan.migrations
        ):
            raise ValueError("MIGRATION_HASH_MISMATCH")
        if tuple(item.version for item in plan.migrations) != ("001", "002"):
            raise ValueError("APPROVED_MIGRATION_SEQUENCE_REQUIRED")
        root = plan.data_root.resolve()
        old_root = plan.old_data_root.resolve()
        if not root.is_absolute() or _inside(root, old_root) or _inside(old_root, root):
            raise ValueError("NEW_DATA_ROOT_MUST_BE_DISTINCT_FROM_OLD_ROOT")
        targets = (plan.reference_seed, plan.runtime, plan.backup, plan.library_root)
        if any(not _inside(target, root) for target in targets):
            raise ValueError("TARGET_OUTSIDE_NEW_DATA_ROOT")
        if plan.seed.candidate.path.resolve() in (target.resolve() for target in targets):
            raise ValueError("SEED_SOURCE_TARGET_COLLISION")
        if set(dict(plan.config_values)) != set(_OWNER_CONFIG) or any(
            not value for _, value in plan.config_values
        ):
            raise ValueError("CONFIG_TARGET_INVALID")
        if dict(plan.config_values).get("PROJET_V2_DATA_DIR") != str(root):
            raise ValueError("CONFIG_DATA_ROOT_MISMATCH")
        if plan.config_target != "HKCU\\Environment":
            raise ValueError("CONFIG_TARGET_INVALID")
        if not self.gateway.validate_migration_sources(plan.migrations):
            raise ValueError("MIGRATION_SOURCE_VALIDATION_FAILED")
        authenticated_seed = self.gateway.authenticate_seed(
            plan.seed.candidate,
            SeedExpectation(plan.seed.candidate.sha256, plan.seed.candidate.size_bytes),
        )
        if (
            not authenticated_seed.authenticated
            or authenticated_seed.candidate != plan.seed.candidate
            or authenticated_seed.integrity != "ok"
            or authenticated_seed.quick_check != "ok"
            or authenticated_seed.foreign_key_violations != 0
        ):
            raise ValueError("SEED_AUTHENTICATION_FAILED_BEFORE_MUTATION")

        old_root_before = self.gateway.snapshot_old_root(old_root)
        root_created = self.gateway.create_data_root(root)
        config_before = self.gateway.read_user_config(_OWNER_CONFIG)
        reference_hash = self.gateway.copy_reference_seed(
            plan.seed, plan.reference_seed, plan.seed.candidate.sha256
        )
        if reference_hash != plan.seed.candidate.sha256:
            raise ValueError("REFERENCE_SEED_COPY_MISMATCH")
        runtime_state = self.gateway.inspect_runtime(plan.runtime, plan.migrations)
        if runtime_state.exists:
            if runtime_state.seed_sha256 != plan.seed.candidate.sha256:
                raise ValueError("RUNTIME_SEED_PROVENANCE_MISMATCH")
            if (
                runtime_state.integrity != "ok"
                or runtime_state.quick_check != "ok"
                or runtime_state.foreign_key_violations != 0
            ):
                raise ValueError("EXISTING_RUNTIME_INVALID")
            applied = dict(runtime_state.applied_migrations)
            if any(
                applied.get(item.version) != item.sha256
                for item in plan.migrations
                if item.version in applied
            ):
                raise ValueError("MIGRATION_CHECKSUM_MISMATCH")
        else:
            runtime_hash = self.gateway.create_runtime_from_reference(
                plan.reference_seed, plan.runtime, reference_hash
            )
            if runtime_hash != reference_hash:
                raise ValueError("RUNTIME_INITIAL_COPY_MISMATCH")
        state = self.gateway.inspect_runtime(plan.runtime, plan.migrations)
        if state.seed_sha256 != plan.seed.candidate.sha256:
            raise ValueError("RUNTIME_SEED_PROVENANCE_MISMATCH")
        applied = dict(state.applied_migrations)
        missing = tuple(item for item in plan.migrations if item.version not in applied)
        backup_sha = ""
        if missing:
            current_version = state.applied_migrations[-1][0] if state.applied_migrations else "000"
            backup_sha = self.gateway.create_backup(
                plan.runtime, plan.backup, plan.reference_seed, current_version
            )
            if not _SHA256.fullmatch(backup_sha):
                raise ValueError("BACKUP_NOT_VERIFIED")
            applied_now = self.gateway.apply_migrations(plan.runtime, missing)
            if applied_now != tuple(item.version for item in missing):
                raise ValueError("MIGRATION_APPLICATION_INCOMPLETE")
        else:
            if runtime_state.identity_sha256 is None:
                raise ValueError("RUNTIME_IDENTITY_UNKNOWN")
            backup_sha = self.gateway.inspect_backup(plan.backup, plan.migrations, "000") or ""
            if not backup_sha:
                raise ValueError("PRE_MIGRATION_BACKUP_NOT_FOUND_OR_INVALID")
        final_state = self.gateway.inspect_runtime(plan.runtime, plan.migrations)
        if (
            not final_state.exists
            or final_state.integrity != "ok"
            or final_state.quick_check != "ok"
            or final_state.foreign_key_violations != 0
            or tuple(version for version, _ in final_state.applied_migrations) != ("001", "002")
        ):
            raise ValueError("RUNTIME_POSTCONDITIONS_FAILED")
        library_ready = self.gateway.create_library_root(plan.library_root)
        if not library_ready:
            raise ValueError("LIBRARY_ROOT_NOT_READY")
        self.gateway.write_user_config(plan.config_values)
        config_after_write = self.gateway.read_user_config(_OWNER_CONFIG)
        if dict(config_after_write) != dict(plan.config_values):
            self.gateway.write_user_config(config_before)
            raise ValueError("USER_CONFIG_POSTCONDITION_FAILED_CONFIG_RESTORED")
        startup_ready = self.gateway.startup_probe(plan)
        if not startup_ready:
            self.gateway.write_user_config(config_before)
            raise ValueError("NORMAL_STARTUP_PROBE_FAILED_CONFIG_RESTORED")
        old_root_unchanged = old_root_before == self.gateway.snapshot_old_root(old_root)
        if not old_root_unchanged:
            self.gateway.write_user_config(config_before)
            raise ValueError("OLD_DATA_ROOT_CHANGED_CONFIG_RESTORED")
        missing_versions = {item.version for item in missing}
        return ProvisioningApplyResult(
            data_root=root,
            seed_sha256=plan.seed.candidate.sha256,
            reference_seed_sha256=reference_hash,
            runtime_sha256=final_state.identity_sha256 or "",
            migrations_applied=tuple(item.version for item in missing),
            migrations_skipped=tuple(
                item.version for item in plan.migrations if item.version not in missing_versions
            ),
            backup_sha256=backup_sha,
            library_root_ready=library_ready,
            config_before=config_before,
            config_after=self.gateway.read_user_config(_OWNER_CONFIG),
            startup_ready=startup_ready,
            rollback_config_available=True,
            idempotent_replay=not root_created and not missing,
            old_root_unchanged=old_root_unchanged,
        )
