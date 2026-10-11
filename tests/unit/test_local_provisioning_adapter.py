from __future__ import annotations

import hashlib
import stat
from pathlib import Path

import pytest

from backend.adapters.outbound.system.local_provisioning import LocalProvisioningAdapter
from backend.infrastructure.filesystem.security import LocalFileSecurityError
from backend.modules.local_provisioning.application.contracts import (
    ProvisioningTargetInspectionRequest,
    SeedCandidate,
    SeedExpectation,
)
from backend.modules.local_provisioning.application.use_cases import InspectProvisioningTarget

OLD_SEED_SHA256 = "38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134"
OLD_SEED_SIZE = 105_553_920


def test_seed_discovery_is_bounded_to_supplied_roots_and_hash_matches(tmp_path: Path) -> None:
    search_root = tmp_path / "approved-search-root"
    nested = search_root / "reference"
    nested.mkdir(parents=True)
    payload = b"admitted-seed-test-fixture"
    candidate = nested / "01_base_pedagogique_v2.sqlite"
    candidate.write_bytes(payload)
    elsewhere = tmp_path / "outside" / candidate.name
    elsewhere.parent.mkdir()
    elsewhere.write_bytes(payload)
    expected = SeedExpectation(hashlib.sha256(payload).hexdigest(), len(payload))
    adapter = LocalProvisioningAdapter(
        repository_root=tmp_path / "repository",
        old_data_root=tmp_path / "old-data-root",
    )

    found = adapter.discover_seed_candidates((search_root,), (expected,))

    assert tuple(item.path for item in found) == (candidate,)
    assert found[0].sha256 == expected.sha256


def test_seed_discovery_ignores_wrong_size_database_files(tmp_path: Path) -> None:
    search_root = tmp_path / "approved-search-root"
    search_root.mkdir()
    (search_root / "not-the-seed.sqlite").write_bytes(b"wrong")
    expected = SeedExpectation("a" * 64, 100)
    adapter = LocalProvisioningAdapter(
        repository_root=tmp_path / "repository",
        old_data_root=tmp_path / "old-data-root",
    )

    assert adapter.discover_seed_candidates((search_root,), (expected,)) == ()


def test_exact_supplied_seed_measurement_reports_actual_size_and_hash(tmp_path: Path) -> None:
    search_root = tmp_path / "owner-supplied"
    search_root.mkdir()
    payload = b"owner-supplied-file-with-unexpected-identity"
    candidate = search_root / "CP645_FINALISATION_628_SUR_628.sqlite"
    candidate.write_bytes(payload)
    adapter = LocalProvisioningAdapter(
        repository_root=tmp_path / "repository",
        old_data_root=tmp_path / "old-data-root",
    )

    measured = adapter.measure_seed_file(candidate, search_root)

    assert measured is not None
    assert measured.path == candidate
    assert measured.size_bytes == len(payload)
    assert measured.sha256 == hashlib.sha256(payload).hexdigest()


def test_exact_supplied_seed_measurement_rejects_path_outside_locator(tmp_path: Path) -> None:
    search_root = tmp_path / "owner-supplied"
    search_root.mkdir()
    outside = tmp_path / "outside.sqlite"
    outside.write_bytes(b"bytes")
    adapter = LocalProvisioningAdapter(
        repository_root=tmp_path / "repository",
        old_data_root=tmp_path / "old-data-root",
    )

    with pytest.raises(LocalFileSecurityError, match="OUTSIDE_ALLOWED_ROOT"):
        adapter.measure_seed_file(outside, search_root)


def test_superseded_seed_is_rejected_without_opening_or_creating_runtime(tmp_path: Path) -> None:
    adapter = LocalProvisioningAdapter(
        repository_root=tmp_path / "repository",
        old_data_root=tmp_path / "old-data-root",
    )
    old_candidate = SeedCandidate(
        tmp_path / "historical" / "01_base_pedagogique_v2.sqlite",
        OLD_SEED_SHA256,
        OLD_SEED_SIZE,
    )
    runtime = tmp_path / "new-data-root" / "runtime.sqlite"

    rejected = adapter.authenticate_seed(
        old_candidate, SeedExpectation(OLD_SEED_SHA256, OLD_SEED_SIZE)
    )

    assert rejected.authenticated is False
    assert rejected.integrity == "NOT_OPENED"
    assert rejected.quick_check == "NOT_OPENED"
    assert not runtime.exists()
    assert not old_candidate.path.exists()


def test_target_inspection_reports_preexisting_unexpected_files_without_writing(tmp_path: Path) -> None:
    root = tmp_path / "new-data-root"
    root.mkdir()
    (root / ".r5-root.json").write_text(
        '{"schema":"R5-USER-DATA-ROOT-1.0","project_identity":"agent-ia-pedagogique-v2"}\n',
        encoding="utf-8",
    )
    unexpected = root / "unexpected.sqlite"
    unexpected.write_bytes(b"preserve")
    adapter = LocalProvisioningAdapter(
        repository_root=tmp_path / "repository",
        old_data_root=tmp_path / "old-data-root",
    )

    result = InspectProvisioningTarget(adapter).execute(
        ProvisioningTargetInspectionRequest(
            "agent-ia-pedagogique-v2", root, tmp_path / "old-data-root"
        )
    )

    assert result.data_root_exists is True
    assert result.root_marker_valid is True
    assert result.unexpected_relative_paths == ("unexpected.sqlite",)
    assert result.findings == ("EXISTING_DATA_ROOT_HAS_UNEXPECTED_ENTRIES",)
    assert unexpected.read_bytes() == b"preserve"


def test_existing_reference_seed_is_rehardened_and_interrupted_copy_temp_is_recovered(
    tmp_path: Path,
) -> None:
    import hashlib

    from backend.modules.local_provisioning.application.contracts import SeedInspection

    root = tmp_path / "new-data-root"
    reference_dir = root / "reference"
    reference_dir.mkdir(parents=True)
    (root / ".r5-root.json").write_text(
        '{"schema":"R5-USER-DATA-ROOT-1.0","project_identity":"agent-ia-pedagogique-v2"}\n',
        encoding="utf-8",
    )
    payload = b"verified-canonical-reference-seed"
    expected_sha256 = hashlib.sha256(payload).hexdigest()
    target = reference_dir / "base_pedagogique_v2.sqlite"
    target.write_bytes(payload)
    temporary = reference_dir / ".seed-copy-recovered.tmp"
    temporary.write_bytes(b"interrupted-copy")
    temporary.chmod(stat.S_IREAD)
    source = SeedInspection(
        SeedCandidate(tmp_path / "source.sqlite", expected_sha256, len(payload)),
        True,
        "ok",
        "ok",
        0,
        1,
        0,
        0,
        0,
    )
    adapter = LocalProvisioningAdapter(
        repository_root=tmp_path / "repository",
        old_data_root=tmp_path / "old-data-root",
    )

    result = adapter.copy_reference_seed(source, target, expected_sha256)

    assert result == expected_sha256
    assert target.read_bytes() == payload
    assert not temporary.exists()
