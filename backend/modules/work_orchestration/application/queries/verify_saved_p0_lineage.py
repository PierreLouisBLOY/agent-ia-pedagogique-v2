"""Authenticate saved parent relations, including the existing typed COURSE reframe."""
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.modules.work_orchestration.contracts.dto.p0_codesign_trace import (
    SAVED_CODESIGN_CONTRACT,
    validate_documentary,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


def verify_saved_parent(child: SavedProduction, parent: SavedProduction) -> None:
    current, original = child.p0_bundle, parent.p0_bundle
    if current is None or original is None or current.production_ref != original.production_ref:
        raise ValueError("P0_SAVED_LINEAGE_BINDING")
    lineage, old = object_data(current.data["lineage"]), object_data(original.data["lineage"])
    if lineage["parent_version_ref"] != original.version_ref:
        raise ValueError("P0_SAVED_LINEAGE_BINDING")
    from backend.modules.validation_control.application.commands.validate_p0 import (
        ValidateP0Command,
    )
    if child.data["contract_id"] == SAVED_CODESIGN_CONTRACT:
        from backend.modules.validation_control.application.commands.validate_p0 import (
            ValidateP0Command,
        )
        proof = validate_documentary(child.data["codesign"], current)
        renewable = {"source_run_id", "source_step_id", "source_request_id", "parent_version_ref"}
        report = ValidateP0Command().execute(current, parent=original)
        if (proof["parent_bundle_sha256"] != original.sha256 or proof["parent_record_sha256"] != parent.sha256
                or current.data["context"] != original.data["context"] or current.data["references"] != original.data["references"]
                or {k:v for k,v in lineage.items() if k not in renewable} != {k:v for k,v in old.items() if k not in renewable}
                or not any(fingerprint(row) == fingerprint(report) for row in items(child.data["validations"], 32))):
            raise ValueError("P0_SAVED_LINEAGE_BINDING")
        return
    if ({k: v for k, v in lineage.items() if k != "parent_version_ref"}
            == {k: v for k, v in old.items() if k != "parent_version_ref"}
            and current.data["context"] == original.data["context"]
            and current.data["references"] == original.data["references"]):
        return
    # A typed historical reframe deliberately renews context/refs and request/run/step.
    # Verify its full witnesses; a similarly named provenance key is insufficient.
    proof = object_data(child.data["provenance"])
    if (current.context.resource_type != "COURSE" or original.context.resource_type != "COURSE"
            or current.context.institutional is None
            or lineage["conversation_id"] != old["conversation_id"]
            or lineage["evidence_set_ref"] != old["evidence_set_ref"]
            or proof.get("LOCAL_EDIT_PARENT_BUNDLE_SHA256") != original.sha256
            or proof.get("LOCAL_EDIT_PARENT_RECORD_SHA256") != parent.sha256
            or proof.get("INSTITUTIONAL_RESOLUTION_SHA256") != fingerprint(current.context.data["institutional_resolution"])):
        raise ValueError("P0_SAVED_LINEAGE_BINDING")
    references = items(current.data["references"], 16)
    reference_proof = proof.get("LOCAL_REFERENCE_SUCCESSOR_SHA256")
    if reference_proof is None or reference_proof == fingerprint(None):
        if current.data["references"] != original.data["references"]:
            raise ValueError("P0_SAVED_LINEAGE_BINDING")
    elif len(references) != 1 or reference_proof != fingerprint(references[0]):
        raise ValueError("P0_SAVED_LINEAGE_BINDING")
    operation = {"mode": "EXPLICIT_LOCAL_CONTEXT_SUCCESSOR", "parent": parent.sha256,
                 "context": current.context.sha256, "title": current.data["title"],
                 "sections": as_plain(current.data["sections"]),
                 "course_chapter": as_plain(current.data.get("course_chapter"))}
    operation_sha = proof.get("LOCAL_EDIT_OPERATION_SHA256")
    if operation_sha != fingerprint(operation):
        # Exact pre-9ba651c producer (blob c5f9205f...) had no chapter parameter.
        # It copied the parent: neither side may carry a chapter in this version.
        legacy = {key: value for key, value in operation.items() if key != "course_chapter"}
        if (reference_proof is not None or "course_chapter" in current.data
                or "course_chapter" in original.data or operation_sha != fingerprint(legacy)):
            raise ValueError("P0_SAVED_LINEAGE_BINDING")
    reports = items(child.data["validations"], 32)
    if not any(report.get("contract_id") == "R6-P0-VALIDATION-1.0"
               and report.get("status") == "PASS"
               and report.get("production_ref") == current.production_ref
               and report.get("version_ref") == current.version_ref
               and report.get("bundle_sha256") == current.sha256
               and report.get("institutional_resolution_sha256") == proof["INSTITUTIONAL_RESOLUTION_SHA256"]
               and report.get("promotion") == "NOT_PERFORMED" for report in reports):
        raise ValueError("P0_SAVED_LINEAGE_BINDING")
