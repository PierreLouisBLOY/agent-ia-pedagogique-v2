"""All source-matrix cells through the composed Application lifecycle, no provider.

These are guided local projections of the existing exact R6 anchors. They do
not establish normal UI creation, pedagogical suitability or free generation.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    build_saved_application,
)
from backend.infrastructure.composition.factories.r6_p0 import (
    R6_EXACT_SOURCE_BINDINGS,
    load_p0_exact_reference,
)
from backend.modules.pedagogical_design.application.commands.create_p0_candidate import (
    CreateP0Candidate,
    ReviseP0Candidate,
)
from tests.integration.test_r6_u1_exact_source_application import (
    _candidate_data,
    _ids,
    _saved,
)

LEVELS = ("FIRST_STMG", "FINAL_STMG", "BTS_CG_YEAR_1", "BTS_CG_YEAR_2")
FAMILIES = (("COURSE", None), ("EXERCISE", None),
            ("QUESTION_SET", "OPEN_QUESTIONS"), ("QUESTION_SET", "QCM"),
            ("QUESTION_SET", "QUIZ"), ("ASSESSMENT", None))
CELLS = tuple((index, level, kind, mode)
              for index, (level, (kind, mode)) in enumerate(
                   (level, family) for level in LEVELS for family in FAMILIES ))


def _source_scenario(level: str, kind: str, mode: str | None) -> str:
    if level == "FIRST_STMG":
        return "R6-S01" if kind == "COURSE" else "R6-S02"
    if level == "FINAL_STMG":
        return "R6-S04" if mode == "QUIZ" else "R6-S03"
    if level == "BTS_CG_YEAR_1":
        return "R6-S07" if mode == "OPEN_QUESTIONS" else "R6-S05"
    return "R6-S06"


def _text(payload: bytes) -> str:
    with ZipFile(BytesIO(payload)) as archive:
        assert archive.testzip() is None
        root = ElementTree.fromstring(archive.read("word/document.xml"))
        return "\n".join(root.itertext())


@pytest.mark.parametrize("index,level,kind,mode", CELLS,
                         ids=[f"matrix_{cell[0]:02d}" for cell in CELLS])
def test_exact_matrix_cell_application_lifecycle(
    tmp_path: Path, index: int, level: str, kind: str, mode: str | None,
) -> None:
    configured = os.environ.get("PROJET_V2_CANONICAL_DB")
    assert configured, "P0_REAL_SOURCE_PRECONDITION_REQUIRED"
    seed = Path(configured)
    target = Read15RuntimeTarget(seed, seed.parent,
        "9d64d15e9c246924edeff16e7bbb5fb7a53791fc2ddf217541824771b34053e1")
    source_scenario = _source_scenario(level, kind, mode)
    binding = next(b for b in R6_EXACT_SOURCE_BINDINGS if source_scenario in b.scenarios)
    loaded = load_p0_exact_reference(target, resource_ref=binding.resource_ref,
                                    resource_version_ref=binding.resource_version_ref)
    reference = loaded["reference"]
    assert isinstance(reference, Mapping)
    evidence = {str(reference["evidence_id"]): str(loaded["evidence"])}
    name = f"P0-RECIPE-MATRIX-{index:02d}"
    data = _candidate_data(name, kind, mode, level, loaded)
    if kind == "ASSESSMENT":
        marking = data["marking"]
        assert isinstance(marking, list)
        if len(marking) == 1:
            marking[0]["points"] = "20.00"
    data["limitations"] = [*data["limitations"],
        "Projection locale guidée de recette ; aucune génération ni acceptation pédagogique.",
        "Options et durée/points de recette sont des conventions locales, non des données officielles."]
    parent = CreateP0Candidate().execute(data, evidence=evidence)
    original_sha = parent.sha256
    record = _saved(parent)
    records = {parent.version_ref: record}

    def source(production: str, version: str):
        result = records[version]
        assert result.production_ref == production
        return result

    root = tmp_path / "saved"
    app = build_saved_application(root, create=True, source=source)
    saved = app.execute("save", body={"production_ref":parent.production_ref,
                        "version_ref":parent.version_ref}, correlation="p0.matrix.save")
    assert isinstance(saved, dict) and saved["record_sha256"] == record.sha256
    assert saved["created"] is True
    reopened_app = build_saved_application(root)
    opened = reopened_app.execute("open", parent.production_ref, parent.version_ref,
                                  correlation="p0.matrix.reopen")
    assert isinstance(opened, dict) and opened["record_sha256"] == record.sha256
    assert opened["active_authority"] == "NONE_RESTORED"
    assert parent.student_projection().keys().isdisjoint({"corrections", "marking"})
    kinds = ["student"] + ([] if kind == "COURSE" else ["correction"])
    if kind == "ASSESSMENT":
        kinds.append("marking")
    for projection in kinds:
        preview = reopened_app.execute("preview", parent.production_ref, parent.version_ref,
            kind=projection, correlation="p0.matrix.preview")
        payload = reopened_app.execute("word", parent.production_ref, parent.version_ref,
            kind=projection, correlation="p0.matrix.word")
        assert isinstance(preview, dict) and isinstance(payload, bytes)
        content = _text(payload)
        assert all(str(block["text"]) in content for block in preview["blocks"])
    if kind == "COURSE":
        with pytest.raises(ValueError, match="R4_EXPORT_KIND"):
            reopened_app.execute("word", parent.production_ref, parent.version_ref,
                kind="correction", correlation="p0.matrix.no.correction")

    child_data = parent.mutable_copy()
    child_data["version_ref"] = _ids(name+"-REV")["version_ref"]
    child_data["lineage"]["parent_version_ref"] = parent.version_ref
    if kind == "COURSE":
        child_data["sections"][0]["heading"] += " — lecture guidée"
    else:
        child_data["questions"][0]["prompt"] += " Justifiez les étapes de votre réponse."
        child_data["corrections"][0]["rationale"] += " La justification est attendue."
        if kind == "ASSESSMENT":
            child_data["marking"][0]["criteria"][0] += " avec justification"
    child = ReviseP0Candidate().execute(parent, child_data, evidence=evidence)
    child_record = _saved(child)
    records[child.version_ref] = child_record
    app.execute("save", body={"production_ref":child.production_ref,
                "version_ref":child.version_ref}, correlation="p0.matrix.child.save")
    final_app = build_saved_application(root)
    assert parent.sha256 == original_sha
    for expected in (record, child_record):
        result = final_app.execute("open", expected.production_ref, expected.version_ref,
                                  correlation="p0.matrix.final.open")
        assert isinstance(result, dict) and result["record_sha256"] == expected.sha256
    validation = final_app.execute("validate", child.production_ref, child.version_ref,
        body={"action_id":_ids(name)["action_id"],"record_sha256":child_record.sha256},
        correlation="p0.matrix.child.validate")
    assert isinstance(validation, dict) and validation["report"]["status"] == "PASS"
    assert validation["report"]["promotion"] == "NOT_PERFORMED"
    with pytest.raises(ValueError, match="R4_VALIDATION_REQUIRED"):
        final_app.execute("gate", child.production_ref, child.version_ref,
                          correlation="p0.matrix.no.promotion")
    target.validate()
