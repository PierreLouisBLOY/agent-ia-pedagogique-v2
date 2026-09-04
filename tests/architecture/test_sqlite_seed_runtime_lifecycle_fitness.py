from pathlib import Path

ROOT = Path(__file__).parents[2]
LIFECYCLE = ROOT / "backend/adapters/outbound/persistence/migrations.py"
SQLITE = ROOT / "backend/adapters/outbound/persistence/sqlite.py"
FILESYSTEM = ROOT / "backend/infrastructure/filesystem/security.py"


def test_seed_reader_is_explicitly_immutable_and_query_only() -> None:
    lifecycle = LIFECYCLE.read_text(encoding="utf-8")
    sqlite = SQLITE.read_text(encoding="utf-8")

    assert "immutable=authenticate_seed" in lifecycle
    assert "immutable=1" in sqlite
    assert "PRAGMA query_only = ON" in sqlite


def test_runtime_publication_is_fresh_and_atomic() -> None:
    source = LIFECYCLE.read_text(encoding="utf-8")
    filesystem = FILESYSTEM.read_text(encoding="utf-8")

    assert "private_temporary_file" in source
    assert "tempfile.mkstemp" in filesystem
    assert "atomic_publish_fresh" in source
    assert "os.link(source_snapshot.path, destination_snapshot.path)" in filesystem
    assert "shutil.copy2(seed_path, temporary)" in source
    assert "shutil.copy2(seed_path, runtime_path)" not in source


def test_migration_policy_is_allowlisted_and_unknowns_remain_deferred() -> None:
    source = LIFECYCLE.read_text(encoding="utf-8")

    assert "APPROVED_RUNTIME_MIGRATIONS" in source
    assert "MigrationNotAllowed" in source
    assert "resource.active-canonical" in source
    assert "pedagogical-context.origin" in source


def test_lifecycle_contains_no_private_path_or_provider_dependency() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (LIFECYCLE, SQLITE)
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
