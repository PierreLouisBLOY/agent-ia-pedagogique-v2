from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from backend.infrastructure.composition.factories.local_provisioning import (
    build_local_provisioning_inbound,
)
from backend.modules.local_provisioning.application.contracts import (
    MigrationExpectation,
    OwnerApprovals,
    ProvisioningInspectionRequest,
    ProvisioningPlan,
    ProvisioningTargetInspectionRequest,
    SeedExpectation,
)

_SEED_EXPECTATIONS = (
    SeedExpectation(
        "9d64d15e9c246924edeff16e7bbb5fb7a53791fc2ddf217541824771b34053e1",
        227_557_376,
    ),
)
_APPROVAL_SHA256 = "0abe109eab2f0f1c49c4ac484ffd596d63b5964c34a66e19a789f880145d2287"


def _load_approvals(root: Path) -> OwnerApprovals:
    evidence = (
        root
        / "livraison_lot_3"
        / "48_R5_CLEAN_USER_DATA_ROOT_20261003"
        / "200_SEED_CANDIDATE_INVENTORY.json"
    )
    payload = json.loads(evidence.read_text(encoding="utf-8-sig"))
    approval = payload.get("owner_approval")
    if not isinstance(approval, dict) or approval.get("package_sha256") != _APPROVAL_SHA256:
        raise ValueError("OWNER_APPROVAL_EVIDENCE_MISMATCH")
    decisions = approval.get("decisions")
    expected = {
        "ALLOW_CREATE_NEW_USER_OWNED_V2_DATA_ROOT",
        "ALLOW_LOCATE_AND_HASH_LOCAL_SEED_CANDIDATES",
        "ALLOW_COPY_AUTHENTICATED_SEED_TO_NEW_ROOT",
        "ALLOW_CREATE_DISTINCT_RUNTIME_FROM_SEED",
        "ALLOW_APPLY_MIGRATIONS_001_002_TO_NEW_RUNTIME",
        "ALLOW_CREATE_REAL_LIBRARY_ROOT",
        "ALLOW_UPDATE_USER_LOCAL_CONFIG_TO_NEW_ROOT",
    }
    if (
        not isinstance(decisions, dict)
        or set(decisions) != expected
        or any(value is not True for value in decisions.values())
    ):
        raise ValueError("OWNER_APPROVALS_NOT_ALL_TRUE")
    return OwnerApprovals(True, True, True, True, True, True, True, _APPROVAL_SHA256)


def run(request_path: Path, report_path: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[4]
    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    allowed_fields = {"allowed_roots", "old_data_root", "new_data_root", "idempotency_key"}
    if not isinstance(request, dict) or set(request) != allowed_fields:
        raise ValueError("PROVISIONING_REQUEST_INVALID")
    if not os.environ.get("LOCALAPPDATA"):
        raise ValueError("LOCALAPPDATA_REQUIRED")
    old_root = Path(request["old_data_root"]).resolve()
    new_root = Path(request["new_data_root"]).resolve()
    inbound = build_local_provisioning_inbound(repository_root=root, old_data_root=old_root)
    inspection = inbound.inspect(
        ProvisioningInspectionRequest(
            project_identity="agent-ia-pedagogique-v2",
            allowed_roots=tuple(Path(value) for value in request["allowed_roots"]),
            seed_expectations=_SEED_EXPECTATIONS,
            old_data_root=old_root,
            current_config=(),
        )
    )
    if inspection.findings:
        result = {
            "schema": "R5-APPLICATION-BOUNDARY-RUN-1.0",
            "state": "BLOCKED",
            "findings": list(inspection.findings),
            "authenticated_candidate_count": len(inspection.seed_candidates),
            "provider_calls": 0,
            "external_network_calls": 0,
        }
        report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    if len(inspection.seed_candidates) != 1:
        raise ValueError("AUTHENTICATED_SEED_AMBIGUOUS")
    migrations = (
        MigrationExpectation(
            "001",
            "5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102",
            root / "database" / "migrations" / "001_document_sha256_check.sql",
        ),
        MigrationExpectation(
            "002",
            "e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893",
            root / "database" / "migrations" / "002_restore_document_invariants.sql",
        ),
    )
    reference = new_root / "reference" / "base_pedagogique_v2.sqlite"
    runtime = new_root / "runtime" / "base_pedagogique_v2.runtime.sqlite"
    backup = new_root / "backup" / "pre-migration.sqlite"
    plan = ProvisioningPlan(
        project_identity="agent-ia-pedagogique-v2",
        seed=inspection.seed_candidates[0],
        data_root=new_root,
        reference_seed=reference,
        runtime=runtime,
        backup=backup,
        library_root=new_root / "library",
        migrations=migrations,
        allowed_seed_roots=tuple(Path(value) for value in request["allowed_roots"]),
        old_data_root=old_root,
        config_target="HKCU\\Environment",
        config_values=(
            ("PROJET_V2_DATA_DIR", str(new_root)),
            ("PROJET_V2_CANONICAL_DB", str(reference)),
            ("PROJET_V2_RUNTIME_DB", str(runtime)),
        ),
        idempotency_key=request["idempotency_key"],
        approvals=_load_approvals(root),
    )
    target_inspection = inbound.inspect_target(
        ProvisioningTargetInspectionRequest(
            "agent-ia-pedagogique-v2", new_root, old_root
        )
    )
    if target_inspection.findings:
        result = {
            "schema": "R5-APPLICATION-BOUNDARY-RUN-1.0",
            "state": "BLOCKED",
            "findings": list(target_inspection.findings),
            "target_root_exists": target_inspection.data_root_exists,
            "target_entries": list(target_inspection.observed_relative_paths),
            "recoverable_temporary_paths": list(target_inspection.recoverable_temporary_paths),
            "provider_calls": 0,
            "external_network_calls": 0,
            "generation_calls": 0,
        }
        report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    applied = inbound.apply(plan)
    result = {
        "schema": "R5-APPLICATION-BOUNDARY-RUN-1.0",
        "state": "APPLIED",
        "seed_sha256": applied.seed_sha256,
        "reference_seed_sha256": applied.reference_seed_sha256,
        "runtime_sha256": applied.runtime_sha256,
        "migrations_applied": list(applied.migrations_applied),
        "migrations_skipped": list(applied.migrations_skipped),
        "backup_sha256": applied.backup_sha256,
        "library_root_ready": applied.library_root_ready,
        "config_updated": applied.config_before != applied.config_after,
        "startup_ready": applied.startup_ready,
        "old_root_unchanged": applied.old_root_unchanged,
        "idempotent_replay": applied.idempotent_replay,
        "target_root_preflight_entries": list(target_inspection.observed_relative_paths),
        "known_temporary_sidecars_preflight": list(target_inspection.recoverable_temporary_paths),
        "provider_calls": 0,
        "external_network_calls": 0,
        "generation_calls": 0,
    }
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Owner-controlled local R5 provisioning")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.request, args.report)
    except Exception as error:
        security_code = getattr(getattr(error, "code", None), "value", None)
        message = str(error)
        safe_value_error_code = (
            message
            if type(error) is ValueError
            and message
            and message.replace("_", "").isalnum()
            and message.upper() == message
            else None
        )
        result = {
            "schema": "R5-APPLICATION-BOUNDARY-RUN-1.0",
            "state": "REJECTED",
            "failure_type": type(error).__name__,
            "failure_code": security_code or safe_value_error_code,
            "provider_calls": 0,
            "external_network_calls": 0,
            "generation_calls": 0,
        }
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] in {"APPLIED", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
