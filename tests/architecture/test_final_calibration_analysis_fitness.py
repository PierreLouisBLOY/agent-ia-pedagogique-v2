from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNER = ROOT / "tests/calibration/pedagogical/r4_r3_r3_analysis.py"


def test_analysis_owner_is_offline_test_only_and_route_neutral() -> None:
    source = OWNER.read_text(encoding="utf-8")
    assert "backend." not in source
    assert "OpenAI(" not in source
    assert "Anthropic(" not in source
    assert "OPENAI_API_KEY" not in source
    assert "ANTHROPIC_API_KEY" not in source
    assert "os.environ" not in source
    assert "LIVE_PROVIDER_CALLS_R3" in source or "live_provider_calls_r3" in source
    assert '"PROVIDER_ROUTE_CHANGE": "NONE"' in source


def test_analysis_outputs_are_docs_or_ignored_runtime_artifacts() -> None:
    source = OWNER.read_text(encoding="utf-8")
    assert "docs/development/PHASE_12_16_G2_FINAL_CALIBRATION_ANALYSIS" in source
    assert "docs/development/PHASE_12_16_G2_HUMAN_ANCHOR_REVIEW_PACKET.md" in source
    assert "artifacts/calibration/12.16-g2-r4-r5" in source
    assert "ADR-P12-063" in source
    assert "ADR-P12-064" in source
