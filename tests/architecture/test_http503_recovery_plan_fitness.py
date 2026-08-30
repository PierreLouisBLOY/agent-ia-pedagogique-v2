from __future__ import annotations

from pathlib import Path

from tests.calibration.pedagogical.r4_r3_r1_recovery import (
    BASELINE_RELATIVE_PATH,
    PLAN_JSON_RELATIVE_PATH,
    PLAN_MARKDOWN_RELATIVE_PATH,
    RECOVERY_LEDGER_RELATIVE_PATH,
    RECOVERY_PLAN_VERSION,
    REUSABLE_MANIFEST_RELATIVE_PATH,
)

ROOT = Path(__file__).resolve().parents[2]
OWNER = ROOT / "tests/calibration/pedagogical/r4_r3_r1_recovery.py"


def _python_files(relative_directory: str) -> tuple[Path, ...]:
    return tuple((ROOT / relative_directory).rglob("*.py"))


def test_http503_recovery_owner_remains_test_only_and_runtime_is_unmodified() -> None:
    forbidden_import = "tests.calibration.pedagogical.r4_r3_r1_recovery"

    assert OWNER.is_file()
    for path in _python_files("backend") + _python_files("evaluation_harness"):
        assert forbidden_import not in path.read_text(encoding="utf-8")


def test_recovery_owner_has_no_live_credential_or_transport_authority() -> None:
    source = OWNER.read_text(encoding="utf-8")

    for forbidden in (
        "EnvironmentProviderSecretResolver",
        "AnthropicSDKScoringTransportFactory",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "messages.create",
        "run_live_calibration",
    ):
        assert forbidden not in source
    assert "live_provider_calls_r1" in source
    assert '"openai_calls": 0' in source
    assert '"anthropic_calls": 0' in source


def test_recovery_outputs_stay_in_declared_document_and_ignored_artifact_boundaries() -> None:
    tracked = (BASELINE_RELATIVE_PATH, PLAN_MARKDOWN_RELATIVE_PATH, PLAN_JSON_RELATIVE_PATH)
    ignored = (RECOVERY_LEDGER_RELATIVE_PATH, REUSABLE_MANIFEST_RELATIVE_PATH)

    assert all(path.startswith("docs/development/") for path in tracked)
    assert all(path.startswith("artifacts/calibration/12.16-g2-r4-r4/") for path in ignored)
    assert RECOVERY_PLAN_VERSION == "12.16-g2-r4-r4-anthropic-recovery-completion-v1"
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/artifacts/" in gitignore


def test_existing_adrs_cover_recovery_without_new_architectural_decision() -> None:
    adr63 = ROOT / "architecture/adr/ADR-P12-063-pedagogical-model-calibration-protocol.md"
    adr64 = ROOT / "architecture/adr/ADR-P12-064-explicit-homogeneous-anthropic-scoring-policy.md"
    baseline = (ROOT / BASELINE_RELATIVE_PATH).read_text(encoding="utf-8")

    assert adr63.is_file() and adr64.is_file()
    assert "ADR-P12-063" in baseline
    assert "ADR-P12-064" in baseline
    assert "ADR supplémentaire : `NO`" in baseline
