from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_sqlite_is_confined_to_outbound_adapters_and_composition() -> None:
    forbidden_roots = (ROOT / "backend" / "agent_runtime", ROOT / "backend" / "modules")
    offenders = []
    for root in forbidden_roots:
        for path in root.rglob("*.py"):
            if "sqlite3" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_no_generic_repository_or_database_binary_is_introduced() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "backend" / "adapters" / "outbound").rglob("*.py")
    )
    assert "GenericRepository" not in sources
    assert not tuple(ROOT.rglob("*.sqlite"))
    assert not tuple(ROOT.rglob("*.sqlite3"))


def test_phase7_migration_is_kept_in_the_adapter_owned_migration_directory() -> None:
    migration = ROOT / "database" / "migrations" / "001_document_sha256_check.sql"
    assert migration.is_file()
    assert "BEGIN IMMEDIATE" in migration.read_text(encoding="utf-8")
