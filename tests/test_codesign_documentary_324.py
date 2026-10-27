"""Closure of the independent review findings; all authorities/data synthetic."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.work_orchestration.contracts.dto.p0_codesign_trace import variant_witness
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from tests.focus_323d_fixture import focus_dispatch
from tests.test_case_study_324 import case_blueprint
from tests.test_codesign_global_324 import composition, simple
from tests.test_codesign_safety_324 import command


@pytest.mark.parametrize(
    "location", ("runs", "cycles", "retrieval", "controls", "summary", "wrong_production")
)
def test_deep_trace_tampering_rejected_even_with_recomputed_documentary_witness(location):
    dispatch, content = simple()
    service, _, _ = composition(dispatch, content, correction=True)
    result = service.execute("codesign", command(service.records[dispatch["version_ref"]]))
    record = service.saved_source(result["view"]["production_ref"], result["view"]["version_ref"])
    changed = record.mutable_copy()
    doc = changed["codesign"]
    trace = doc["trace"]
    if location == "runs":
        trace["runs"][0]["extra"] = True
    elif location == "cycles":
        trace["runs"][0]["cycles"][0]["extra"] = True
    elif location == "retrieval":
        trace["retrieval"][0]["extra"] = True
    elif location == "controls":
        trace["operations"][0]["controls"]["extra"] = True
    elif location == "summary":
        trace["operations"][1]["correction"]["change_summary"] = {"hidden": "object"}
    else:
        trace["productions"][0]["production_ref"] = "prod:" + "f" * 32
    doc["witness_sha256"] = variant_witness(
        record.p0_bundle, doc["parent_bundle_sha256"], doc["parent_record_sha256"], trace
    )
    with pytest.raises(ValueError):
        SavedProduction(changed)


def test_parent_reservations_and_own_generation_diagnostics_are_retained():
    dispatch, content = simple()
    service, generation, _ = composition(dispatch, content)
    parent = service.records[dispatch["version_ref"]]
    service.generation_controls[parent.version_ref] = {
        "contract_id": "SYNTHETIC_ROOT_CONTROL_NOT_AN_ADMISSION"
    }
    original = generation.generate

    def warned(*, request):
        return replace(
            original(request=request),
            warnings=({"code": "SYNTHETIC_OWN_WARNING"},),
            uncertainties=({"code": "SYNTHETIC_OWN_UNCERTAINTY"},),
            execution_metadata={"synthetic_usage": 3},
        )

    generation.generate = warned
    result = service.execute("codesign", command(parent))
    record = service.saved_source(result["view"]["production_ref"], result["view"]["version_ref"])
    assert "SOURCE_USAGE_NOT_DECLARED" in record.data["reservations"]
    own = record.data["codesign"]["trace"]["operations"][0]["controls"]
    assert "SYNTHETIC_OWN_WARNING" in own["warnings_json"]
    assert "SYNTHETIC_OWN_UNCERTAINTY" in own["uncertainties_json"]
    assert json.loads(own["execution_metadata_json"]) == {"synthetic_usage": 3}
    assert "GENERATION_CONTROL_SHA256" not in record.data["provenance"]


def test_explained_course_professor_support_uses_same_course_without_invented_answers(tmp_path):
    dispatch, content = simple("COURSE")
    service, _, _ = composition(dispatch, content)
    parent = service.records[dispatch["version_ref"]]
    result = service.execute("codesign", command(parent))
    view = result["view"]
    saved = build_saved_application(
        tmp_path / "SYNTHETIC-course",
        create=True,
        source=service.saved_source,
        word_profile="product-v7",
    )
    saved.execute(
        "save",
        body={"production_ref": view["production_ref"], "version_ref": view["version_ref"]},
        correlation="synthetic-save",
    )
    student = saved.execute(
        "preview",
        view["production_ref"],
        view["version_ref"],
        kind="student",
        correlation="synthetic-student",
    )
    teacher = saved.execute(
        "preview",
        view["production_ref"],
        view["version_ref"],
        kind="correction",
        correlation="synthetic-teacher",
    )
    assert teacher["title"].endswith("Support professeur") and "Corrigé" not in teacher["title"]
    for block in student["blocks"]:
        assert block in teacher["blocks"]
    assert "Revue IA" in json.dumps(teacher, ensure_ascii=False)
    assert service.records[view["version_ref"]].data["corrections"] == ()
    with pytest.raises(ValueError, match="R4_EXPORT_KIND"):
        saved.execute(
            "word",
            parent.production_ref,
            parent.version_ref,
            kind="correction",
            correlation="legacy-unchanged",
        )


def synthetic_admitted(dispatch):
    from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
        ADMITTED_DOCUMENTS,
        OWNER_ADMISSION_SHA256,
    )

    candidate, sha = next(iter(ADMITTED_DOCUMENTS.items()))
    resolution = dispatch["context"]["institutional_resolution"]
    resolution.update(
        status="RESOLVED_ADMITTED",
        gaps=[],
        attachments=[],
        version_label="SYNTHETIC_INTEGRATION_ONLY",
        owner_admission_sha256=OWNER_ADMISSION_SHA256,
        qualification_sha256="d" * 64,
        document_provenance={"candidate_id": candidate, "sha256": sha},
    )
    context = P0Context(dispatch["context"])
    dispatch["context_sha256"] = dispatch["lineage"]["context_sha256"] = context.sha256
    return dispatch


@pytest.mark.parametrize("case", (False, True))
def test_specialized_exercise_is_wholly_reviewed_and_student_compare_uses_export_projection(
    tmp_path, case
):
    dispatch, content = case_blueprint() if case else focus_dispatch()
    dispatch = synthetic_admitted(dispatch)
    service, generation, review = composition(dispatch, content)
    parent = service.records[dispatch["version_ref"]]
    proposed = deepcopy(content)
    ref = dispatch["references"][0]
    proposed["exercise"]["documents"][0].update(
        provenance="SUPPLIED_REFERENCE",
        evidence_id=ref["evidence_id"],
        text=dispatch["evidence"][ref["evidence_id"]],
    )
    if case:
        proposed["exercise"]["case_study"]["data"][0].update(
            kind="DOCUMENTED_FACT",
            text=dispatch["evidence"][ref["evidence_id"]],
            quote=dispatch["evidence"][ref["evidence_id"]],
        )
        proposed["exercise"]["case_study"]["organizations"][0]["label"] = "perception"
    generation.content = proposed
    result = service.execute("codesign", command(parent))
    assert result["state"] == "CODESIGN_CANDIDATE", result
    assert "teacher_answers" in review.calls[0].target_payload["exercise"]
    assert (
        review.calls[0].target_payload["exercise"]["objectives"][0]["learning_objective_ref"]
        == "C1"
    )
    assert "capability_id" not in review.calls[0].target_payload["exercise"]["objectives"][0]
    assert "https://" in json.dumps(dict(review.calls[0].target_payload["supplied_evidence"][1]))
    assert "passages" not in review.calls[0].resolved_inputs
    assert "URL_PRESENT" in json.dumps(result["trace"]["reports"], ensure_ascii=False)
    if case:
        assert "case_study" in review.calls[0].target_payload["exercise"]
    saved = build_saved_application(
        tmp_path / "SYNTHETIC-specialized",
        create=True,
        source=service.saved_source,
        word_profile="product-v7",
    )
    view = result["view"]
    saved.execute(
        "save",
        body={"production_ref": view["production_ref"], "version_ref": view["version_ref"]},
        correlation="synthetic-save",
    )
    compared = saved.execute(
        "compare",
        view["production_ref"],
        view["version_ref"],
        kind="student",
        correlation="synthetic-compare",
    )
    serialized = json.dumps(compared, ensure_ascii=False)
    assert (
        "evidence:" not in serialized
        and "SUPPLIED_REFERENCE" not in serialized
        and "teacher_answers" not in serialized
    )


@pytest.mark.parametrize(
    "path",
    (
        ["exercise"],
        ["exercise", "objectives"],
        ["exercise", "objectives", 0, "learning_objective_ref"],
    ),
)
def test_pedagogical_objective_alias_and_ancestors_cannot_authorize_correction(path):
    from backend.adapters.outbound.generation.openai.p0_content import bind_p0_content
    from backend.modules.work_orchestration.contracts.dto.p0_codesign_trace import correction_paths

    dispatch, content = focus_dispatch()
    bundle = bind_p0_content(dispatch, content)
    with pytest.raises(ValueError, match="P0_CODESIGN_OBJECTIVES_IMMUTABLE"):
        correction_paths(
            bundle,
            {
                "findings": [
                    {
                        "correction_required": True,
                        "target_locator": {"kind": "json_path", "path": path},
                    }
                ]
            },
        )
