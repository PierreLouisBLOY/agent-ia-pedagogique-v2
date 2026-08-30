from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNER = ROOT / "tests/calibration/pedagogical/anchor_corpus_v2.py"
ADR = ROOT / "architecture/adr/ADR-P12-065-versioned-human-prevalidated-anchor-corpus.md"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_v2_owner_is_test_only_offline_and_provider_route_neutral() -> None:
    imports = _imports(OWNER)
    assert not any(name == "backend" or name.startswith("backend.") for name in imports)
    assert not any(name == "openai" or name.startswith("openai.") for name in imports)
    assert not any(name == "anthropic" or name.startswith("anthropic.") for name in imports)
    source = OWNER.read_text(encoding="utf-8")
    assert "EnvironmentProviderSecretResolver" not in source
    assert "TransportFactory" not in source
    assert "OPENAI_API_KEY" not in source
    assert "ANTHROPIC_API_KEY" not in source
    assert "os.environ" not in source
    assert ".responses.create(" not in source
    assert ".messages.create(" not in source
    assert '"provider_calls": 0' in source
    assert "PROVIDER_ROUTE_CHANGE : `NONE`" in source


def test_v2_artifacts_are_versioned_tracked_or_explicitly_ignored() -> None:
    source = OWNER.read_text(encoding="utf-8")
    assert "12.16-g1-v2" in source
    assert "PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_PACKET.md" in source
    assert "PHASE_12_16_G2_ANCHOR_CORPUS_V2_DIFFERENTIATION_MATRIX.md" in source
    assert "PHASE_12_16_G2_ANCHOR_CORPUS_V2_REMEDIATION_BASELINE.md" in source
    assert "artifacts/calibration/12.16-g2-anchor-corpus-v2" in source
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "--quiet",
            "artifacts/calibration/12.16-g2-anchor-corpus-v2/"
            "human_prevalidation_reconciliation.json",
        ],
        cwd=ROOT,
        check=False,
    )
    assert ignored.returncode == 0


def test_adr_p12_065_records_versioning_and_human_gate_without_live_authority() -> None:
    source = ADR.read_text(encoding="utf-8")
    assert "Statut : Accepté" in source
    assert "12.16-g1-v1" in source
    assert "12.16-g1-v2" in source
    assert "CLOSED_DIAGNOSTIC_BASELINE" in source
    assert "16/16" in source
    assert "Aucun seuil de release" in source
    assert "aucun appel live" in source.casefold()
