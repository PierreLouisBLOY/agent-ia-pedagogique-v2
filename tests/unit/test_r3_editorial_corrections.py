"""Fresh invented editorial fixtures; no pilot export or historical plan is loaded."""
import hashlib
from uuid import uuid4

import pytest

from backend.adapters.outbound.generation.openai.locator_materialization import calculation_locators
from backend.modules.pedagogical_design.application.commands.revise_assessment import (
    ReviseAssessmentCommand,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    encoded,
    items,
    locate,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    EditorialCorrectionPlan,
)
from backend.modules.validation_control.contracts.dto.editorial_scope import (
    EditorialAuthorizationEvidence,
    build_editorial_scope,
)
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import R3Command
from tests.support.r3_synthetic import CONV, V2, bundle

BASELINE = "d" * 40
CONTRACT_HASH = "c" * 64


def review_for(parent):
    return {"status": "completed", "production_ref": parent.production_ref,
            "version_ref": parent.version_ref, "bundle_sha256": parent.sha256,
            "subject_sha256": parent.data["subject_sha256"], "review_ref": "review:" + "b" * 32,
            "findings": [{"finding_id": "F-01"}, {"finding_id": "F-02"}]}


def plan_data(parent, review):
    edits = []
    for i, a in enumerate(items(object_data(parent.data["correction"])["answers"])[:2]):
        old = a["expected_answer"]
        new = "Explication artificielle 🚀 é : conserver le résultat. " + old
        edits.append({"finding_id": f"F-0{i+1}", "question_id": a["question_id"], "answer_index": i,
            "expected_answer_path": EditorialCorrectionPlan.PATHS[2*i],
            "calculation_locator_path": EditorialCorrectionPlan.PATHS[2*i+1],
            "original_expected_answer": old, "proposed_expected_answer": new,
            "original_text_sha256": hashlib.sha256(old.encode()).hexdigest(),
            "proposed_text_sha256": hashlib.sha256(new.encode()).hexdigest()})
    return {"contract": EditorialCorrectionPlan.CONTRACT, "operation": EditorialCorrectionPlan.OPERATION,
            "prepared_from_baseline_commit": BASELINE, "implementation_baseline_commit": BASELINE,
            "contract_document_sha256": CONTRACT_HASH, "production_ref": parent.production_ref,
            "parent_version_ref": parent.version_ref, "parent_bundle_sha256": parent.sha256,
            "parent_subject_sha256": parent.data["subject_sha256"],
            "review_sha256": hashlib.sha256(encoded(review)).hexdigest(), "proposal_source_sha256": "a"*64,
            "edits": edits, "changed_content_paths": list(EditorialCorrectionPlan.PATHS),
            "source_capability": None, "origin_kind": "LOCAL_DETERMINISTIC_M04",
            "locator_algorithm": "calculation_locators", "locator_source_sha256": EditorialCorrectionPlan.LOCATOR_SHA,
            "max_child_publications": 1, "provider_calls": 0, "dependency_changes": []}


def prepared(*, parent=None, review=None, conversation_id=CONV):
    parent = parent or bundle()
    review = review or review_for(parent)
    plan = EditorialCorrectionPlan(encoded(plan_data(parent, review)))
    evidence = EditorialAuthorizationEvidence(plan, conversation_id, BASELINE, CONTRACT_HASH,
                                              "9"*64, encoded(review), object())
    return parent, plan, evidence


def child_for(parent, plan, command_id=None, operation_ref=None, calculator=calculation_locators):
    command_id = command_id or str(uuid4())
    operation_ref = operation_ref or "op:" + "a" * 32
    lineage = {"operation_ref": operation_ref, "command_id": command_id, "source_capability": None,
               "parent_version_ref": parent.version_ref, "parent_bundle_sha256": parent.sha256,
               "instruction_sha256": plan.sha256, "changed_locators": list(plan.PATHS),
               "dependency_changes": []}
    return ReviseAssessmentCommand().execute_editorial(plan, parent, version_ref=V2,
        lineage=lineage, calculate_locators=calculator), command_id, operation_ref


def scope_for():
    parent, plan, evidence = prepared()
    child, command_id, operation_ref = child_for(parent, plan)
    live = {"open": True}
    scope = build_editorial_scope(evidence, parent, child, command_id=command_id,
        operation_ref=operation_ref, authenticate=lambda e: live["open"] and e is evidence,
        calculate_locators=calculation_locators)
    return parent, plan, evidence, child, scope, live


def local_command(conversation_id, revision, parent, plan, **overrides):
    body = {"conversation_id": conversation_id, "command_id": str(uuid4()), "expected_revision": revision,
            "production_ref": parent.production_ref, "base_version_ref": parent.version_ref,
            "base_bundle_sha256": parent.sha256, "operation": plan.OPERATION,
            "editorial_contract": plan.CONTRACT, "plan_sha256": plan.sha256,
            "review_sha256": plan.data["review_sha256"]}
    body.update(overrides)
    return R3Command("modifications", body)


def test_local_assembly_exact_strings_unicode_and_immutable_parent():
    parent, plan, _ = prepared()
    before = encoded(parent.data)
    child, _, _ = child_for(parent, plan)
    assert encoded(parent.data) == before
    assert child.version_ref != parent.version_ref
    for i, a in enumerate(child.data["correction"]["answers"][:2]):
        text = plan.data["edits"][i]["proposed_expected_answer"]
        assert a["expected_answer"] == text
        loc = a["calculations"][0]["locator"]
        assert locate(loc, [{"section_id": a["question_id"], "text": text}]) == loc["exact_text"]
        assert loc["start"] == text.index(loc["exact_text"])
        assert loc["start"] != len(text[:loc["start"]].encode())  # Python chars, not bytes.
    for k in ("subject", "subject_sha256", "case_data", "questions", "references", "limitations"):
        assert child.data[k] == parent.data[k]
    assert child.data["correction"]["answers"][2:] == parent.data["correction"]["answers"][2:]


@pytest.mark.parametrize("field,value", [
    ("max_child_publications", True), ("provider_calls", False), ("origin_kind", "CAP-G02"),
    ("source_capability", "CAP-G02"), ("implementation_baseline_commit", "latest"),
    ("parent_bundle_sha256", "bad"), ("changed_content_paths", ["arbitrary"]),
    ("extra", "approved"), ("locator_source_sha256", "1"*64),
])
def test_plan_closed_types_and_identities(field, value):
    parent = bundle()
    d = plan_data(parent, review_for(parent))
    d[field] = value
    with pytest.raises(ValueError):
        EditorialCorrectionPlan(encoded(d))


@pytest.mark.parametrize("mutation", ["duplicate", "bom", "nan", "scalar", "extra_edit", "hash", "index", "qid", "suffix"])
def test_plan_raw_bytes_and_exact_edits(mutation):
    parent = bundle()
    d = plan_data(parent, review_for(parent))
    if mutation == "duplicate":
        raw = b'{"contract":"a","contract":"b"}'
    elif mutation == "bom":
        raw = b"\xef\xbb\xbf" + encoded(d)
    elif mutation == "nan":
        raw = b'{"value":NaN}'
    elif mutation == "scalar":
        raw = b"null"
    else:
        if mutation == "extra_edit":
            d["edits"].append(d["edits"][0])
        elif mutation == "hash":
            d["edits"][0]["proposed_text_sha256"] = "f"*64
        elif mutation == "index":
            d["edits"][0]["answer_index"] = False
        elif mutation == "qid":
            d["edits"][1]["question_id"] = d["edits"][0]["question_id"]
        else:
            d["edits"][0]["proposed_expected_answer"] = "Replacement without suffix"
            d["edits"][0]["proposed_text_sha256"] = hashlib.sha256(
                d["edits"][0]["proposed_expected_answer"].encode()).hexdigest()
        raw = encoded(d)
    with pytest.raises(ValueError):
        EditorialCorrectionPlan(raw)


@pytest.mark.parametrize("field,value", [
    ("expected_revision", True), ("instruction", "please"), ("editorial_contract", "other"),
    ("plan_sha256", "bad"), ("review_sha256", False), ("candidate", {}), ("approved", True),
])
def test_command_closed(field, value):
    parent, plan, _ = prepared()
    with pytest.raises(ValueError):
        local_command(CONV, 1, parent, plan, **{field: value})


def test_parent_binding_and_new_version_required():
    parent, plan, _ = prepared()
    data = parent.mutable_copy()
    data["correction"]["answers"][0]["expected_answer"] += " drift"
    with pytest.raises(ValueError):
        child_for(AssessmentBundle(data), plan)
    child, cid, op = child_for(parent, plan)
    with pytest.raises(ValueError):
        ReviseAssessmentCommand().execute_editorial(plan, parent, version_ref=parent.version_ref,
            lineage=child.data["lineage"], calculate_locators=calculation_locators)


def test_locator_repeats_missing_overlap_and_wrong_calculator():
    locs = calculation_locators("q", "12.00 12.00 12.00", ("12.00", "12.00"))
    assert [x["start"] for x in locs] == [0, 6]
    for text, values in [("12.00", ("12.00", "12.00")), ("none", ("12.00",)),
                          ("112.00", ("112.00", "12.00"))]:
        with pytest.raises(ValueError):
            calculation_locators("q", text, values)
    parent, plan, _ = prepared()
    with pytest.raises(ValueError):
        child_for(parent, plan, calculator=lambda *args: ())
