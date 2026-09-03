from pathlib import Path

ROOT = Path(__file__).parents[2]
LOADER = ROOT / "backend/infrastructure/config/loaders/sqlite.py"
SCHEMA = ROOT / "backend/infrastructure/config/schemas/sqlite.py"
COMPOSITION = ROOT / "backend/infrastructure/composition/factories/sqlite.py"


def test_portable_configuration_declares_new_and_legacy_names() -> None:
    source = LOADER.read_text(encoding="utf-8")

    for setting in (
        "PROJET_V2_DATA_DIR",
        "PROJET_V2_CANONICAL_DB",
        "PROJET_V2_RUNTIME_DB",
        "PEDAGOGICAL_CANONICAL_SEED_PATH",
        "PEDAGOGICAL_RUNTIME_DATABASE_PATH",
    ):
        assert setting in source


def test_configuration_contains_no_private_or_nominative_default() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (LOADER, SCHEMA, COMPOSITION)
    )

    forbidden_fragments = (
        "-".join(("Pierre", "Louis")),
        "Desk" + "top",
        "Mon" + " Drive",
        "G:" + "\\",
    )
    for forbidden in forbidden_fragments:
        assert forbidden not in source


def test_loader_performs_no_global_disk_discovery() -> None:
    source = LOADER.read_text(encoding="utf-8")

    for forbidden in ("rglob(", "glob(", "os.walk(", "Path.home(", "expanduser("):
        assert forbidden not in source


def test_composition_uses_the_config_loader_without_reading_environment() -> None:
    source = COMPOSITION.read_text(encoding="utf-8")

    assert "load_sqlite_paths" in source
    assert "os.environ" not in source
    assert "dotenv" not in source


def test_path_contract_contains_no_sql_provider_or_business_owner() -> None:
    source = SCHEMA.read_text(encoding="utf-8")

    assert "sqlite3" not in source
    assert "openai" not in source.lower()
    assert "anthropic" not in source.lower()
    assert "backend.modules" not in source
