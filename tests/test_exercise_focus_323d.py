"""Local focus is explicit and pinned; it grants no admission or send authority."""

from copy import deepcopy

import pytest

from backend.adapters.outbound.generation.openai.p0_content import (
    bind_p0_content,
    build_p0_content_request,
)
from backend.modules.materialization_export.application.services.exercise_projection import (
    project_exercise,
)
from backend.modules.pedagogical_context.contracts.dto.exercise_context import exercise_focus
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService
from tests.focus_323d_fixture import LOCAL_LABEL, SOURCE_LABEL, focus_dispatch


def test_full_native_object_remains_intact_and_local_question_is_distinct():
    d, _ = focus_dispatch()
    original = deepcopy(d["context"]["institutional_resolution"])
    typed = P0Context(d["context"])
    focus = exercise_focus(typed.data)
    assert focus["question_label"] == LOCAL_LABEL
    assert focus["source_question_label"] == SOURCE_LABEL
    assert focus["source_question_sha256"] == fingerprint(original["question"])
    assert typed.as_dict()["institutional_resolution"] == original
    assert focus["institutional_status"] == "CONTENT_GAP"
    with pytest.raises(ValueError, match="EXERCISE_INSTITUTIONAL_ADMISSION_REQUIRED"):
        build_p0_content_request(d)


@pytest.mark.parametrize(
    "fault,code",
    [
        ("hash", "EXERCISE_FOCUS_SOURCE_CHANGED"),
        ("metadata", "EXERCISE_FOCUS_SOURCE_CHANGED"),
        ("ref", "EXERCISE_FOCUS_SOURCE_BINDING"),
        ("type", "EXERCISE_FOCUS_SOURCE_BINDING"),
        ("version", "EXERCISE_FOCUS_SOURCE_BINDING"),
        ("authority", "EXERCISE_FOCUS_LOCAL_AUTHORITY"),
        ("substring", "EXERCISE_FOCUS_COMPONENT_NOT_UNIQUE"),
        ("absent", "EXERCISE_FOCUS_COMPONENT_NOT_UNIQUE"),
        ("duplicate", "EXERCISE_FOCUS_COMPONENT_NOT_UNIQUE"),
        ("suffix", "EXERCISE_FOCUS_SOURCE_PARTITION"),
        ("empty", "P0_CONTEXT_TEXT"),
        ("truncated", "EXERCISE_FOCUS_COMPONENT"),
        ("blank_component", "EXERCISE_FOCUS_COMPONENT"),
        ("source_blank_component", "EXERCISE_FOCUS_SOURCE_PARTITION"),
    ],
)
def test_focus_refusals(fault, code):
    d, _ = focus_dispatch()
    c = d["context"]
    q = c["institutional_resolution"]["question"]
    f = c["exercise_focus_selection"]
    if fault == "hash":
        f["source_question_sha256"] = "a" * 64
    elif fault == "metadata":
        q["position"] = 2
    elif fault == "ref":
        f["source_question_ref"] = "other"
    elif fault == "type":
        q["element_type"] = "THEME"
    elif fault == "version":
        q["framework_version_id"] = "other"
    elif fault == "authority":
        f["authority"] = "OFFICIAL"
    elif fault == "substring":
        f["local_question_label"] = "un individu devient-il acteur dans une organisation ?"
    elif fault == "absent":
        f["local_question_label"] = "Question absente ?"
    elif fault == "duplicate":
        q["official_label"] = LOCAL_LABEL + " " + LOCAL_LABEL
        f["source_question_sha256"] = fingerprint(q)
    elif fault == "suffix":
        q["official_label"] += " suffixe non couvert"
        f["source_question_sha256"] = fingerprint(q)
    elif fault == "empty":
        c["exercise_focus_justification"] = ""
    elif fault == "truncated":
        f["local_question_label"] = LOCAL_LABEL[:-1]
    elif fault == "blank_component":
        f["local_question_label"] = "?"
    elif fault == "source_blank_component":
        q["official_label"] += " ?"
        f["source_question_sha256"] = fingerprint(q)
    with pytest.raises(ValueError, match=code):
        P0Context(c)


@pytest.mark.parametrize("fault", ["missing", "extra", "wrong_type", "foreign_family"])
def test_closed_selection_and_family_even_before_resolution(fault):
    d, _ = focus_dispatch()
    c = d["context"]
    c["institutional_resolution"] = None
    if fault == "missing":
        del c["exercise_focus_selection"]["authority"]
    elif fault == "extra":
        c["exercise_focus_selection"]["unknown"] = "not allowed"
    elif fault == "wrong_type":
        c["exercise_focus_selection"]["source_question_ref"] = {"unexpected": "object"}
    else:
        c["resource_type"] = "COURSE"
    with pytest.raises(ValueError):
        P0Context(c)


def test_old_context_does_not_gain_focus_or_accept_a_compound_question():
    d, _ = focus_dispatch()
    c = d["context"]
    c["contract_id"] = "P0-CONTEXT-EXERCISE-1.0"
    del c["exercise_focus_selection"]
    with pytest.raises(ValueError, match="EXERCISE_SINGLE_QUESTION_BINDING"):
        P0Context(c)


def test_prepare_reloads_source_and_never_replaces_a_failed_expected_pin():
    d, _ = focus_dispatch()
    c = d["context"]
    resolved = deepcopy(c["institutional_resolution"])
    c["institutional_resolution"] = None
    resolved["question"]["official_text"] = "CHANGED_AFTER_SELECTION"
    calls = []
    service = P0CreationService(
        lambda _: calls.append("reference-must-not-load"),
        institutional_resolver=lambda *_: resolved,
        focused_institutional_resolver=lambda *_: resolved,
    )
    with pytest.raises(ValueError, match="EXERCISE_FOCUS_SOURCE_CHANGED"):
        service.execute(
            "prepare",
            {"command_id": "d" * 32, "context": c, "reference": {"notion_id": "synthetic"}},
        )
    assert service.prepared == {} and calls == []


def test_focus_has_no_native_fallback_in_local_reference_profile():
    from backend.infrastructure.composition.factories.p0_product_consent import (
        product_source_reader,
    )

    d, _ = focus_dispatch()
    c = d["context"]
    c["institutional_resolution"] = None

    def forbidden(*_):
        raise AssertionError("MUST_NOT_READ_OR_RESOLVE")

    service = P0CreationService(forbidden, institutional_resolver=forbidden)
    with pytest.raises(ValueError, match="EXERCISE_FOCUS_RESOLVER_REQUIRED"):
        service.execute("prepare", {"command_id": "d" * 32, "context": c, "reference": {}})
    read = product_source_reader(target=None, admission=None, institutional_resolver=forbidden)
    with pytest.raises(ValueError, match="EXERCISE_FOCUS_LOCAL_REFERENCE_CONTEXT_UNSUPPORTED"):
        read({"context": c})


def test_production_and_both_projections_bind_the_explicit_context():
    d, c = focus_dispatch()
    bundle = bind_p0_content(d, c)
    assert bundle.context.data["contract_id"] == "P0-CONTEXT-EXERCISE-1.1"
    student, teacher = (project_exercise(bundle, kind) for kind in ("student", "correction"))
    assert student.exercise_content["header"]["question"] == LOCAL_LABEL
    assert not any(
        SOURCE_LABEL in b.text or "Empreinte de la question source" in b.text
        for b in student.blocks
    )
    assert any(SOURCE_LABEL in b.text for b in teacher.blocks)
    assert any("sans relation officielle plus étroite" in b.text for b in teacher.blocks)
    from io import BytesIO
    from zipfile import ZipFile

    from backend.adapters.outbound.export.course_word import CourseOOXMLWordWriter

    with ZipFile(BytesIO(CourseOOXMLWordWriter().write(teacher))) as archive:
        printed = archive.read("word/document.xml").decode()
    assert "question institutionnelle complète et empreinte conservées dans V2" in printed
    assert SOURCE_LABEL not in printed
    assert all(text in printed for text in bundle.data["limitations"])


def test_native_catalog_hash_is_opt_in_and_covers_unprojected_metadata(monkeypatch):
    from backend.modules.knowledge_reference.application.queries.stmg_alignment import (
        ReadSTMGAlignment,
    )
    from tests.normal_focus_323d_fixture import install

    f = install(monkeypatch)
    catalog = f.Catalog()
    reader = ReadSTMGAlignment(catalog)
    historical = reader.snapshot()
    enhanced = reader.snapshot(question_fingerprints=True)
    stripped = deepcopy(enhanced)
    for frame in stripped["frames"]:
        for q in frame["questions"]:
            assert len(q.pop("source_question_sha256")) == 64
    assert stripped == historical
    question = next(
        q for q in catalog.data["official_framework_element"] if q["id"] == "question:SGN_PREMIERE"
    )
    expected = fingerprint(question)
    row = next(fr for fr in enhanced["frames"] if fr["frame"] == "SGN_PREMIERE")["questions"][0]
    assert row["source_question_sha256"] == expected
    question["position"] += 1
    changed = next(
        fr
        for fr in reader.snapshot(question_fingerprints=True)["frames"]
        if fr["frame"] == "SGN_PREMIERE"
    )["questions"][0]
    assert changed["source_question_sha256"] != expected and changed["label"] == row["label"]


@pytest.mark.parametrize(
    "fault", [None, "foreign", "version", "absent", "pin", "selection", "scope_version"]
)
def test_real_resolver_child_scope_is_explicit_and_bound(monkeypatch, fault):
    from backend.modules.knowledge_reference.application.queries.stmg_alignment import (
        ReadSTMGAlignment,
    )
    from tests.normal_focus_323d_fixture import install

    f = install(monkeypatch)
    catalog = f.Catalog()
    c = f.context()
    q = next(
        e for e in catalog.data["official_framework_element"] if e["id"] == "question:SGN_PREMIERE"
    )
    child = {**q, "id": "child:SYNTHETIC", "parent_element_id": q["id"], "element_type": "CONCEPT"}
    if fault == "foreign":
        child["parent_element_id"] = "foreign:QUESTION"
    if fault == "version":
        child["framework_version_id"] = "foreign:VERSION"
    if fault != "absent":
        catalog.data["official_framework_element"].append(child)
    for a in catalog.data["institutional_attachment"]:
        if a["framework_element_id"] == q["id"]:
            a["framework_element_id"] = child["id"]
    query = ReadSTMGAlignment(catalog)
    reference = {**f.SOURCE, "notion_id": "notion:shared"}
    legacy = query.resolve(c["institutional"], reference)
    assert "exercise_attachment_scope" not in legacy
    resolved = query.resolve(c["institutional"], reference, focus_witness=True)
    assert {k: v for k, v in resolved.items() if k != "exercise_attachment_scope"} == legacy
    # The synthetic catalog is not the qualified native corpus; its normal
    # source-port fixture separately declares this capacity scope.
    resolved["capacity_scope"] = "SELECTED_THEME_OR_QUESTION_NO_NARROWER_CLAIM"
    if fault == "pin":
        resolved["exercise_attachment_scope"]["source_question_sha256"] = "a" * 64
    if fault == "selection":
        resolved["exercise_attachment_scope"]["selection_sha256"] = "a" * 64
    if fault == "scope_version":
        resolved["exercise_attachment_scope"]["program_version"] = "other"
    c["institutional_resolution"] = resolved
    if fault is None:
        P0Context(c)
        del resolved["exercise_attachment_scope"]
        with pytest.raises(ValueError, match="EXERCISE_FOCUS_RELATION_MISSING"):
            P0Context(c)
    else:
        with pytest.raises(ValueError):
            P0Context(c)
