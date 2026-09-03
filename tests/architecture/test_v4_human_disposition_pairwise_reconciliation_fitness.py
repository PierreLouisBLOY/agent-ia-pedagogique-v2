from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from tests.support.historical_hash_freeze import assert_current_historical_hashes

ROOT = Path(__file__).resolve().parents[2]
OWNER = (
    ROOT
    / "tests/calibration/pedagogical/"
    "v4_human_disposition_pairwise_reconciliation.py"
)
REPORT = (
    ROOT
    / "docs/development/"
    "PHASE_12_16_G2_V4_HUMAN_DISPOSITION_PAIRWISE_RECONCILIATION.md"
)
LOCAL_RESULT = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v4/"
    "human_disposition_pairwise_reconciliation_result.json"
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_reconciliation_owner_is_offline_test_only_and_runtime_neutral() -> None:
    imports = _imports(OWNER)
    assert not any(name == "backend" or name.startswith("backend.") for name in imports)
    assert not any(name == "openai" or name.startswith("openai.") for name in imports)
    assert not any(name == "anthropic" or name.startswith("anthropic.") for name in imports)
    source = OWNER.read_text(encoding="utf-8")
    forbidden = (
        "EnvironmentProviderSecretResolver",
        "TransportFactory",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "os.environ",
        ".responses.create(",
        ".messages.create(",
    )
    assert all(marker not in source for marker in forbidden)
    assert '"provider_calls": 0' in source
    assert '"runtime_route_change": "NONE"' in source
    assert '"release_threshold_adoption": "NOT_ALLOWED"' in source


def test_local_inputs_and_result_are_ignored_while_report_is_trackable() -> None:
    for relative_path in (
        "artifacts/calibration/12.16-g2-anchor-corpus-v4/"
        "completed_human_disposition_pairwise.md",
        "artifacts/calibration/12.16-g2-anchor-corpus-v4/"
        "human_disposition_pairwise_reconciliation.json",
        LOCAL_RESULT,
    ):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", relative_path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 0
    tracked = subprocess.run(
        [
            "git",
            "check-ignore",
            "--quiet",
            "docs/development/"
            "PHASE_12_16_G2_V4_HUMAN_DISPOSITION_PAIRWISE_RECONCILIATION.md",
        ],
        cwd=ROOT,
        check=False,
    )
    assert tracked.returncode == 1


def test_historical_v1_v2_v3_v4_sources_remain_byte_exact() -> None:
    assert_current_historical_hashes(
        ROOT,
        (
            "tests/calibration/pedagogical/catalog.py",
            "tests/calibration/pedagogical/anchor_corpus_v2.py",
            "tests/calibration/pedagogical/anchor_corpus_v3.py",
            "tests/calibration/pedagogical/anchor_corpus_v4.py",
            "architecture/adr/ADR-P12-067-disposition-first-pairwise-human-calibration.md",
            "docs/development/PHASE_12_16_G2_V4_DISPOSITION_FIRST_REMEDIATION_BASELINE.md",
            "docs/development/PHASE_12_16_G2_V4_NEGATIVE_CONTROL_REMEDIATION_MATRIX.md",
            "docs/development/PHASE_12_16_G2_V4_HUMAN_DISPOSITION_PAIRWISE_PACKET.md",
        ),
    )


def test_tracked_report_preserves_blind_mapping_and_authority_separation() -> None:
    report = REPORT.read_text(encoding="utf-8")
    assert "CAND-" not in report
    assert "cal.v4.scn-" not in report
    assert "PROVIDER_CALLS = `0`; PROVIDER_COST = `0`" in report
    assert "RUNTIME_ROUTE_CHANGE = `NONE`" in report
    assert "RELEASE_THRESHOLD_ADOPTION = `NOT_ALLOWED`" in report
    assert "PROVIDER != AUTHORITY" in report
    assert "MODEL_JUDGE != DOMAIN_VALIDATOR" in report
    assert "Aucun corpus v5 n'est créé automatiquement" in report
    assert "12.16-G2-V4-OWNER_DECISION_REQUIRED" in report
