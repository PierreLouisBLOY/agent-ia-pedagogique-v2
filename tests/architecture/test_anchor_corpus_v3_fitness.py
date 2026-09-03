from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from tests.support.historical_hash_freeze import assert_current_historical_hashes

ROOT = Path(__file__).resolve().parents[2]
OWNER = ROOT / "tests/calibration/pedagogical/anchor_corpus_v3.py"
ADR = (
    ROOT
    / "architecture/adr/"
    "ADR-P12-066-strong-only-deliverability-calibration-semantics.md"
)
LOCAL_KEY = (
    "artifacts/calibration/12.16-g2-anchor-corpus-v3/"
    "human_delta_prevalidation_reconciliation.json"
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


def test_v3_owner_is_test_only_offline_and_runtime_route_neutral() -> None:
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
    assert "GateEngine/runtime/routes : `UNCHANGED`" in source


def test_v3_local_key_is_ignored_and_tracked_documents_are_not() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", LOCAL_KEY],
        cwd=ROOT,
        check=False,
    )
    assert ignored.returncode == 0
    for relative_path in (
        "docs/development/"
        "PHASE_12_16_G2_ANCHOR_CORPUS_V3_CRITERION_DEFECT_ALIGNMENT_MATRIX.md",
        "docs/development/PHASE_12_16_G2_V3_HUMAN_DELTA_PREVALIDATION_PACKET.md",
        "docs/development/"
        "PHASE_12_16_G2_ANCHOR_CORPUS_V3_STRONG_ONLY_REMEDIATION_BASELINE.md",
        "architecture/adr/"
        "ADR-P12-066-strong-only-deliverability-calibration-semantics.md",
    ):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", relative_path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 1


def test_v1_v2_corpus_and_reconciliation_proofs_remain_byte_exact() -> None:
    assert_current_historical_hashes(
        ROOT,
        (
            "tests/calibration/pedagogical/catalog.py",
            "tests/calibration/pedagogical/anchor_corpus_v2.py",
            "docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_PACKET.md",
            "docs/development/PHASE_12_16_G2_V2_HUMAN_PREVALIDATION_RECONCILIATION.md",
            "architecture/adr/ADR-P12-065-versioned-human-prevalidated-anchor-corpus.md",
        ),
    )


def test_adr_p12_066_records_durable_primary_secondary_separation() -> None:
    source = ADR.read_text(encoding="utf-8")
    assert "Statut : Accepté" in source
    assert "STRONG_ONLY" in source
    assert "DELIVERY_CANDIDATE" in source
    assert "NON_DELIVERABLE_NEGATIVE_CONTROL" in source
    assert "secondaires et non bloquants" in source
    assert "ni seuil runtime" in source
    assert "Un résultat de scorer n'est pas un résultat runtime" in source
    assert "GateEngine" in source
    assert "V1 et v2 demeurent immuables" in source
