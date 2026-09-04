from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
ACTIVE_RESOURCE_FILES = (
    ROOT
    / "backend/modules/resource_library/domain/value_objects/persistence_vocabulary.py",
    ROOT / "backend/modules/resource_library/ports/outbound/resource_store.py",
    ROOT
    / "backend/modules/resource_library/application/dto/output/resource_view.py",
    ROOT / "backend/modules/resource_library/application/queries/get_resource.py",
    ROOT / "backend/adapters/inbound/application/resource_library.py",
)


def test_active_domain_and_application_no_longer_use_the_ambiguous_identity_type() -> None:
    sources = "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE_RESOURCE_FILES)

    assert "ResourceIdentityStatus" not in sources
    assert "identity_status" not in sources
    assert "availability_status" in sources


def test_read15_does_not_publish_unproven_canonicality() -> None:
    source = (
        ROOT / "backend/adapters/inbound/application/resource_library.py"
    ).read_text(encoding="utf-8")

    assert '"availability_status": view.availability_status' in source
    assert '"canonicality_status"' not in source
    assert '"identity_status"' not in source


def test_legacy_sqlite_identity_column_is_confined_to_outbound_mapping() -> None:
    adapter = (
        ROOT / "backend/adapters/outbound/resource_library/sqlite.py"
    ).read_text(encoding="utf-8")
    mapping = (
        ROOT / "backend/adapters/outbound/persistence/vocabulary.py"
    ).read_text(encoding="utf-8")

    assert 'record.get("identity_status")' in adapter
    assert "_LegacyResourceIdentityStatus" in mapping
    assert "not losslessly representable by the legacy column" in mapping


def test_derived_resource_catalog_names_only_the_proven_dimension() -> None:
    source = (
        ROOT / "backend/adapters/outbound/read_models/sqlite.py"
    ).read_text(encoding="utf-8")

    assert "availability_status: str" in source
    assert "identity_status: str" not in source
