"""Documentary co-design witnesses. No runtime types or restored authority."""
import re
from collections.abc import Mapping
from copy import deepcopy
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.quality_evaluation.contracts.dto.p0_review_report import (
    validate_p0_review_binding,
)

SAVED_CODESIGN_CONTRACT = "SAVED-PRODUCTION-P0-CODESIGN-1.0"
DOCUMENTARY_CONTRACT = "P0-CODESIGN-DOCUMENTARY-1.0"


def _text(value: object, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("P0_CODESIGN_DOCUMENTARY_TYPE")
    return value


def _strings(value: object, maximum: int, *, required: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or not int(required) <= len(value) <= maximum:
        raise ValueError("P0_CODESIGN_DOCUMENTARY_TYPE")
    result = tuple(_text(item) for item in value)
    if len(result) != len(set(result)):
        raise ValueError("P0_CODESIGN_DOCUMENTARY_DUPLICATE")
    return result


def _hash(value: object) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("P0_CODESIGN_DOCUMENTARY_HASH")


def _validate_runs_and_retrieval(trace: Mapping[str, object]) -> None:
    seen_runs: set[str] = set()
    for run in items(trace["runs"], 2):
        object_data(run, {"run_id", "workflow_kind", "parent_run_id", "source_sha256", "result_sha256",
                          "shared_envelope", "cycles", "state", "completion_reason"})
        run_id = _text(run["run_id"], 36)
        if re.fullmatch(r"run:[0-9a-f]{32}", run_id) is None or run_id in seen_runs:
            raise ValueError("P0_CODESIGN_DOCUMENTARY_RUNS")
        seen_runs.add(run_id)
        if run["parent_run_id"] is not None:
            _text(run["parent_run_id"], 36)
        for field in ("source_sha256", "result_sha256"):
            _hash(run[field])
        if (run["shared_envelope"] is not True or run["state"] not in {"succeeded", "partial"}
                or run["workflow_kind"] not in {"WF-6", "WF-7"}):
            raise ValueError("P0_CODESIGN_DOCUMENTARY_RUNS")
        _text(run["completion_reason"], 100)
        cycles = items(run["cycles"], 8)
        if not cycles:
            raise ValueError("P0_CODESIGN_DOCUMENTARY_RUNS")
        launched: list[str] = []
        for cycle in cycles:
            object_data(cycle, {"launched", "completed", "directives", "coordination"})
            started = _strings(cycle["launched"], 4)
            completed = _strings(cycle["completed"], 4)
            directives = _strings(cycle["directives"], 8)
            if (not set(completed) <= set(started) or any(re.fullmatch(r"step:[0-9a-f]{32}", ref) is None for ref in started)
                    or any(code != "CONTINUE" for code in directives)
                    or cycle["coordination"] not in {"CONTINUE", "COMPLETE"}):
                raise ValueError("P0_CODESIGN_DOCUMENTARY_CYCLE")
            launched.extend(started)
        if len(launched) != len(set(launched)):
            raise ValueError("P0_CODESIGN_DOCUMENTARY_CYCLE")
    for row in items(trace["retrieval"], 8):
        object_data(row, {"source_ref", "locator", "version", "selection"})
        for field in ("source_ref", "locator", "version"):
            _text(row[field], 1000)
        if row["selection"] != "NOT_ADMITTED_BY_DISCOVERY":
            raise ValueError("P0_CODESIGN_DOCUMENTARY_RETRIEVAL")


def _validate_controls(value: object, bundle_sha: str, evidence_ids: set[str]) -> None:
    controls = object_data(value, {"guard_disposition", "guard_signals", "warnings_json", "uncertainties_json", "execution_metadata_json",
        "provided_evidence_refs", "declared_evidence_refs_used", "source_usage_declaration", "bundle_sha256"})
    if (controls["bundle_sha256"] != bundle_sha or controls["guard_disposition"] not in {"ALLOW", "ALLOW_WITH_WARNINGS"}
            or controls["source_usage_declaration"] != "TECHNICAL_DECLARATION_NOT_VALIDATION"):
        raise ValueError("P0_CODESIGN_DOCUMENTARY_CONTROLS")
    if set(_strings(controls["provided_evidence_refs"], 8, required=True)) != evidence_ids:
        raise ValueError("P0_CODESIGN_DOCUMENTARY_CONTROLS")
    if not set(_strings(controls["declared_evidence_refs_used"], 8)) <= evidence_ids:
        raise ValueError("P0_CODESIGN_DOCUMENTARY_CONTROLS")
    for field in ("warnings_json", "uncertainties_json", "execution_metadata_json"):
        _text(controls[field], 16384)
    for signal in items(controls["guard_signals"], 32):
        object_data(signal, {"code", "location"})
        _text(signal["code"], 100)
        _text(signal["location"], 1000)


def validate_documentary(value: object, bundle: P0Production) -> dict[str, object]:
    data = object_data(value, {"contract_id", "trace", "parent_bundle_sha256", "parent_record_sha256", "witness_sha256"})
    if data["contract_id"] != DOCUMENTARY_CONTRACT:
        raise ValueError("P0_CODESIGN_DOCUMENTARY_CONTRACT")
    for field in ("parent_bundle_sha256", "parent_record_sha256", "witness_sha256"):
        _hash(data[field])
    trace = object_data(data["trace"], {"productions", "reports", "runs", "retrieval", "operations", "correction", "pedagogical_acceptance", "promotion"})
    _validate_runs_and_retrieval(trace)
    proposed, reports, operations = items(trace["productions"], 2), items(trace["reports"], 2), items(trace["operations"], 2)
    if (not proposed or len(proposed) != len(reports) or len(proposed) != len(operations)
            or trace["promotion"] != "NOT_PERFORMED" or trace["pedagogical_acceptance"] != "NOT_PERFORMED"):
        raise ValueError("P0_CODESIGN_DOCUMENTARY_TRACE")
    if trace["correction"] != ("ONE_BOUNDED_CHILD" if len(proposed) == 2 else "NOT_REQUIRED"):
        raise ValueError("P0_CODESIGN_DOCUMENTARY_TRACE")
    runs = items(trace["runs"], 2)
    if not runs or runs[0].get("workflow_kind") != "WF-6" or len(runs) != len(proposed):
        raise ValueError("P0_CODESIGN_DOCUMENTARY_RUNS")
    if len(runs) == 2 and (runs[1].get("workflow_kind") != "WF-7" or runs[1].get("parent_run_id") != runs[0].get("run_id")
            or runs[1].get("source_sha256") != runs[0].get("result_sha256")):
        raise ValueError("P0_CODESIGN_DOCUMENTARY_RUNS")
    evidence_ids = {str(row["evidence_id"]) for row in items(bundle.data["references"], 8)}
    matched = False
    for index, (raw, report, operation) in enumerate(zip(proposed, reports, operations, strict=True)):
        candidate = P0Production(raw)
        if candidate.production_ref != bundle.production_ref:
            raise ValueError("P0_CODESIGN_DOCUMENTARY_IDENTITY")
        validate_p0_review_binding(report, production_ref=candidate.production_ref, version_ref=candidate.version_ref,
            bundle_sha256=candidate.sha256, evidence_ids=evidence_ids)
        lineage = object_data(candidate.data["lineage"])
        operation = object_data(operation, {"run_id", "step_id", "request_id", "capability", "parent_version_ref", "version_ref", "bundle_sha256", "correction", "controls"})
        _validate_controls(operation["controls"], candidate.sha256, evidence_ids)
        if (operation["run_id"] != lineage["source_run_id"] or operation["step_id"] != lineage["source_step_id"]
                or operation["request_id"] != lineage["source_request_id"] or operation["version_ref"] != candidate.version_ref
                or operation["bundle_sha256"] != candidate.sha256 or operation["parent_version_ref"] != lineage["parent_version_ref"]):
            raise ValueError("P0_CODESIGN_DOCUMENTARY_IDENTITY")
        run = runs[index]
        if (operation["run_id"] != run.get("run_id") or run.get("result_sha256") != candidate.sha256
                or candidate.data["context"] != bundle.data["context"] or candidate.data["references"] != bundle.data["references"]):
            raise ValueError("P0_CODESIGN_DOCUMENTARY_IDENTITY")
        if index == 0:
            if operation["capability"] not in {"CAP-G01", "CAP-G02"} or operation["correction"] is not None:
                raise ValueError("P0_CODESIGN_DOCUMENTARY_OPERATION")
        else:
            previous = P0Production(proposed[index-1])
            c11 = object_data(operation["correction"], {"contract_id", "review_ref", "parent_bundle_sha256", "finding_ids",
                "allowed_paths", "addressed_findings", "unresolved_findings", "change_summary", "resolution", "new_warnings_json"})
            _text(c11["change_summary"], 4000)
            _text(c11["new_warnings_json"], 16384)
            _text(c11["review_ref"], 71)
            _strings(c11["finding_ids"], 32, required=True)
            _strings(c11["addressed_findings"], 32)
            _strings(c11["unresolved_findings"], 32)
            paths = correction_paths(previous, reports[index-1])
            ids = {str(row["finding_id"]) for row in items(reports[index-1]["findings"], 32)
                   if row["correction_required"] or row.get("severity") == "blocking"}
            addressed, unresolved = c11["addressed_findings"], c11["unresolved_findings"]
            declared = c11["finding_ids"]
            if (operation["capability"] != "CAP-G03" or c11["contract_id"] != "P0-C11C12-DOCUMENTARY-1.0"
                    or c11["review_ref"] != "review:" + fingerprint(reports[index-1])
                    or c11["parent_bundle_sha256"] != previous.sha256 or object_data(candidate.data["lineage"])["parent_version_ref"] != previous.version_ref
                    or fingerprint(c11["allowed_paths"]) != fingerprint(paths)
                    or not isinstance(declared, (list, tuple)) or set(declared) != ids
                    or not isinstance(addressed, (list, tuple)) or not isinstance(unresolved, (list, tuple))
                    or set(addressed) & set(unresolved) or set(addressed) | set(unresolved) != ids
                    or c11["resolution"] != "FRESH_REVIEW_REQUIRED"):
                raise ValueError("P0_CODESIGN_DOCUMENTARY_CORRECTION")
            verify_correction_delta(previous, candidate, paths)
        if candidate.sha256 == bundle.sha256:
            if data["parent_bundle_sha256"] != run["source_sha256"]:
                raise ValueError("P0_CODESIGN_DOCUMENTARY_PARENT")
            if index > 0 and data["parent_bundle_sha256"] != P0Production(proposed[index-1]).sha256:
                raise ValueError("P0_CODESIGN_DOCUMENTARY_PARENT")
            matched = True
    if not matched:
        raise ValueError("P0_CODESIGN_DOCUMENTARY_BUNDLE")
    expected = variant_witness(bundle, str(data["parent_bundle_sha256"]), str(data["parent_record_sha256"]), trace)
    if data["witness_sha256"] != expected:
        raise ValueError("P0_CODESIGN_DOCUMENTARY_WITNESS")
    return data


def variant_witness(bundle: P0Production, parent_bundle_sha: str, parent_record_sha: str, trace: Mapping[str, object]) -> str:
    return fingerprint({"domain": "CO_DESIGN_VARIANT_V1", "parent_bundle_sha256": parent_bundle_sha,
        "parent_record_sha256": parent_record_sha, "child_bundle_sha256": bundle.sha256,
        "lineage": as_plain(bundle.data["lineage"]), "trace_sha256": fingerprint(trace)})


def correction_paths(parent: P0Production, report: Mapping[str, object]) -> tuple[tuple[str | int, ...], ...]:
    """AG-01 policy: only exact JSON locators on canonical content, never suggested_action."""
    paths = []
    payload = correction_content(parent)
    for finding in items(report["findings"], 32):
        if not finding["correction_required"] and finding.get("severity") != "blocking":
            continue
        locator = object_data(finding["target_locator"])
        path = locator.get("path")
        if (set(locator) != {"kind", "path"} or locator["kind"] != "json_path"
                or not isinstance(path, (list, tuple)) or not 1 <= len(path) <= 12
                or any(type(part) not in {str, int} for part in path)):
            raise ValueError("P0_CODESIGN_TARGETED_LOCATOR_REQUIRED")
        typed = cast(tuple[str | int, ...], tuple(path))
        if typed[0] == "exercise" and (len(typed) == 1 or typed[1] == "objectives"):
            raise ValueError("P0_CODESIGN_OBJECTIVES_IMMUTABLE")
        _locate(payload, typed)
        paths.append(typed)
    if not paths:
        raise ValueError("P0_CODESIGN_TARGETED_LOCATOR_REQUIRED")
    if "course_chapter" in payload:
        if ("title",) in paths:
            paths.append(("course_chapter", "title"))
        if ("course_chapter", "title") in paths:
            paths.append(("title",))
    return tuple(dict.fromkeys(paths))


def correction_content(bundle: P0Production) -> dict[str, object]:
    keys = ("title", "course_chapter", "limitations") if "course_chapter" in bundle.data else (
        ("title", "exercise", "limitations") if "exercise" in bundle.data else ("title", "sections", "questions", "corrections", "marking", "limitations"))
    return {key: as_plain(bundle.data[key]) for key in keys}


def _locate(data: object, path: tuple[str | int, ...]) -> object:
    current = data
    try:
        for part in path:
            if type(part) is int and isinstance(current, list) and 0 <= part < len(current):
                current = current[part]
            elif type(part) is str and isinstance(current, dict) and part in current:
                current = current[part]
            else:
                raise ValueError("P0_CODESIGN_TARGETED_LOCATOR_REQUIRED")
    except (TypeError, IndexError, KeyError):
        raise ValueError("P0_CODESIGN_TARGETED_LOCATOR_REQUIRED") from None
    return current


def verify_correction_delta(parent: P0Production, child: P0Production, paths: tuple[tuple[str | int, ...], ...]) -> None:
    before, after = deepcopy(correction_content(parent)), deepcopy(correction_content(child))
    for path in sorted(paths, key=len):
        for payload in (before, after):
            container = _locate(payload, path[:-1])
            last = path[-1]
            if isinstance(container, dict) and type(last) is str and last in container:
                container[last] = "BOUNDED_CORRECTION_FIELD"
            elif isinstance(container, list) and type(last) is int and 0 <= last < len(container):
                container[last] = "BOUNDED_CORRECTION_FIELD"
            else:
                raise ValueError("P0_CODESIGN_CORRECTION_SHAPE_CHANGED")
    if before != after:
        raise ValueError("P0_CODESIGN_UNPERMITTED_CORRECTION_DELTA")
