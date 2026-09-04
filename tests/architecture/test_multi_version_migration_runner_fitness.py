import hashlib
from pathlib import Path

ROOT = Path(__file__).parents[2]
RUNNER = ROOT / "backend/adapters/outbound/persistence/migrations.py"
MIGRATION_001 = ROOT / "database/migrations/001_document_sha256_check.sql"
MIGRATION_001_SHA256 = "5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102"


def test_migration_001_remains_bit_for_bit_immutable() -> None:
    assert hashlib.sha256(MIGRATION_001.read_bytes()).hexdigest() == MIGRATION_001_SHA256


def test_runner_owns_an_ordered_checksum_registry_and_prefix_validation() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "class MigrationSpec" in source
    assert "class MigrationRegistry" in source
    assert "migration order must be contiguous from 1" in source
    assert "migration versions must be contiguous from 001" in source
    assert "migration history is not an ordered prefix" in source
    assert "MigrationChecksumMismatch" in source


def test_runner_rejects_seed_as_target_before_loading_migrations() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    provision = source[source.index("def provision_runtime(") :]

    assert provision.index("_assert_distinct(seed_path, runtime_path)") < provision.index(
        "_coerce_migration_registry(migration_source)"
    )


def test_runner_contains_no_private_path_or_provider_dependency() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    private_fragments = (
        "-".join(("Pierre", "Louis")),
        "Desk" + "top",
        "Mon" + " Drive",
        "G:" + "\\",
    )

    assert all(fragment not in source for fragment in private_fragments)
    assert "openai" not in source.lower()
    assert "anthropic" not in source.lower()
