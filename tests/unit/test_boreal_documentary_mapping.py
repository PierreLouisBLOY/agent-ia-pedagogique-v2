"""Synthetic artifact tests; the real historical bytes remain private and pinned."""
import hashlib
import json

import pytest

from backend.adapters.outbound.resource_library import boreal_documentary as adapter
from tests.support.r4_synthetic import record


def setup_artifacts(tmp_path, monkeypatch, *, unknown_id=False, teacher_input=False):
    source = record().mutable_copy()["view"]
    references = [{"case_reference_id": "S01", "evidence_id": "evidence:shared",
        "source_ref": "content:first", "locator": "chunk:first",
        "version_or_checksum": "a" * 64, "excerpt": "first passage",
        "excerpt_sha256": "a" * 64},
        {"case_reference_id": "S02", "evidence_id": "evidence:shared",
        "source_ref": "content:second", "locator": "chunk:second",
        "version_or_checksum": "b" * 64, "excerpt": "second passage",
        "excerpt_sha256": "b" * 64}]
    supplied = [{"source_ref": r["source_ref"], "locator": r["locator"],
                 "version_or_checksum": r["version_or_checksum"], "text": r["excerpt"]}
                for r in references]
    output = {"sections": [{"code": s["section_id"], "text": s["text"]}
                            for s in source["sections"]],
              "evidence_ids_used": ["evidence:unknown" if unknown_id else "evidence:shared"]}
    request = {"input": json.dumps({"source_step_id": "historical-generation",
        "pedagogical_context": source["pedagogical_context"],
        "resolved_inputs": {"evidence": supplied}})}
    objects = {
        "generated_output_structured.json": ("OUTPUT_SHA", output),
        "provider_response_raw.json": ("RESPONSE_SHA", {"output": [{"content": [
            {"type": "output_text", "text": json.dumps(output)}]}]}),
        "60_ATELIER_BOREAL_SOURCE_INVENTORY.json": ("INVENTORY_SHA", {
            "correction_and_marking_excluded_from_provider_input": not teacher_input,
            "selected_references": references}),
        "61_ATELIER_BOREAL_GENERATION_REQUEST.json": ("REQUEST_FILE_SHA", request),
    }
    for name, (constant, value) in objects.items():
        raw = json.dumps(value).encode()
        (tmp_path / name).write_bytes(raw)
        monkeypatch.setattr(adapter, constant, hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(adapter, "REQUEST_SHA", hashlib.sha256(json.dumps(request,
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest())


def test_shared_historical_id_maps_all_constituents_without_fabricated_attribution(tmp_path, monkeypatch):
    setup_artifacts(tmp_path, monkeypatch)
    value, mapping = adapter.normalize_boreal_documentary(tmp_path, tmp_path)
    assert len(mapping["constituents"]) == 2
    assert len(value.view.data["references"]) == 1
    assert value.data["bundle"] is None
    assert value.data["origin"] == "IMPORTED_DOCUMENTARY"
    assert mapping["solving_score"] is None


@pytest.mark.parametrize("mutation", ["unknown_id", "teacher_input", "bytes"])
def test_lineage_teacher_input_and_byte_mutations_are_rejected(tmp_path, monkeypatch, mutation):
    setup_artifacts(tmp_path, monkeypatch, unknown_id=mutation == "unknown_id",
                    teacher_input=mutation == "teacher_input")
    if mutation == "bytes":
        path = tmp_path / "generated_output_structured.json"
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="BOREAL_DOCUMENTARY_"):
        adapter.normalize_boreal_documentary(tmp_path, tmp_path)
