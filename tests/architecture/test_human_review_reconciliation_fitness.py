from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNER = ROOT / "tests/calibration/pedagogical/human_review_reconciliation.py"


def test_human_review_reconciliation_owner_is_offline_and_route_neutral() -> None:
    source = OWNER.read_text(encoding="utf-8")
    assert "backend." not in source
    assert "OpenAI(" not in source
    assert "Anthropic(" not in source
    assert "OPENAI_API_KEY" not in source
    assert "ANTHROPIC_API_KEY" not in source
    assert "os.environ" not in source
    assert '"openai_calls": 0' in source
    assert '"anthropic_calls": 0' in source
    assert '"PROVIDER_ROUTE_CHANGE": "NONE"' in source


def test_human_review_reconciliation_outputs_are_bounded_and_governed() -> None:
    source = OWNER.read_text(encoding="utf-8")
    assert "PHASE_12_16_G2_HUMAN_REVIEW_RECONCILIATION_REPORT" in source
    assert "PHASE_12_16_G2_HUMAN_REVIEW_RECONCILIATION_BASELINE" in source
    assert "artifacts/calibration/12.16-g2-human-review/completed_review.md" in source
    assert "artifacts/calibration/12.16-g2-r4-r5/human_review_reconciliation.json" in source
    assert "ADR-P12-063" in source
    assert "ADR-P12-064" in source
    assert "OWNER_CALIBRATION_DECISION_READY" in source
