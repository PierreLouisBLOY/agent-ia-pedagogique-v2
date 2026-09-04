import hashlib
from pathlib import Path

ROOT = Path(__file__).parents[2]
RUNNER = ROOT / "backend/adapters/outbound/persistence/migrations.py"
MIGRATION_001 = ROOT / "database/migrations/001_document_sha256_check.sql"
MIGRATION_002 = ROOT / "database/migrations/002_restore_document_invariants.sql"
MIGRATION_001_SHA256 = "5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102"
MIGRATION_002_SHA256 = "e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893"


def test_migration_identities_are_immutable_and_distinct() -> None:
    assert hashlib.sha256(MIGRATION_001.read_bytes()).hexdigest() == MIGRATION_001_SHA256
    assert hashlib.sha256(MIGRATION_002.read_bytes()).hexdigest() == MIGRATION_002_SHA256
    assert MIGRATION_001_SHA256 != MIGRATION_002_SHA256


def test_002_contains_only_the_document_invariant_rebuild() -> None:
    sql = MIGRATION_002.read_text(encoding="utf-8")

    assert "DEFAULT 'OTHER'" in sql
    assert "DEFAULT 'fr'" in sql
    assert "DEFAULT 'ACTIVE'" in sql
    assert "DEFAULT CURRENT_TIMESTAMP" in sql
    assert "size_bytes IS NULL OR size_bytes >= 0" in sql
    assert "length(sha256) = 64" in sql
    assert "CREATE INDEX idx_document_sha256" in sql
    assert "CREATE INDEX idx_document_url" in sql
    assert "context_origin" not in sql.lower()
    assert "is_canonical" not in sql.lower()
    assert "resource_ref" not in sql.lower()


def test_runner_registers_002_with_its_own_postcondition() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'MIGRATION_002_VERSION = "002"' in source
    assert f'MIGRATION_002_SHA256 = "{MIGRATION_002_SHA256}"' in source
    assert 'MIGRATION_002_FILENAME = "002_restore_document_invariants.sql"' in source
    assert 'DOCUMENT_INVARIANTS_POSTCONDITION = "document-invariants"' in source
    assert "_assert_document_invariants(connection)" in source


def test_002_and_runner_contain_no_private_path_or_provider_dependency() -> None:
    source = RUNNER.read_text(encoding="utf-8") + MIGRATION_002.read_text(
        encoding="utf-8"
    )
    private_fragments = (
        "-".join(("Pierre", "Louis")),
        "Desk" + "top",
        "Mon" + " Drive",
        "G:" + "\\",
    )

    assert all(fragment not in source for fragment in private_fragments)
    assert "openai" not in source.lower()
    assert "anthropic" not in source.lower()
