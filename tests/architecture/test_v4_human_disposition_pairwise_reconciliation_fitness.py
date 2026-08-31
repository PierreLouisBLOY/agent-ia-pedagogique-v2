from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

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
    frozen = {
        "tests/calibration/pedagogical/catalog.py": (
            "53da2068fa6585086fe955b633a1d8e173cf770c8b5cb5e71f6cc8cc474e7317"
        ),
        "tests/calibration/pedagogical/anchor_corpus_v2.py": (
            "bd0c5eff43be20b4f578b99321e076471804f8a3e0e197858b08a3701800be76"
        ),
        "tests/calibration/pedagogical/anchor_corpus_v3.py": (
            "cf90457393b02dca233cd4bc5d5c73e4a63a091591cb448d19b30b68e6bdc241"
        ),
        "tests/calibration/pedagogical/anchor_corpus_v4.py": (
            "b0a86640502db4ab1d0b623e50faffa45178d9e93b0a24976df3312d460662be"
        ),
        "architecture/adr/ADR-P12-067-disposition-first-pairwise-human-calibration.md": (
            "3d22fb3c79f9ff17834cdcbea1a355e189693853761b91364a3438e5409a3301"
        ),
        "docs/development/PHASE_12_16_G2_V4_DISPOSITION_FIRST_REMEDIATION_BASELINE.md": (
            "f4c491aad290455a407377200208ea961c95fa06c9b7cb4c78dbc20a08aea096"
        ),
        "docs/development/PHASE_12_16_G2_V4_NEGATIVE_CONTROL_REMEDIATION_MATRIX.md": (
            "05d9e8fd1d7a154f09e8000aa25d768191c16052afa77f174c5f3d0e5aa9fdde"
        ),
        "docs/development/PHASE_12_16_G2_V4_HUMAN_DISPOSITION_PAIRWISE_PACKET.md": (
            "56bc9d28b65b2e7b82a982cf36afb56d13e147ce6c0716587acaef47e4c42a1f"
        ),
    }
    actual = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in frozen
    }
    assert actual == frozen


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
