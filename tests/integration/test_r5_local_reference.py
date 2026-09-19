import hashlib
import json
from contextlib import closing
from dataclasses import replace

import pytest

from backend.adapters.inbound.cli.local_references import execute, main
from backend.adapters.outbound.evidence.local_reference import (
    LocalReferenceContentAdapter,
    LocalReferenceRejected,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.infrastructure.composition.factories.local_reference import prepare_local_references
from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraftRequest,
)
from tests.support.conversation_synthetic import synthetic_target

CONTEXT = {"resource_type": "ASSESSMENT", "level": "BTS_CG_YEAR_2", "discipline": "analyse financière",
    "topics": ["bilan fonctionnel", "BFR"], "objectives": ["calculer le FRNG et le BFR", "interpréter l’équilibre financier"],
    "difficulty": "STANDARD", "duration_minutes": 60, "total_points": "20", "language": "fr"}


def request():
    return ConversationDraftRequest("req:" + "a" * 32, "conv:" + "b" * 32, "gen:" + "c" * 32,
        "Crée un contrôle BTS CG de 1 h sur le bilan fonctionnel et le BFR, noté sur 20.",
        ConfirmedConversationContext(CONTEXT))


def test_local_application_agents_projection_no_dispatch(tmp_path, monkeypatch):
    from backend.adapters.outbound.generation.conversation import NoGenerationDispatch
    from backend.agent_runtime.agents.generation import GenerationCoordinator
    def forbidden(*args, **kwargs):
        pytest.fail("Generation dispatch forbidden")
    monkeypatch.setattr(NoGenerationDispatch, "generate", forbidden)
    monkeypatch.setattr(GenerationCoordinator, "execute", forbidden)
    target = synthetic_target(tmp_path / "copy")
    before = target.runtime_path.read_bytes()
    result = prepare_local_references(target, request=request(), queries=("bilan fonctionnel", "BFR"))
    assert result["status"] == "READY_NOT_SENT"
    assert not result["production_created"]
    assert result["provider_calls"] == result["count_calls"] == result["provider_credential_resolved"] == 0
    assert "GenerationCoordinator.prepare" in result["trace"]
    assert "EvidenceAgent.search_evidence" in result["trace"]
    assert "EvidenceAgent.build_evidence_set" in result["trace"]
    assert result["projection"]["pedagogical_context"] == CONTEXT
    for item in result["provenance"]:
        assert item["excerpt_sha256"] == hashlib.sha256(item["excerpt"].encode()).hexdigest()
        assert not item["official_authority_attested"] and not item["external_file_opened"]
    assert all(r["provenance_label"].startswith("REFERENCE_LOCALE_R5_V1") for r in result["references"])
    assert target.runtime_path.read_bytes() == before
    assert not target.runtime_path.with_name(target.runtime_path.name + "-wal").exists()


def test_exact_selection_rechecked_and_stale_selection_rejected(tmp_path):
    target = synthetic_target(tmp_path / "copy")
    result = prepare_local_references(target, request=request(), queries=("bilan fonctionnel",))
    ref = result["provenance"][0]
    selection = [{"query": "bilan fonctionnel", "passage_ref": ref["locator"], "version_or_checksum": ref["version_or_checksum"]}]
    assert prepare_local_references(target, request=request(), queries=("bilan fonctionnel",), selection=selection)["selection_mode"] == "EXPLICIT"
    selection[0]["version_or_checksum"] = "0" * 64
    with pytest.raises(LocalReferenceRejected, match="REFERENCE_SELECTION_MISSING"):
        prepare_local_references(target, request=request(), queries=("bilan fonctionnel",), selection=selection)


def test_wrong_hash_rejected_before_sqlite_open(tmp_path, monkeypatch):
    import backend.infrastructure.composition.factories.local_reference as module
    target = synthetic_target(tmp_path / "copy")
    def forbidden(*args, **kwargs):
        pytest.fail("SQLite opened before hash verification")
    monkeypatch.setattr(module, "connect_sqlite", forbidden)
    with pytest.raises(ValueError):
        prepare_local_references(replace(target, expected_sha256="0" * 64), request=request(), queries=("BFR",))


def test_content_requires_read_only_snapshot(tmp_path):
    target = synthetic_target(tmp_path / "copy")
    with closing(connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)) as connection:
        with pytest.raises(LocalReferenceRejected):
            LocalReferenceContentAdapter(connection).materialize({}, evidence_id="x")


def test_private_export_manifest_and_fresh_only(tmp_path, capsys):
    target = synthetic_target(tmp_path / "copy")
    source = tmp_path / "request.json"
    source.write_text(json.dumps({"brief": request().brief, "context": CONTEXT, "queries": ["bilan fonctionnel"]}), encoding="utf-8")
    output = tmp_path / "private-export"
    sha = execute(target=target, request_path=source, output=output)
    assert sha == hashlib.sha256((output / "MANIFEST_SHA256.txt").read_bytes()).hexdigest()
    for line in (output / "MANIFEST_SHA256.txt").read_text().splitlines():
        digest, name = line.split("  ")
        assert digest == hashlib.sha256((output / name).read_bytes()).hexdigest()
    assert capsys.readouterr().out == ""
    with pytest.raises(ValueError, match="FRESH_OUTPUT_REQUIRED"):
        execute(target=target, request_path=source, output=output)
    assert main(["--runtime", str(target.runtime_path), "--data-root", str(target.data_root),
        "--runtime-sha256", target.expected_sha256, "--request", str(source), "--output", str(output)]) == 1
    assert capsys.readouterr().out == "R5_REFERENCE_PREPARATION_REJECTED\n"


@pytest.mark.parametrize("queries", [("absentxyznever",), ("BFR", "BFR"), (), ("a", "b", "c", "d")])
def test_empty_absent_duplicate_or_over_limit_rejected(tmp_path, queries):
    with pytest.raises(LocalReferenceRejected):
        prepare_local_references(synthetic_target(tmp_path / "copy"), request=request(), queries=queries)
