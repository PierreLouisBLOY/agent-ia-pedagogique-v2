import ast
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    LOCAL_REFERENCE_LABEL,
    SECTION_IDS,
    SYNTHETIC_REFERENCE_LABEL,
    ConversationDraft,
)
from tests.support import r5_scope_guard as guard

ROOT = Path(__file__).resolve().parents[2]


def test_exact_active_scope_no_private_preparations_staged():
    from tests.support.r3_guard_oracle import PREPARATION
    changed = set()
    for args in (["diff", "--name-only", guard.BASELINE, "--"], ["diff", "--cached", "--name-only", guard.BASELINE, "--"],
                 ["ls-files", "--others", "--exclude-standard"]):
        paths = set(subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines())
        if "--cached" in args:
            assert not paths & set(PREPARATION)
        changed |= paths
    assert guard.violations(ROOT, changed=changed - set(PREPARATION)) == []
    for path in guard.PATHS:
        staged = subprocess.run(["git", "show", ":" + path], cwd=ROOT, capture_output=True)
        if staged.returncode:
            assert path not in guard.PRE
        else:
            assert guard.index_matches(ROOT, path, staged.stdout), path


def test_closed_versioned_provenance_keeps_synthetic_and_rejects_forgery():
    reference = {"evidence_id": "e:1", "source_ref": "r:1", "version_ref": "v:1", "checksum_sha256": "a" * 64,
                 "locator": "p:1", "provenance_label": SYNTHETIC_REFERENCE_LABEL, "declared_used": True}
    draft = ConversationDraft("prod:" + "a" * 32, "contenu synthétique",
        tuple({"section_id": name, "text": "Texte purement synthétique pour le test."} for name in SECTION_IDS),
        (reference,), {"source_run_id": "run:1", "source_step_id": "step:1", "evidence_set_ref": "es:1"}, ())
    assert replace(draft, references=({**reference, "provenance_label": LOCAL_REFERENCE_LABEL},))
    with pytest.raises(ValueError, match="INVALID_DRAFT_REFERENCE"):
        replace(draft, references=({**reference, "provenance_label": "OFFICIAL_APPROVED"},))
    with pytest.raises(ValueError, match="MIXED_REFERENCE_PROVENANCE"):
        replace(draft, references=(reference, {**reference, "evidence_id": "e:2", "provenance_label": LOCAL_REFERENCE_LABEL}))


def test_new_entry_has_no_network_credentials_provider_or_http_route():
    from tests.support.r5_worker_guard import violations as worker_violations
    assert worker_violations(ROOT) == []
    paths = [p for p in guard.HISTORICAL_PATHS if p.startswith("backend/") and p not in guard.PRE]
    forbidden = {"openai", "anthropic", "socket", "urllib", "requests", "getpass", "os"}
    for path in paths:
        tree = ast.parse((ROOT / path).read_bytes())
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imports += [alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names]
        assert not any(name and (name.split(".")[0] in forbidden or "credential" in name or ".openai" in name) for name in imports)
    routes = "backend/adapters/inbound/api/routes.py"
    before = subprocess.run(["git", "show", guard.BASELINE + ":" + routes], cwd=ROOT, check=True, capture_output=True).stdout
    assert guard.digest(before) == guard.digest((ROOT / routes).read_bytes())
